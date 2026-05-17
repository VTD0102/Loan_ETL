"""
Retrain customer risk model (LightGBM) — v3.1.

Changes vs v3:
  - Added PR-AUC
  - Added Brier score
  - Added Risk Band Report
  - Added metrics dict into artifact
  - Removed unused `pred` variable in threshold analysis

Changes vs v2:
  - Removed ext_source_1, ext_source_3 (third-party scores, unavailable at inference)
  - Added years_employed (from DAYS_EMPLOYED), occupation_type (18 HC categories)
  - All 22 user-input features are now required — no median imputation at inference
  - LightGBM handles NaN natively in training (Gold rows with sparse demographics)

Feature count: 28
  User-input (22): 8 core + 6 bureau + 6 demographics + years_employed + occupation_type
  Auto-computed (4): log_monthly_income, loan_amount_to_income, rating_ordinal, high_dti_flag
  DB history (2): num_previous_loans, previous_default_rate

Source : gold.hc_features_v1 (DuckDB local, after running etl.pipeline)
Output : ml/models/customer_risk_model.pkl

Run from project root:
    python -m ml.retrain_customer_model
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from utils.db_connection import get_engine  # noqa: E402
from ml.validate_data import validate       # noqa: E402


MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"
MODEL_VERSION = "customer_lgbm_v3_1_metrics"

LOW_THRESHOLD = 0.2
HIGH_THRESHOLD = 0.4


_QUERY = """
SELECT
    -- ── Core loan features (8) ────────────────────────────────────────────
    stated_monthly_income                                       AS monthly_income,
    loan_original_amount                                        AS loan_amount,
    term,
    employment_status_grouped                                   AS employment_status,
    debt_to_income_ratio                                        AS dti,
    is_homeowner_flag                                           AS is_homeowner,
    1                                                           AS listing_category,
    credit_score_midpoint                                       AS credit_score,

    -- ── v3 new: years_employed + occupation_type ─────────────────────────
    years_employed,
    occupation_type,

    -- ── Bureau / credit history features (6) ─────────────────────────────
    num_previous_loans, previous_default_rate,
    num_bureau_records, num_active_credit,
    total_overdue_amount, max_credit_overdue_days, has_bad_debt,

    -- ── Derived flags (4) ─────────────────────────────────────────────────
    income_verifiable_flag, high_dti_flag, rating_ordinal,
    log_monthly_income, loan_amount_to_income,

    -- ── Demographics (6) ─────────────────────────────────────────────────
    age_years, gender_male_flag, education_ordinal,
    cnt_children, cnt_fam_members, is_married_flag,

    is_default
FROM gold.hc_features_v1
WHERE credit_score_midpoint   IS NOT NULL
  AND stated_monthly_income   IS NOT NULL
  AND loan_original_amount    IS NOT NULL
  AND debt_to_income_ratio    IS NOT NULL
  AND years_employed          IS NOT NULL
  AND occupation_type         IS NOT NULL
"""


NUMERIC_FEATURES = [
    # Core 8
    "monthly_income",
    "loan_amount",
    "term",
    "dti",
    "is_homeowner",
    "listing_category",
    "credit_score",

    # v3 new
    "years_employed",

    # Bureau/history
    "num_previous_loans",
    "previous_default_rate",
    "num_bureau_records",
    "num_active_credit",
    "total_overdue_amount",
    "max_credit_overdue_days",
    "has_bad_debt",

    # Derived
    "income_verifiable_flag",
    "high_dti_flag",
    "rating_ordinal",
    "log_monthly_income",
    "loan_amount_to_income",

    # Demographics
    "age_years",
    "gender_male_flag",
    "education_ordinal",
    "cnt_children",
    "cnt_fam_members",
    "is_married_flag",
]

CATEGORICAL_FEATURES = [
    "employment_status",
    "occupation_type",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


# All 18 HC occupation types + Unknown for NULL rows in training data
OCCUPATION_CATEGORIES = [
    "Accountants",
    "Cleaning staff",
    "Cooking staff",
    "Core staff",
    "Drivers",
    "HR staff",
    "High skill tech staff",
    "IT staff",
    "Laborers",
    "Low-skill Laborers",
    "Managers",
    "Medicine staff",
    "Private service staff",
    "Realty agents",
    "Sales staff",
    "Secretaries",
    "Security staff",
    "Waiters/barmen staff",
    "Unknown",
]

EMPLOYMENT_CATEGORIES = [
    "Employed",
    "Self-employed",
    "Retired",
    "Not employed",
    "Other/Unknown",
]


def train():
    validate()

    print("\n" + "=" * 55)
    print("  CUSTOMER RISK MODEL — RETRAIN (LightGBM v3.1)")
    print("=" * 55)

    # ── 1. Connect & fetch ───────────────────────────────────────────────
    print("\n[1/6] Fetching data from gold.hc_features_v1...")
    engine = get_engine()
    df = pd.read_sql(_QUERY, engine)

    print(f"  Rows: {len(df):,}  |  Features: {len(ALL_FEATURES)}")

    # ── 2. Clean ─────────────────────────────────────────────────────────
    print("\n[2/6] Cleaning data...")

    df["employment_status"] = df["employment_status"].fillna("Other/Unknown")
    df["occupation_type"] = df["occupation_type"].fillna("Unknown")

    # LightGBM handles NaN natively for numeric columns — no median fill
    df = df.dropna(
        subset=[
            "is_default",
            "monthly_income",
            "loan_amount",
            "credit_score",
        ]
    )

    print(f"  Rows after dropna: {len(df):,}")
    print(f"  Default rate: {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES]
    y = df["is_default"].astype(int)

    feature_defaults = _feature_defaults(X)
    dti_p75 = float(df["dti"].quantile(0.75))

    # ── 3. Split 80/20 ───────────────────────────────────────────────────
    print("\n[3/6] Splitting 80/20 (stratified by is_default)...")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    print(f"  Train: {len(X_train):,} rows | Test: {len(X_test):,} rows")

    # ── 4. Build pipeline ────────────────────────────────────────────────
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

    # ── 5. Train ─────────────────────────────────────────────────────────
    print("\n[5/6] Training...")
    pipeline.fit(X_train, y_train)

    # ── 6. Evaluate ──────────────────────────────────────────────────────
    print("\n[6/6] Evaluating...")

    y_prob = pipeline.predict_proba(X_test)[:, 1]

    # Giữ y_pred mặc định của LightGBM để so với bản v3 cũ.
    # Nếu muốn report theo business threshold HIGH_THRESHOLD, dùng dòng dưới:
    # y_pred = (y_prob >= HIGH_THRESHOLD).astype(int)
    y_pred = pipeline.predict(X_test)

    auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    print(f"\n  --- Model Evaluation (Test Set) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(f"  PR-AUC  : {pr_auc:.4f}")
    print(f"  Brier   : {brier:.4f}")

    print(classification_report(
        y_test,
        y_pred,
        target_names=["No Default", "Default"],
    ))

    _print_threshold_analysis(y_test, y_prob)
    _print_risk_band_report(y_test, y_prob, LOW_THRESHOLD, HIGH_THRESHOLD)

    # ── 7. Save artifact ─────────────────────────────────────────────────
    feature_names_out = (
        pipeline.named_steps["preprocessor"].get_feature_names_out().tolist()
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump({
        "pipeline": pipeline,
        "feature_cols": ALL_FEATURES,
        "feature_names_out": feature_names_out,
        "feature_defaults": feature_defaults,
        "thresholds": {
            "low": LOW_THRESHOLD,
            "high": HIGH_THRESHOLD,
        },
        "dti_p75": dti_p75,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "roc_auc": round(float(auc), 4),
            "pr_auc": round(float(pr_auc), 4),
            "brier": round(float(brier), 4),
            "default_rate": round(float(y.mean()), 4),
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
        },
        "training_config": {
            "model": "LGBMClassifier",
            "version": MODEL_VERSION,
            "n_estimators": 500,
            "learning_rate": 0.05,
            "num_leaves": 63,
            "max_depth": -1,
            "min_child_samples": 50,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "is_unbalance": True,
            "low_threshold": LOW_THRESHOLD,
            "high_threshold": HIGH_THRESHOLD,
            "random_state": 42,
        },
    }, MODEL_PATH)

    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


def _print_threshold_analysis(y_test, y_prob):
    print("\n  --- Threshold Analysis ---")

    for threshold in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
        mask = y_prob >= threshold
        rejected = int(mask.sum())
        recall = float(y_test[mask].sum()) / max(float(y_test.sum()), 1.0)
        precision = float(y_test[mask].mean()) if rejected > 0 else 0.0

        print(
            f"  threshold={threshold:.2f} | "
            f"rejected={rejected:,} | "
            f"recall(default)={recall:.2%} | "
            f"precision={precision:.2%}"
        )


def _print_risk_band_report(y_true, y_prob, low=0.2, high=0.4):
    """
    Verify Low/Medium/High bands are meaningful.

    A good model should show:
        Low    → low actual default rate
        Medium → moderate actual default rate
        High   → high actual default rate
    """
    report_df = pd.DataFrame({
        "y_true": y_true.values if hasattr(y_true, "values") else y_true,
        "y_prob": y_prob,
    })

    report_df["risk_band"] = pd.cut(
        report_df["y_prob"],
        bins=[-0.001, low, high, 1.001],
        labels=["Low", "Medium", "High"],
    )

    report = report_df.groupby("risk_band", observed=True).agg(
        count=("y_true", "size"),
        avg_pd=("y_prob", "mean"),
        actual_default_rate=("y_true", "mean"),
    ).round(4)

    print("\n  --- Risk Band Report ---")
    print(report.to_string())
    print("  (actual_default_rate should increase Low → Medium → High)")


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