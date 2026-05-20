"""
Credit score service v2 — computes a FICO-style score (300–850) for a user's
latest submitted loan application using the LR scorecard model trained on
gold.hc_features_v2.

KEY CHANGE vs v1:
  - NO credit_score_midpoint (was gameable — user self-reported)
  - NO rating_ordinal (was derived from credit_score → multicollinear)
  - All features are verifiable behavioral/system data
  - credit_score from app is stored but NOT used as model input

Feature mapping from Supabase application data → v2 scorecard features:
- debt_to_income_ratio   : stored combined DTI, fallback to (loan_amount / term) / monthly_income
- payment_to_income      : same combined DTI value
- loan_amount_to_income  : loan_amount / (monthly_income * 12)
- log_monthly_income     : ln(1 + monthly_income)
- current_debt_ratio     : total_overdue_amount / loan_amount (proxy)
- total_debt_to_income   : total_overdue_amount / (monthly_income * 12) (proxy)
- is_homeowner_flag      : 1/0 from is_homeowner
- income_verifiable_flag : 1 if employed/self-employed, else 0
- high_dti_flag          : 1 if combined DTI > dti_p75 from training data
- num_previous_loans     : prior APPROVED applications for this user
- previous_default_rate  : fraction of prior applications that were rejected
- employment_status_grouped: normalised employment category
- DPD, bureau, demographic fields: from application, defaults for legacy rows.
"""
import math
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.scoring import pd_to_credit_score, score_to_band
from models.application import LoanApplication
from models.user import User

SCORECARD_PATH = Path(__file__).parents[2] / "machinelearning" / "ml" / "models" / "scorecard_model.pkl"

# ═══════════════════════════════════════════════════════════════════════════════
# v2 FEATURE LISTS — NO credit_score_midpoint, NO rating_ordinal
# ═══════════════════════════════════════════════════════════════════════════════
NUMERIC_FEATURES = [
    # Income & loan
    "debt_to_income_ratio",
    "loan_amount_to_income",
    "log_monthly_income",
    "payment_to_income",
    "high_dti_flag",
    # Debt burden
    "current_debt_ratio",
    "total_debt_to_income",
    # DPD features
    "max_dpd_24m",
    "avg_dpd_recent",
    "num_installs_dpd10",
    # Bureau aggregates
    "num_bureau_records",
    "num_active_credit",
    "total_overdue_amount",
    "max_credit_overdue_days",
    "has_bad_debt",
    "total_prolongations",
    # Previous application
    "num_previous_loans",
    "previous_default_rate",
    # CB queries
    "cb_queries_30d",
    "num_cb_queries",
    # Demographics
    "is_homeowner_flag",
    "income_verifiable_flag",
    "years_employed",
    "age_years",
    "education_ordinal",
    "is_married_flag",
    # Missing indicators
    "income_missing_flag",
    "dti_missing_flag",
]
CATEGORICAL_FEATURES = ["employment_status_grouped", "occupation_type"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

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


def _employment_group(status: str) -> str:
    return _EMPLOYMENT_GROUP.get(status, "Other/Unknown")


def _value(obj, name: str, default):
    value = getattr(obj, name, default)
    return default if value is None else value


def _number(obj, name: str, default=0.0) -> float:
    return float(_value(obj, name, default))


def _ratio(value, default=0.0) -> float:
    if value is None:
        return default
    number = float(value)
    return number / 100 if number > 5 else number


def _int(obj, name: str, default=0) -> int:
    return int(_value(obj, name, default))


def _flag(obj, name: str, default=False) -> int:
    return int(bool(_value(obj, name, default)))


def _build_features(app, num_previous_loans: int, previous_default_rate: float,
                    dti_p75: float) -> pd.DataFrame:
    """Build feature vector from application data — v2, no credit_score input."""
    mi   = float(app.monthly_income)
    la   = float(app.loan_amount)
    term = int(app.term)

    # Derived features
    requested_dti     = (la / term) / mi if mi > 0 and term > 0 else 0.0
    hc_dti            = _ratio(getattr(app, "dti", None), requested_dti)
    loan_to_income    = la / (mi * 12) if mi > 0 else 0.0
    log_income        = math.log1p(max(mi, 0))
    homeowner_flag    = 1 if app.is_homeowner else 0
    emp_status        = str(app.employment_status)
    income_verifiable = _flag(
        app,
        "income_verifiable_flag",
        emp_status in ("Employed", "Self-employed"),
    )
    high_dti_flag     = 1 if hc_dti > dti_p75 else 0
    emp_grouped       = _employment_group(emp_status)
    occupation_type   = str(_value(app, "occupation_type", "OTHER") or "OTHER")

    # Debt burden (use total_overdue as proxy for current_debt in inference)
    total_overdue     = _number(app, "total_overdue_amount", 0.0)
    current_debt_r    = total_overdue / la if la > 0 else 0.0
    total_debt_income = total_overdue / (mi * 12) if mi > 0 else 0.0

    return pd.DataFrame([{
        # Income & loan
        "debt_to_income_ratio":     hc_dti,
        "loan_amount_to_income":    loan_to_income,
        "log_monthly_income":       log_income,
        "payment_to_income":        hc_dti,
        "high_dti_flag":            high_dti_flag,
        # Debt burden
        "current_debt_ratio":       current_debt_r,
        "total_debt_to_income":     total_debt_income,
        # DPD features (from app or defaults)
        "max_dpd_24m":              _int(app, "max_credit_overdue_days", 0),
        "avg_dpd_recent":           0.0,  # not available at inference
        "num_installs_dpd10":       0,    # not available at inference
        # Bureau aggregates
        "num_bureau_records":       _int(app, "num_bureau_records", 0),
        "num_active_credit":        _int(app, "num_active_credit", 0),
        "total_overdue_amount":     total_overdue,
        "max_credit_overdue_days":  _int(app, "max_credit_overdue_days", 0),
        "has_bad_debt":             _flag(app, "has_bad_debt", False),
        "total_prolongations":      0,    # not available at inference
        # Previous application
        "num_previous_loans":       num_previous_loans,
        "previous_default_rate":    previous_default_rate,
        # CB queries (not available at inference — use 0)
        "cb_queries_30d":           0,
        "num_cb_queries":           0,
        # Demographics
        "is_homeowner_flag":        homeowner_flag,
        "income_verifiable_flag":   income_verifiable,
        "years_employed":           _number(app, "years_employed", 0.0),
        "age_years":                _int(app, "age_years", 35),
        "education_ordinal":        _int(app, "education_ordinal", 2),
        "is_married_flag":          _flag(app, "is_married_flag", False),
        # Missing indicators
        "income_missing_flag":      0,  # if we have it in app, it's not missing
        "dti_missing_flag":         0,
        # Categorical
        "employment_status_grouped": emp_grouped,
        "occupation_type":          occupation_type,
    }])


def _resolve_user(identifier: str, db: Session) -> User:
    user = db.query(User).filter(User.email == identifier).first()
    if user:
        return user

    user = db.query(User).filter(User.id == identifier).first()
    if user:
        return user

    raise ValueError(f"User '{identifier}' not found")


def _previous_application_stats(app, db: Session) -> tuple[int, float]:
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
              AND id != :app_id
        """),
        {"uid": app.user_id, "app_id": app.id},
    ).fetchone()

    total = int(prev.total) if prev else 0
    num_prev_loans = int(prev.num_approved) if prev else 0
    prev_default_rate = (
        round(float(prev.num_rejected) / total, 4) if prev and total > 0 else 0.0
    )
    return num_prev_loans, prev_default_rate


def _score_application(app, db: Session) -> dict:
    artifact = _load()
    pipeline = artifact["pipeline"]
    feat_cols = artifact["feature_cols"]
    dti_p75 = artifact.get("dti_p75", 0.5)

    num_prev_loans, prev_default_rate = _previous_application_stats(app, db)

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
        "member_key":          str(app.user_id),
        "credit_score":        credit_score,
        "score_band":          score_to_band(credit_score),
        "default_probability": round(pd_value, 4),
        "risk_level":          risk_level,
        "top_factors":         top_factors,
    }


def get_credit_score(user_id: str, db: Session) -> dict:
    user = _resolve_user(user_id, db)
    app = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user.id)
        .filter(LoanApplication.status != "DRAFT")
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )
    if app is None:
        raise ValueError(f"No submitted application found for user '{user_id}'")
    return _score_application(app, db)


def get_credit_score_for_application(
    app_id: str,
    db: Session,
    *,
    user_id: str | None = None,
) -> dict:
    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if app is None:
        raise ValueError(f"Application '{app_id}' not found")
    if user_id is not None:
        user = _resolve_user(user_id, db)
        if str(app.user_id) != str(user.id):
            raise PermissionError("Không có quyền truy cập điểm tín dụng của đơn này")
    return _score_application(app, db)
