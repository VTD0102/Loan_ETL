"""
LR Scorecard — Stage 1 of two-stage pipeline (v4).

Stage 1: Convert raw application features → FICO-style credit_score_computed (300–850).
Stage 2: LightGBM uses credit_score_computed + other features for risk prediction.

Changes vs v3:
  - Removed: credit_score_midpoint (dominant self-reported feature — now output, not input)
  - Removed: rating_ordinal (derived from credit_score — same source of leakage)
  - Removed: payment_to_income (exact duplicate of debt_to_income_ratio)
  - Removed: has_bad_debt (near-zero variance — 18/300k samples positive)
  - Added: loan_type (1=Cash, 0=Revolving from NAME_CONTRACT_TYPE)
  - occupation_type: OrdinalEncoder → TargetEncoder (encodes by mean default rate per category)
  - OOF 5-fold predictions saved to models/oof_stage1.csv for Stage 2 training

FICO PDO:
    score = base_score - factor * (logit - base_logit)
    factor = PDO / ln(2) = 28.854
    base_score=600, base_odds_good=50, PDO=20

Run: python -m machinelearning.ml.train_scorecard
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
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler, TargetEncoder

BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "scorecard_model.pkl"
OOF_PATH   = BASE_DIR / "ml" / "models" / "oof_stage1.csv"

PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.utils.db_connection import get_engine
from machinelearning.ml.validate_data import validate

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

# v4 feature list (22): removed credit_score_midpoint/rating_ordinal/payment_to_income/has_bad_debt, added loan_type
NUMERIC_FEATURES = [
    "debt_to_income_ratio",
    "loan_amount_to_income",
    "log_monthly_income",
    "is_homeowner_flag",
    "income_verifiable_flag",
    "high_dti_flag",
    "num_previous_loans",
    "previous_default_rate",
    "num_bureau_records",
    "num_active_credit",
    "total_overdue_amount",
    "max_credit_overdue_days",
    "years_employed",
    "age_years",
    "gender_male_flag",
    "education_ordinal",
    "cnt_children",
    "cnt_fam_members",
    "is_married_flag",
    "loan_type",
]
CATEGORICAL_EMP = ["employment_status_grouped"]   # OrdinalEncoder
CATEGORICAL_OCC = ["occupation_type"]             # TargetEncoder
ALL_FEATURES    = NUMERIC_FEATURES + CATEGORICAL_EMP + CATEGORICAL_OCC

QUERY = """
SELECT
    listing_key,
    debt_to_income_ratio, loan_amount_to_income,
    log_monthly_income, is_homeowner_flag,
    income_verifiable_flag, high_dti_flag,
    num_previous_loans, previous_default_rate,
    num_bureau_records, num_active_credit,
    total_overdue_amount, max_credit_overdue_days,
    years_employed,
    age_years, gender_male_flag, education_ordinal,
    cnt_children, cnt_fam_members, is_married_flag,
    loan_type,
    employment_status_grouped,
    occupation_type,
    is_default
FROM gold.hc_features_v1
WHERE debt_to_income_ratio  IS NOT NULL
  AND log_monthly_income    IS NOT NULL
  AND loan_amount_to_income IS NOT NULL
"""

N_FOLDS = 5


def prob_to_score(p) -> np.ndarray:
    """Convert P(default) → FICO score in [300, 850]."""
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    logit = np.log(p / (1 - p))
    score = BASE_SCORE - _FACTOR * (logit - _BASE_LOGIT)
    return np.clip(np.round(score), SCORE_MIN, SCORE_MAX).astype(int)


def _build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat_emp", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
         CATEGORICAL_EMP),
        ("cat_occ", TargetEncoder(target_type="binary"), CATEGORICAL_OCC),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(C=0.1, max_iter=500, random_state=42)),
    ])


def train():
    validate()

    print("\n" + "=" * 55)
    print("  LR SCORECARD — TRAIN v4 (two-stage pipeline)")
    print("=" * 55)
    print(f"  FICO params: base={BASE_SCORE}, odds_good={BASE_ODDS_GOOD}, PDO={PDO}")

    engine = get_engine()

    print("\n[1/7] Loading features from gold.hc_features_v1...")
    df = pd.read_sql(QUERY, engine)
    df[NUMERIC_FEATURES]  = df[NUMERIC_FEATURES].fillna(df[NUMERIC_FEATURES].median())
    df[CATEGORICAL_EMP]   = df[CATEGORICAL_EMP].fillna("Other/Unknown")
    df[CATEGORICAL_OCC]   = df[CATEGORICAL_OCC].fillna("Unknown")
    print(f"  Rows: {len(df):,}  |  Default rate: {df['is_default'].mean():.2%}")
    print(f"  loan_type distribution: {df['loan_type'].value_counts().to_dict()}")

    dti_p75 = float(np.percentile(df["debt_to_income_ratio"].dropna(), 75))

    keys = df["listing_key"].values
    X    = df[ALL_FEATURES]
    y    = df["is_default"]

    print(f"\n[2/7] {N_FOLDS}-fold OOF predictions for Stage 2 training...")
    kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
    oof_probs = np.zeros(len(X))

    for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr = y.iloc[train_idx]
        fold_pipe = _build_pipeline()
        fold_pipe.fit(X_tr, y_tr)
        oof_probs[val_idx] = fold_pipe.predict_proba(X_val)[:, 1]
        fold_auc = roc_auc_score(y.iloc[val_idx], oof_probs[val_idx])
        print(f"  Fold {fold + 1}/{N_FOLDS}: AUC={fold_auc:.4f}")

    oof_scores = prob_to_score(oof_probs)
    overall_oof_auc = roc_auc_score(y, oof_probs)
    print(f"  OOF AUC : {overall_oof_auc:.4f}")
    print(f"  OOF score range: {oof_scores.min()} – {oof_scores.max()}")

    oof_df = pd.DataFrame({
        "listing_key":           keys,
        "oof_prob":              oof_probs.round(6),
        "credit_score_computed": oof_scores,
    })
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    oof_df.to_csv(OOF_PATH, index=False)
    print(f"  OOF predictions saved → {OOF_PATH}")

    print("\n[3/7] Splitting 80/20 (stratified) for held-out eval...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\n[4/7] Training final pipeline on all data...")
    final_pipeline = _build_pipeline()
    final_pipeline.fit(X, y)

    print("\n[5/7] Evaluating on held-out 20% (for reporting only)...")
    y_prob_test = final_pipeline.predict_proba(X_test)[:, 1]
    y_pred_test = (y_prob_test >= 0.5).astype(int)
    auc         = roc_auc_score(y_test, y_prob_test)
    scores      = prob_to_score(y_prob_test)

    print(f"  ROC-AUC      : {auc:.4f}")
    print(f"  Score range  : {int(scores.min())} – {int(scores.max())}")
    print(f"  Score mean   : {scores.mean():.0f}   median: {int(np.median(scores))}")
    print(classification_report(y_test, y_pred_test, target_names=["No Default", "Default"]))

    print("\n[6/7] Computing per-feature points (1 std-dev → ±points)...")
    lr           = final_pipeline.named_steps["classifier"]
    coefficients = lr.coef_[0]
    feature_names_pipeline = NUMERIC_FEATURES + CATEGORICAL_EMP + CATEGORICAL_OCC
    points_per_std = (-_FACTOR * coefficients).round(2)
    contribution = pd.DataFrame({
        "feature":        feature_names_pipeline,
        "coef":           coefficients.round(4),
        "points_per_std": points_per_std,
    }).sort_values("points_per_std", ascending=False)
    print(contribution.to_string(index=False))

    print("\n[7/7] Saving artifact...")
    artifact = {
        "pipeline":       final_pipeline,
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
        "metrics":            {"roc_auc": float(auc), "oof_auc": float(overall_oof_auc)},
        "model_version":      "scorecard_lr_v4",
    }
    joblib.dump(artifact, MODEL_PATH)
    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    train()
