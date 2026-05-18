"""
Retrain customer risk model (LightGBM) - v4 (Stability dataset).

Changes vs v3:
  - Source: gold.hc_features_v2 (Home Credit Credit Risk Model Stability).
  - Removed credit_score / credit_score_midpoint and rating_ordinal.
  - Removed gender_male_flag, cnt_children, cnt_fam_members.
  - Added debt-burden, DPD, bureau, CB-query, prolongation, and missing flags.
  - Runtime-unavailable features are filled from artifact feature_defaults.

Feature count: 35
  Numeric (33): income/loan, debt burden, DPD, bureau, previous apps,
                CB queries, demographics, missing flags.
  Categorical (2): employment_status, occupation_type.

Source : gold.hc_features_v2 (DuckDB local)
Output : machinelearning/ml/models/customer_risk_model.pkl

Run from project root:
    python -m machinelearning.ml.retrain_customer_model
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.ml.validate_data import validate
from machinelearning.utils.db_connection import get_engine

MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"
MODEL_VERSION = "customer_lgbm_v4_stability"

LOW_THRESHOLD = 0.2
HIGH_THRESHOLD = 0.4

_QUERY = """
SELECT
    -- Income & loan
    stated_monthly_income                                       AS monthly_income,
    loan_original_amount                                        AS loan_amount,
    term,
    debt_to_income_ratio                                        AS dti,
    loan_amount_to_income,

    -- Derived income
    log_monthly_income,
    high_dti_flag,
    payment_to_income,

    -- Debt burden
    current_debt_ratio,
    total_debt_to_income,

    -- DPD features
    max_dpd_24m,
    avg_dpd_recent,
    num_installs_dpd10,
    num_active_credit,

    -- Bureau / credit history
    num_bureau_records,
    num_active_credit                                           AS num_active_credit_bureau,
    total_overdue_amount,
    max_credit_overdue_days,
    has_bad_debt,
    total_prolongations,
    max_overdue_amount,

    -- Previous applications
    num_previous_loans,
    previous_default_rate,

    -- CB queries
    cb_queries_30d,
    num_cb_queries,

    -- Demographics
    age_years,
    years_employed,
    education_ordinal,
    is_homeowner_flag                                           AS is_homeowner,
    income_verifiable_flag,
    is_married_flag,

    -- Missing indicators
    income_missing_flag,
    dti_missing_flag,

    -- Categorical
    employment_status_grouped                                   AS employment_status,
    occupation_type,

    -- Target
    is_default
FROM gold.hc_features_v2
WHERE age_years IS NOT NULL
"""

NUMERIC_FEATURES = [
    # Income & loan
    "monthly_income", "loan_amount", "term", "dti", "loan_amount_to_income",
    # Derived income
    "log_monthly_income", "high_dti_flag", "payment_to_income",
    # Debt burden
    "current_debt_ratio", "total_debt_to_income",
    # DPD
    "max_dpd_24m", "avg_dpd_recent", "num_installs_dpd10", "num_active_credit",
    # Bureau
    "num_bureau_records", "num_active_credit_bureau",
    "total_overdue_amount", "max_credit_overdue_days", "has_bad_debt",
    "total_prolongations", "max_overdue_amount",
    # Previous apps
    "num_previous_loans", "previous_default_rate",
    # CB queries
    "cb_queries_30d", "num_cb_queries",
    # Demographics
    "age_years", "years_employed", "education_ordinal",
    "is_homeowner", "income_verifiable_flag", "is_married_flag",
    # Missing flags
    "income_missing_flag", "dti_missing_flag",
]
CATEGORICAL_FEATURES = ["employment_status", "occupation_type"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

EMPLOYMENT_CATEGORIES = [
    "Employed", "Self-employed", "Retired", "Not employed", "Other/Unknown",
]
OCCUPATION_CATEGORIES = [
    "EMPLOYED", "PRIVATE_SECTOR_EMPLOYEE", "SALARIED_GOVT",
    "RETIRED_PENSIONER", "SELFEMPLOYED", "HANDICAPPED",
    "HANDICAPPED_2", "HANDICAPPED_3", "OTHER",
]


def train():
    validate()

    print("\n" + "=" * 60)
    print("  CUSTOMER RISK MODEL - RETRAIN (v4 Stability)")
    print("=" * 60)

    print("\n[1/6] Fetching data from gold.hc_features_v2...")
    engine = get_engine()
    df = pd.read_sql(_QUERY, engine)
    print(f"  Rows: {len(df):,}  |  Features: {len(ALL_FEATURES)}")

    print("\n[2/6] Cleaning data...")
    df["employment_status"] = df["employment_status"].fillna("Other/Unknown")
    df["occupation_type"] = df["occupation_type"].fillna("OTHER")
    df = df.dropna(subset=["is_default"])
    print(f"  Rows after dropna: {len(df):,}")
    print(f"  Default rate: {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES]
    y = df["is_default"]
    feature_defaults = _feature_defaults(X)
    dti_p75 = float(df["dti"].quantile(0.75)) if df["dti"].notna().any() else 0.5

    print("\n[3/6] Splitting 80/20 (stratified by is_default)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train):,} rows | Test: {len(X_test):,} rows")

    print("\n[4/6] Building pipeline (LightGBM)...")
    preprocessor = ColumnTransformer([
        ("num", "passthrough", NUMERIC_FEATURES),
        ("cat", OrdinalEncoder(
            categories=[EMPLOYMENT_CATEGORIES, OCCUPATION_CATEGORIES],
            handle_unknown="use_encoded_value",
            unknown_value=-1,
        ), CATEGORICAL_FEATURES),
    ])

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LGBMClassifier(
            n_estimators=800,
            learning_rate=0.03,
            num_leaves=63,
            max_depth=-1,
            min_child_samples=50,
            reg_alpha=0.1,
            reg_lambda=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            is_unbalance=True,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )),
    ])
    print("  Pipeline: passthrough numeric + OrdinalEncoder(2 cats) -> LightGBM")

    print("\n[5/6] Training...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print("\n  --- Model Evaluation (Test Set) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["No Default", "Default"]))

    _print_threshold_analysis(y_test, y_prob)

    feature_names_out = (
        pipeline.named_steps["preprocessor"].get_feature_names_out().tolist()
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline": pipeline,
        "feature_cols": ALL_FEATURES,
        "feature_names_out": feature_names_out,
        "feature_defaults": feature_defaults,
        "thresholds": {"low": LOW_THRESHOLD, "high": HIGH_THRESHOLD},
        "dti_p75": dti_p75,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }, MODEL_PATH)
    print(f"\n  Saved -> {MODEL_PATH}")
    print("=" * 60)


def _print_threshold_analysis(y_test, y_prob):
    print("\n  --- Threshold Analysis ---")
    for t in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
        mask = y_prob >= t
        rejected = mask.sum()
        recall = float(y_test[mask].sum()) / max(y_test.sum(), 1)
        precision = float(y_test[mask].mean()) if mask.sum() > 0 else 0
        print(f"  threshold={t:.2f} | rejected={rejected:,} "
              f"| recall(default)={recall:.2%} | precision={precision:.2%}")


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
