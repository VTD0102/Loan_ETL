"""
Credit score service — computes a FICO-style score (300–850) for a user's
latest submitted loan application using the LR scorecard model trained on
gold.hc_features_v1.

Feature mapping from Supabase application data → HC-style scorecard features:
- credit_score_midpoint  : application.credit_score  (already 300–850)
- debt_to_income_ratio   : (loan_amount / term) / monthly_income  (HC-style)
- payment_to_income      : same as above
- loan_amount_to_income  : loan_amount / (monthly_income * 12)
- log_monthly_income     : ln(1 + monthly_income)
- rating_ordinal         : derived from credit_score via HC band thresholds
- is_homeowner_flag      : 1/0 from is_homeowner
- income_verifiable_flag : 1 if employed/self-employed, else 0
- high_dti_flag          : 1 if HC-DTI > dti_p75 from training data
- num_previous_loans     : prior APPROVED applications for this user
- previous_default_rate  : fraction of prior applications that were rejected
- employment_status_grouped: normalised employment category
"""
import math
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.scoring import pd_to_credit_score, score_to_band
from models.user import User

SCORECARD_PATH = Path(__file__).parents[2] / "ml" / "models" / "scorecard_model.pkl"

NUMERIC_FEATURES     = [
    "credit_score_midpoint", "debt_to_income_ratio", "loan_amount_to_income",
    "log_monthly_income", "rating_ordinal", "is_homeowner_flag",
    "income_verifiable_flag", "high_dti_flag",
    "payment_to_income", "num_previous_loans", "previous_default_rate",
    "num_bureau_records", "num_active_credit", "total_overdue_amount",
    "max_credit_overdue_days", "has_bad_debt", "ext_source_1", "ext_source_3",
    "age_years", "gender_male_flag", "education_ordinal", "cnt_children",
    "cnt_fam_members", "is_married_flag",
]
CATEGORICAL_FEATURES = ["employment_status_grouped"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# HC rating bands (derived from EXT_SOURCE_2 → credit_score thresholds)
_RATING_ORDINAL_MAP = [
    (790, 7),  # AA
    (693, 6),  # A
    (597, 5),  # B
    (500, 4),  # C
    (404, 3),  # D
    (300, 1),  # HR
]

_EMPLOYMENT_GROUP = {
    "Employed":     "Employed",
    "Self-employed":"Self-employed",
    "Retired":      "Retired",
    "Not employed": "Not employed",
    "Unemployed":   "Not employed",
}

_artifact = None


def _load():
    global _artifact
    if _artifact is None:
        _artifact = joblib.load(SCORECARD_PATH)
    return _artifact


def _rating_ordinal(score: int) -> int:
    for threshold, ordinal in _RATING_ORDINAL_MAP:
        if score >= threshold:
            return ordinal
    return 1


def _employment_group(status: str) -> str:
    return _EMPLOYMENT_GROUP.get(status, "Other/Unknown")


def _build_features(app, num_previous_loans: int, previous_default_rate: float,
                    dti_p75: float) -> pd.DataFrame:
    mi   = float(app.monthly_income)
    la   = float(app.loan_amount)
    term = int(app.term)
    cs   = int(app.credit_score)

    hc_dti            = (la / term) / mi if mi > 0 and term > 0 else 0.0
    loan_to_income    = la / (mi * 12) if mi > 0 else 0.0
    log_income        = math.log1p(max(mi, 0))
    rating_ord        = _rating_ordinal(cs)
    homeowner_flag    = 1 if app.is_homeowner else 0
    emp_status        = str(app.employment_status)
    income_verifiable = 1 if emp_status in ("Employed", "Self-employed") else 0
    high_dti_flag     = 1 if hc_dti > dti_p75 else 0
    emp_grouped       = _employment_group(emp_status)

    return pd.DataFrame([{
        "credit_score_midpoint":  cs,
        "debt_to_income_ratio":   hc_dti,
        "loan_amount_to_income":  loan_to_income,
        "log_monthly_income":     log_income,
        "rating_ordinal":         rating_ord,
        "is_homeowner_flag":      homeowner_flag,
        "income_verifiable_flag": income_verifiable,
        "high_dti_flag":          high_dti_flag,
        "payment_to_income":      hc_dti,
        "num_previous_loans":     num_previous_loans,
        "previous_default_rate":  previous_default_rate,
        "num_bureau_records":     0,
        "num_active_credit":      0,
        "total_overdue_amount":   0.0,
        "max_credit_overdue_days": 0,
        "has_bad_debt":           0,
        "ext_source_1":           cs / 850,
        "ext_source_3":           cs / 850,
        "age_years":              35,
        "gender_male_flag":       0,
        "education_ordinal":      3,
        "cnt_children":           0,
        "cnt_fam_members":        1,
        "is_married_flag":        0,
        "employment_status_grouped": emp_grouped,
    }])


def _resolve_user(identifier: str, db: Session) -> User:
    user = db.query(User).filter(User.email == identifier).first()
    if user:
        return user

    user = db.query(User).filter(User.id == identifier).first()
    if user:
        return user

    raise ValueError(f"User '{identifier}' not found")


def get_credit_score(user_id: str, db: Session) -> dict:
    user = _resolve_user(user_id, db)
    artifact    = _load()
    pipeline    = artifact["pipeline"]
    feat_cols   = artifact["feature_cols"]
    dti_p75     = artifact.get("dti_p75", 2.683)

    # Latest submitted application for this user
    app = db.execute(
        text("""
            SELECT monthly_income, loan_amount, term, employment_status,
                   is_homeowner, credit_score
            FROM loan_applications
            WHERE user_id = :uid
              AND status != 'DRAFT'
            ORDER BY submitted_at DESC
            LIMIT 1
        """),
        {"uid": user.id},
    ).fetchone()

    if app is None:
        raise ValueError(f"No submitted application found for user '{user_id}'")

    # Behavioural features — prior applications for this user
    prev = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'APPROVED')          AS num_approved,
                COUNT(*) FILTER (WHERE status IN ('AUTO_REJECTED',
                                                   'ADMIN_REJECTED',
                                                   'REJECTED'))       AS num_rejected,
                COUNT(*)                                              AS total
            FROM loan_applications
            WHERE user_id = :uid
        """),
        {"uid": user.id},
    ).fetchone()

    total              = int(prev.total) if prev else 0
    num_prev_loans     = int(prev.num_approved) if prev else 0
    prev_default_rate  = (
        round(float(prev.num_rejected) / total, 4) if prev and total > 0 else 0.0
    )

    df = _build_features(app, num_prev_loans, prev_default_rate, dti_p75)
    df[NUMERIC_FEATURES]     = df[NUMERIC_FEATURES].fillna(0.0)
    df[CATEGORICAL_FEATURES] = df[CATEGORICAL_FEATURES].fillna("Other/Unknown")

    X            = df[feat_cols]
    pd_value     = float(pipeline.predict_proba(X)[0, 1])
    credit_score = pd_to_credit_score(pd_value)

    risk_level = (
        "Low"    if pd_value < artifact["thresholds"]["low"]
        else "High" if pd_value > artifact["thresholds"]["high"]
        else "Medium"
    )

    # SHAP via LinearExplainer
    top_factors: list[dict] = []
    try:
        import shap
        X_transformed = pipeline.named_steps["preprocessor"].transform(X)
        lr_model      = pipeline.named_steps["classifier"]
        explainer     = shap.LinearExplainer(
            lr_model, X_transformed, feature_perturbation="interventional"
        )
        shap_values = explainer.shap_values(X_transformed)[0]
        top3 = sorted(zip(feat_cols, shap_values), key=lambda t: abs(t[1]), reverse=True)[:3]
        top_factors = [
            {"feature": f, "direction": "increases_risk" if v > 0 else "decreases_risk",
             "impact": round(float(v), 4)}
            for f, v in top3
        ]
    except Exception:
        pass

    return {
        "member_key":          str(user.id),
        "credit_score":        credit_score,
        "score_band":          score_to_band(credit_score),
        "default_probability": round(pd_value, 4),
        "risk_level":          risk_level,
        "top_factors":         top_factors,
    }
