"""
LR Scorecard — Home Credit dataset.

Mục đích: Convert P(default) → FICO-style score 300–850, có breakdown từng feature.
Source : gold.hc_features_v1 (12 engineered features)
Output : ml/models/scorecard_model.pkl

FICO PDO (Points to Double the Odds):
    score = base_score - factor * (model_logit - base_logit)
    factor = PDO / ln(2)
    base_logit = -ln(base_odds_good)

Default params: base_score=600, base_odds_good=50, PDO=20
  → 720 = rất tốt, 600 = trung bình, 500 = rủi ro cao.

Run: python ml/train_scorecard.py
"""
import math
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "scorecard_model.pkl"

sys.path.insert(0, str(BASE_DIR))
from utils.db_connection import get_engine
from ml.validate_data import validate

# ── FICO PDO params ─────────────────────────────────────────────────────────
BASE_SCORE     = 600
BASE_ODDS_GOOD = 50
PDO            = 20
SCORE_MIN      = 300
SCORE_MAX      = 850

_FACTOR     = PDO / math.log(2)
_BASE_LOGIT = -math.log(BASE_ODDS_GOOD)

LOW_THRESHOLD  = 0.20
HIGH_THRESHOLD = 0.40

NUMERIC_FEATURES = [
    "credit_score_midpoint",
    "debt_to_income_ratio",
    "loan_amount_to_income",
    "log_monthly_income",
    "rating_ordinal",
    "is_homeowner_flag",
    "income_verifiable_flag",
    "high_dti_flag",
    "payment_to_income",
    # Real prev-app aggregates
    "num_previous_loans", "previous_default_rate",
    # Bureau aggregates
    "num_bureau_records", "num_active_credit",
    "total_overdue_amount", "max_credit_overdue_days", "has_bad_debt",
    # v3: years_employed thay thế ext_source_1/3
    "years_employed",
    # Demographics
    "age_years", "gender_male_flag", "education_ordinal",
    "cnt_children", "cnt_fam_members", "is_married_flag",
]
CATEGORICAL_FEATURES = ["employment_status_grouped", "occupation_type"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

QUERY = """
SELECT
    credit_score_midpoint, debt_to_income_ratio, loan_amount_to_income,
    log_monthly_income, rating_ordinal, is_homeowner_flag,
    income_verifiable_flag, high_dti_flag, payment_to_income,
    num_previous_loans, previous_default_rate,
    num_bureau_records, num_active_credit,
    total_overdue_amount, max_credit_overdue_days, has_bad_debt,
    years_employed,
    age_years, gender_male_flag, education_ordinal,
    cnt_children, cnt_fam_members, is_married_flag,
    employment_status_grouped,
    occupation_type,
    is_default
FROM gold.hc_features_v1
WHERE credit_score_midpoint  IS NOT NULL
  AND debt_to_income_ratio   IS NOT NULL
  AND log_monthly_income     IS NOT NULL
  AND loan_amount_to_income  IS NOT NULL
"""


def prob_to_score(p) -> np.ndarray:
    """Convert P(default) → FICO score in [300, 850]."""
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    logit = np.log(p / (1 - p))
    score = BASE_SCORE - _FACTOR * (logit - _BASE_LOGIT)
    return np.clip(np.round(score), SCORE_MIN, SCORE_MAX).astype(int)


def train():
    validate()

    print("\n" + "=" * 55)
    print("  LR SCORECARD — TRAIN")
    print("=" * 55)
    print(f"  FICO params: base={BASE_SCORE}, odds_good={BASE_ODDS_GOOD}, PDO={PDO}")

    engine = get_engine()

    print("\n[1/6] Loading features from gold.hc_features_v1...")
    df = pd.read_sql(QUERY, engine)
    df[NUMERIC_FEATURES]     = df[NUMERIC_FEATURES].fillna(df[NUMERIC_FEATURES].median())
    df[CATEGORICAL_FEATURES] = df[CATEGORICAL_FEATURES].fillna("Other/Unknown")
    print(f"  Rows: {len(df):,}  |  Default rate: {df['is_default'].mean():.2%}")

    dti_p75 = float(np.percentile(df["debt_to_income_ratio"].dropna(), 75))

    X = df[ALL_FEATURES]
    y = df["is_default"]

    print("\n[2/6] Splitting 80/20 (stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\n[3/6] Building pipeline (StandardScaler + LR)...")
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
         CATEGORICAL_FEATURES),
    ])
    # KHÔNG dùng class_weight="balanced" — scorecard cần probability calibrated
    # tự nhiên (mean ≈ default rate thực) để FICO score trải rộng đúng.
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier",   LogisticRegression(
            C=0.1, max_iter=500, random_state=42,
        )),
    ])

    print("\n[4/6] Training...")
    pipeline.fit(X_train, y_train)

    print("\n[5/6] Evaluating on test set...")
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    auc    = roc_auc_score(y_test, y_prob)
    scores = prob_to_score(y_prob)

    print(f"  ROC-AUC      : {auc:.4f}")
    print(f"  Score range  : {int(scores.min())} – {int(scores.max())}")
    print(f"  Score mean   : {scores.mean():.0f}   median: {int(np.median(scores))}")
    print(classification_report(y_test, y_pred, target_names=["No Default", "Default"]))

    # ── Feature contribution table (1 std-dev → ±points) ───────────────────
    print("\n[6/6] Computing per-feature points...")
    lr            = pipeline.named_steps["classifier"]
    coefficients  = lr.coef_[0]
    feature_names = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    # Mỗi 1 std-dev tăng → log-odds default thay đổi `coef` → điểm thay đổi -factor*coef
    points_per_std = (-_FACTOR * coefficients).round(2)
    contribution = pd.DataFrame({
        "feature":         feature_names,
        "coef":            coefficients.round(4),
        "points_per_std":  points_per_std,
    }).sort_values("points_per_std", ascending=False)
    print(contribution.to_string(index=False))

    artifact = {
        "pipeline":       pipeline,
        "feature_cols":   ALL_FEATURES,
        "thresholds":     {"low": LOW_THRESHOLD, "high": HIGH_THRESHOLD},
        "fico_params": {
            "base_score":     BASE_SCORE,
            "base_odds_good": BASE_ODDS_GOOD,
            "pdo":            PDO,
            "factor":         _FACTOR,
            "base_logit":     _BASE_LOGIT,
            "score_min":      SCORE_MIN,
            "score_max":      SCORE_MAX,
        },
        "contribution_table": contribution.to_dict(orient="records"),
        "dti_p75":            dti_p75,
        "metrics":            {"roc_auc": float(auc)},
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)
    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    train()
