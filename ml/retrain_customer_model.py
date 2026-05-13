"""
Retrain customer risk model (LightGBM) on Home Credit dataset.
Source : silver.home_credit_cleansed (DuckDB local)
Output : ml/models/customer_risk_model.pkl

Run from project root:
    python -m ml.retrain_customer_model
"""
import sys
from datetime import datetime, timezone
import joblib
import pandas as pd
from pathlib import Path
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
from utils.db_connection import get_engine
from ml.validate_data import validate

MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"
MODEL_VERSION = "customer_lgbm_v2"

# ── Risk thresholds — used by backend/services/ml_service.py at inference ────
LOW_THRESHOLD  = 0.2
HIGH_THRESHOLD = 0.4

_QUERY = """
SELECT
    -- Original 8 customer-input features
    stated_monthly_income                                       AS monthly_income,
    loan_original_amount                                        AS loan_amount,
    term,
    employment_status_grouped                                   AS employment_status,
    debt_to_income_ratio                                        AS dti,
    is_homeowner_flag                                           AS is_homeowner,
    1                                                           AS listing_category,
    credit_score_midpoint                                       AS credit_score,

    -- ── Rich credit / bureau / prev-app features ───────────────────────────
    ext_source_1, ext_source_3,
    num_previous_loans, previous_default_rate,
    num_bureau_records, num_active_credit,
    total_overdue_amount, max_credit_overdue_days, has_bad_debt,
    income_verifiable_flag, high_dti_flag, rating_ordinal,
    log_monthly_income, loan_amount_to_income,

    -- ── Demographics (Phase 3) ────────────────────────────────────────────
    age_years, gender_male_flag, education_ordinal,
    cnt_children, cnt_fam_members, is_married_flag,

    is_default
FROM gold.hc_features_v1
WHERE credit_score_midpoint   IS NOT NULL
  AND stated_monthly_income   IS NOT NULL
  AND loan_original_amount    IS NOT NULL
  AND debt_to_income_ratio    IS NOT NULL
"""

NUMERIC_FEATURES = [
    # Original 8
    "monthly_income", "loan_amount", "term", "dti",
    "is_homeowner", "listing_category", "credit_score",
    # Rich gold features
    "ext_source_1", "ext_source_3",
    "num_previous_loans", "previous_default_rate",
    "num_bureau_records", "num_active_credit",
    "total_overdue_amount", "max_credit_overdue_days", "has_bad_debt",
    "income_verifiable_flag", "high_dti_flag", "rating_ordinal",
    "log_monthly_income", "loan_amount_to_income",
    # Demographics (Phase 3)
    "age_years", "gender_male_flag", "education_ordinal",
    "cnt_children", "cnt_fam_members", "is_married_flag",
]
CATEGORICAL_FEATURES = ["employment_status"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# ── Query from silver layer ───────────────────────────────────────────────────
# FIX: correct column names from transform_silver.sql:
#   is_borrower_homeowner  BOOLEAN  (not is_homeowner / not 'Yes' string)
#   listing_category_numeric INTEGER (not listing_category_id)
#   employment_status      VARCHAR  ✅
SILVER_QUERY = """
SELECT
    stated_monthly_income
        AS monthly_income,
    loan_original_amount
        AS loan_amount,
    term,
    COALESCE(employment_status, 'Other')
        AS employment_status,
    debt_to_income_ratio
        AS dti,
    CASE WHEN is_borrower_homeowner IS TRUE THEN 1 ELSE 0 END
        AS is_homeowner,
    listing_category_numeric
        AS listing_category,
    (credit_score_range_upper + credit_score_range_lower) / 2.0
        AS credit_score,
    is_default
FROM silver.prosper_loans_cleansed
WHERE stated_monthly_income    IS NOT NULL
  AND loan_original_amount     IS NOT NULL
  AND debt_to_income_ratio     IS NOT NULL
  AND credit_score_range_upper IS NOT NULL
  AND credit_score_range_lower IS NOT NULL
  AND term                     IS NOT NULL
"""


def train():
    validate()

    print("\n" + "=" * 55)
    print("  CUSTOMER RISK MODEL — RETRAIN")
    print("=" * 55)

    # ── 1. Connect & fetch ───────────────────────────────
    print("\n[1/6] Connecting to database...")
    engine = get_engine()

    print("\n[1/6] Fetching data from gold.hc_features_v1...")
    df = pd.read_sql(_QUERY, engine)
    print(f"  Rows: {len(df):,}  |  Features: {len(ALL_FEATURES)}")

    print("\n[2/6] Cleaning data...")
    # Cột có null nhiều → fill median; LightGBM xử lý OK
    for col in ["ext_source_1", "ext_source_3",
                "gender_male_flag", "education_ordinal", "age_years",
                "cnt_children", "cnt_fam_members", "is_married_flag"]:
        df[col] = df[col].fillna(df[col].median())
    df["employment_status"] = df["employment_status"].fillna("Other/Unknown")
    df = df.dropna(subset=["is_default", "monthly_income", "loan_amount", "credit_score"])
    print(f"  Rows after dropna: {len(df):,}")
    print(f"  Default rate: {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES]
    y = df["is_default"]
    feature_defaults = _feature_defaults(X)
    dti_p75 = float(df["dti"].quantile(0.75))

    # ── 3. Split ─────────────────────────────────────────
    print("\n[4/6] Splitting 80/20 (stratified by is_default)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )
    print(f"  Train: {len(X_train)} rows | Test: {len(X_test)} rows")

    print("\n[4/6] Building pipeline (LightGBM)...")
    # LightGBM xử lý numeric trực tiếp; categorical chỉ cần ordinal-encode
    preprocessor = ColumnTransformer([
        ("num", "passthrough", NUMERIC_FEATURES),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
         CATEGORICAL_FEATURES),
    ])

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LGBMClassifier(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            max_depth=-1,
            min_child_samples=50,
            reg_alpha=0.1,
            reg_lambda=0.1,
            is_unbalance=True,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )),
    ])

    print("  Pipeline: numeric passthrough + OrdinalEncoder → LightGBM")

    # ── 5. Train ─────────────────────────────────────────
    print("\n[6/6] Training...")
    pipeline.fit(X_train, y_train)

    # ── 6. Evaluate ──────────────────────────────────────
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)

    print(f"\n  --- Model Evaluation (Test Set) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(classification_report(
        y_test, y_pred,
        target_names=["No Default", "Default"]
    ))

    # ── 7. Save artifact ─────────────────────────────────
    feature_names_out = (
        pipeline
        .named_steps["preprocessor"]
        .get_feature_names_out()
        .tolist()
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline"           : pipeline,
        "feature_cols"       : ALL_FEATURES,
        "feature_names_out"  : feature_names_out,
        "feature_defaults"   : feature_defaults,
        "thresholds"         : {"low": LOW_THRESHOLD, "high": HIGH_THRESHOLD},
        "dti_p75"            : dti_p75,
        "model_version"      : MODEL_VERSION,
        "trained_at"         : datetime.now(timezone.utc).isoformat(),
    }, MODEL_PATH)
    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


def _feature_defaults(X: pd.DataFrame) -> dict:
    defaults = {}
    for col in NUMERIC_FEATURES:
        value = X[col].median()
        defaults[col] = 0 if pd.isna(value) else _python_scalar(value)
    for col in CATEGORICAL_FEATURES:
        mode = X[col].mode(dropna=True)
        defaults[col] = "Other/Unknown" if mode.empty else str(mode.iloc[0])
    return defaults


def _python_scalar(value):
    if hasattr(value, "item"):
        return value.item()
    return value


if __name__ == "__main__":
    train()
