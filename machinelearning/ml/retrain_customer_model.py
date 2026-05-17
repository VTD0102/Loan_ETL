"""
Customer Risk Model (LightGBM) — Stage 2 of two-stage pipeline (v4).

Stage 1: Scorecard (LR) computes credit_score_computed (300–850) from raw features.
Stage 2: LightGBM uses credit_score_computed + other features for risk classification.

Changes vs v3:
  - Removed: credit_score (self-reported — replaced by credit_score_computed from Stage 1)
  - Removed: rating_ordinal (derived from credit_score — same source of leakage)
  - Removed: listing_category (was hardcoded constant 1 — zero variance)
  - Removed: has_bad_debt (near-zero variance — 18/300k samples positive)
  - Added: credit_score_computed (OOF Stage 1 predictions — FICO 300–850)
  - Added: loan_type (1=Cash, 0=Revolving)
  - OOF predictions loaded from models/oof_stage1.csv (produced by train_scorecard.py)

Feature count: 26
  Numeric (24): dti, monthly_income, loan_amount, term, is_homeowner, years_employed,
                num_previous_loans, previous_default_rate, num_bureau_records,
                num_active_credit, total_overdue_amount, max_credit_overdue_days,
                income_verifiable_flag, high_dti_flag, log_monthly_income,
                loan_amount_to_income, age_years, gender_male_flag, education_ordinal,
                cnt_children, cnt_fam_members, is_married_flag, credit_score_computed,
                loan_type
  Categorical (2): employment_status, occupation_type

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
from machinelearning.utils.db_connection import get_engine
from machinelearning.ml.validate_data import validate

MODEL_PATH    = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"
OOF_PATH      = BASE_DIR / "ml" / "models" / "oof_stage1.csv"
MODEL_VERSION = "customer_lgbm_v4"

LOW_THRESHOLD  = 0.2
HIGH_THRESHOLD = 0.4

_QUERY = """
SELECT
    f.listing_key,

    -- ── Core loan features ────────────────────────────────────────────────
    f.stated_monthly_income                                     AS monthly_income,
    f.loan_original_amount                                      AS loan_amount,
    f.term,
    f.employment_status_grouped                                 AS employment_status,
    f.debt_to_income_ratio                                      AS dti,
    f.is_homeowner_flag                                         AS is_homeowner,
    f.loan_type,

    -- ── Employment & occupation ───────────────────────────────────────────
    f.years_employed,
    f.occupation_type,

    -- ── Bureau / credit history ───────────────────────────────────────────
    f.num_previous_loans, f.previous_default_rate,
    f.num_bureau_records, f.num_active_credit,
    f.total_overdue_amount, f.max_credit_overdue_days,

    -- ── Derived flags ─────────────────────────────────────────────────────
    f.income_verifiable_flag, f.high_dti_flag,
    f.log_monthly_income, f.loan_amount_to_income,

    -- ── Demographics ─────────────────────────────────────────────────────
    f.age_years, f.gender_male_flag, f.education_ordinal,
    f.cnt_children, f.cnt_fam_members, f.is_married_flag,

    f.is_default
FROM gold.hc_features_v1 f
WHERE f.debt_to_income_ratio    IS NOT NULL
  AND f.stated_monthly_income   IS NOT NULL
  AND f.loan_original_amount    IS NOT NULL
  AND f.years_employed          IS NOT NULL
  AND f.occupation_type         IS NOT NULL
"""

NUMERIC_FEATURES = [
    # Core
    "monthly_income", "loan_amount", "term", "dti", "is_homeowner",
    # Employment
    "years_employed",
    # Bureau/history
    "num_previous_loans", "previous_default_rate",
    "num_bureau_records", "num_active_credit",
    "total_overdue_amount", "max_credit_overdue_days",
    # Derived
    "income_verifiable_flag", "high_dti_flag",
    "log_monthly_income", "loan_amount_to_income",
    # Demographics
    "age_years", "gender_male_flag", "education_ordinal",
    "cnt_children", "cnt_fam_members", "is_married_flag",
    # Stage 1 output (OOF)
    "credit_score_computed",
    # Loan type
    "loan_type",
]
CATEGORICAL_FEATURES = ["employment_status", "occupation_type"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

OCCUPATION_CATEGORIES = [
    "Accountants", "Cleaning staff", "Cooking staff", "Core staff", "Drivers",
    "HR staff", "High skill tech staff", "IT staff", "Laborers", "Low-skill Laborers",
    "Managers", "Medicine staff", "Private service staff", "Realty agents",
    "Sales staff", "Secretaries", "Security staff", "Waiters/barmen staff", "Unknown",
]
EMPLOYMENT_CATEGORIES = [
    "Employed", "Self-employed", "Retired", "Not employed", "Other/Unknown",
]


def train():
    validate()

    print("\n" + "=" * 55)
    print("  CUSTOMER RISK MODEL — RETRAIN (v4)")
    print("=" * 55)

    # ── 1. Load Stage 1 OOF predictions ─────────────────────────────────────
    print(f"\n[1/7] Loading Stage 1 OOF predictions from {OOF_PATH.name}...")
    if not OOF_PATH.exists():
        raise FileNotFoundError(
            f"{OOF_PATH} not found. Run train_scorecard.py first to generate OOF predictions."
        )
    oof_df = pd.read_csv(OOF_PATH, dtype={"listing_key": str})
    print(f"  OOF rows: {len(oof_df):,}")
    print(f"  credit_score_computed range: {oof_df['credit_score_computed'].min()} – {oof_df['credit_score_computed'].max()}")

    # ── 2. Fetch gold data ───────────────────────────────────────────────────
    print("\n[2/7] Fetching data from gold.hc_features_v1...")
    engine = get_engine()
    df = pd.read_sql(_QUERY, engine)
    print(f"  Rows: {len(df):,}  |  Features (before OOF merge): {len(ALL_FEATURES) - 1}")

    # ── 3. Merge OOF predictions ─────────────────────────────────────────────
    print("\n[3/7] Merging OOF credit_score_computed...")
    df = df.merge(oof_df[["listing_key", "credit_score_computed"]], on="listing_key", how="inner")
    print(f"  Rows after merge: {len(df):,}")

    # ── 4. Clean ─────────────────────────────────────────────────────────────
    print("\n[4/7] Cleaning data...")
    df["employment_status"] = df["employment_status"].fillna("Other/Unknown")
    df["occupation_type"]   = df["occupation_type"].fillna("Unknown")
    df = df.dropna(subset=["is_default", "monthly_income", "loan_amount"])
    print(f"  Rows after dropna: {len(df):,}")
    print(f"  Default rate: {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES]
    y = df["is_default"]
    feature_defaults = _feature_defaults(X)
    dti_p75 = float(df["dti"].quantile(0.75))

    # ── 5. Split 80/20 ───────────────────────────────────────────────────────
    print("\n[5/7] Splitting 80/20 (stratified by is_default)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train):,} rows | Test: {len(X_test):,} rows")

    # ── 6. Build pipeline ────────────────────────────────────────────────────
    print("\n[6/7] Building pipeline (LightGBM)...")
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
            n_estimators=500,
            learning_rate=0.05,
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
    print("  Pipeline: passthrough numeric + OrdinalEncoder(2 cats) → LightGBM")
    pipeline.fit(X_train, y_train)

    # ── 7. Evaluate ──────────────────────────────────────────────────────────
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)

    print(f"\n  --- Model Evaluation (Test Set) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["No Default", "Default"]))

    _print_threshold_analysis(y_test, y_prob)

    # Feature importance
    lgbm = pipeline.named_steps["classifier"]
    feat_names = pipeline.named_steps["preprocessor"].get_feature_names_out().tolist()
    importances = lgbm.feature_importances_
    imp_df = (
        pd.DataFrame({"feature": feat_names, "importance": importances})
        .sort_values("importance", ascending=False)
        .head(15)
    )
    print("\n  Top-15 feature importances:")
    print(imp_df.to_string(index=False))

    # ── 8. Save artifact ─────────────────────────────────────────────────────
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline"          : pipeline,
        "feature_cols"      : ALL_FEATURES,
        "feature_names_out" : feat_names,
        "feature_defaults"  : feature_defaults,
        "thresholds"        : {"low": LOW_THRESHOLD, "high": HIGH_THRESHOLD},
        "dti_p75"           : dti_p75,
        "model_version"     : MODEL_VERSION,
        "trained_at"        : datetime.now(timezone.utc).isoformat(),
        "metrics"           : {"roc_auc": float(auc)},
    }, MODEL_PATH)
    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


def _print_threshold_analysis(y_test, y_prob):
    print("\n  --- Threshold Analysis ---")
    for t in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
        mask      = y_prob >= t
        rejected  = int(mask.sum())
        recall    = float(y_test[mask].sum()) / max(y_test.sum(), 1)
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
