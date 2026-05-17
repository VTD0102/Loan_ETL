"""
Credit score service — v4 (two-stage pipeline)

Computes a FICO-style score (300–850) for a user's latest submitted loan application
using Stage 1 (Scorecard LR) trained on gold.hc_features_v1.

v4 changes:
  - Removed: credit_score_midpoint (self-reported, now Stage 1 output)
  - Removed: rating_ordinal (derived from credit_score)
  - Removed: payment_to_income (duplicate of debt_to_income_ratio)
  - Removed: has_bad_debt (near-zero variance)
  - Added: loan_type (from loan_purpose stored in DB)
  - income_verifiable_flag: from DB (user checkbox, not derived from employment)
  - DTI: computed HC-style from loan_amount, term, monthly_income (not stored form DTI)
"""
import math
import joblib
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.scoring import pd_to_credit_score, score_to_band
from models.user import User

SCORECARD_PATH = Path(__file__).parents[2] / "machinelearning" / "ml" / "models" / "scorecard_model.pkl"

# Stage 1 feature names (must match train_scorecard.py ALL_FEATURES exactly)
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
CATEGORICAL_FEATURES = ["employment_status_grouped", "occupation_type"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

_LOAN_PURPOSE_TO_TYPE = {
    "Education": 1, "Home": 1, "Car": 1, "Business": 1,
    "Medical": 1, "Personal": 1, "Revolving": 0,
}

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


def _number(obj, name: str, default=0.0) -> float:
    value = getattr(obj, name, default)
    return float(value) if value is not None else float(default)


def _int(obj, name: str, default=0) -> int:
    value = getattr(obj, name, default)
    return int(value) if value is not None else int(default)


def _flag(obj, name: str, default=False) -> int:
    value = getattr(obj, name, default)
    return int(bool(value))


def _value(obj, name: str, default):
    v = getattr(obj, name, default)
    return default if v is None else v


def _build_features(app, num_previous_loans: int, previous_default_rate: float,
                    dti_p75: float) -> pd.DataFrame:
    mi   = float(app.monthly_income)
    la   = float(app.loan_amount)
    term = int(app.term)

    hc_dti         = (la / term) / mi if mi > 0 and term > 0 else 0.0
    loan_to_income  = la / (mi * 12) if mi > 0 else 0.0
    log_income      = math.log1p(max(mi, 0))
    homeowner_flag  = 1 if app.is_homeowner else 0
    emp_status      = str(app.employment_status)
    emp_grouped     = _EMPLOYMENT_GROUP.get(emp_status, "Other/Unknown")
    occupation_type = str(_value(app, "occupation_type", "Unknown") or "Unknown")

    # income_verifiable_flag: from DB (user checkbox in v4)
    income_verifiable = _flag(app, "income_verifiable_flag", False)
    high_dti_flag     = 1 if hc_dti > dti_p75 else 0

    # loan_type: from loan_purpose stored in DB (nullable for legacy rows)
    loan_purpose = str(_value(app, "loan_purpose", "Personal") or "Personal")
    loan_type    = _LOAN_PURPOSE_TO_TYPE.get(loan_purpose, 1)

    return pd.DataFrame([{
        "debt_to_income_ratio":    hc_dti,
        "loan_amount_to_income":   loan_to_income,
        "log_monthly_income":      log_income,
        "is_homeowner_flag":       homeowner_flag,
        "income_verifiable_flag":  income_verifiable,
        "high_dti_flag":           high_dti_flag,
        "num_previous_loans":      num_previous_loans,
        "previous_default_rate":   previous_default_rate,
        "num_bureau_records":      _int(app, "num_bureau_records", 0),
        "num_active_credit":       _int(app, "num_active_credit", 0),
        "total_overdue_amount":    _number(app, "total_overdue_amount", 0.0),
        "max_credit_overdue_days": _int(app, "max_credit_overdue_days", 0),
        "years_employed":          _number(app, "years_employed", 0.0),
        "age_years":               _int(app, "age_years", 35),
        "gender_male_flag":        _flag(app, "gender_male_flag", False),
        "education_ordinal":       _int(app, "education_ordinal", 3),
        "cnt_children":            _int(app, "cnt_children", 0),
        "cnt_fam_members":         _int(app, "cnt_fam_members", 1),
        "is_married_flag":         _flag(app, "is_married_flag", False),
        "loan_type":               loan_type,
        "employment_status_grouped": emp_grouped,
        "occupation_type":         occupation_type,
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
    user     = _resolve_user(user_id, db)
    artifact = _load()
    pipeline  = artifact["pipeline"]
    feat_cols = artifact["feature_cols"]
    dti_p75   = artifact.get("dti_p75", 2.683)

    # Latest submitted application for this user
    app = db.execute(
        text("""
            SELECT monthly_income, loan_amount, term, employment_status,
                   is_homeowner, loan_purpose,
                   occupation_type, years_employed,
                   num_bureau_records, num_active_credit,
                   total_overdue_amount, max_credit_overdue_days,
                   income_verifiable_flag,
                   age_years, gender_male_flag, education_ordinal,
                   cnt_children, cnt_fam_members, is_married_flag
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

    # Behavioural features
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

    total             = int(prev.total) if prev else 0
    num_prev_loans    = int(prev.num_approved) if prev else 0
    prev_default_rate = (
        round(float(prev.num_rejected) / total, 4) if prev and total > 0 else 0.0
    )

    df = _build_features(app, num_prev_loans, prev_default_rate, dti_p75)
    df[NUMERIC_FEATURES]     = df[NUMERIC_FEATURES].fillna(0.0)
    df[CATEGORICAL_FEATURES] = df[CATEGORICAL_FEATURES].fillna("Other/Unknown")

    X        = df[feat_cols]
    pd_value = float(pipeline.predict_proba(X)[0, 1])
    credit_score = pd_to_credit_score(pd_value)

    risk_level = (
        "Low"    if pd_value < artifact["thresholds"]["low"]
        else "High" if pd_value > artifact["thresholds"]["high"]
        else "Medium"
    )

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
