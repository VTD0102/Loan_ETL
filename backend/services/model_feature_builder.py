"""
model_feature_builder.py — v4

Builds the ordered feature vector for the LightGBM stability model.
Deprecated self-reported score fields are not used. Features unavailable at
application time are filled from model artifact defaults and reported via
imputed_features.
"""
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from schemas.application import ApplicationBase

EMPLOYMENT_GROUPS = {
    "Employed": "Employed",
    "Self-employed": "Self-employed",
    "Retired": "Retired",
    "Not employed": "Not employed",
    "Unemployed": "Not employed",
    "Other": "Other/Unknown",
    "Other/Unknown": "Other/Unknown",
}

INCOME_TYPE_BY_EMPLOYMENT = {
    "Employed": "EMPLOYED",
    "Self-employed": "SELFEMPLOYED",
    "Retired": "RETIRED_PENSIONER",
    "Not employed": "OTHER",
    "Other/Unknown": "OTHER",
}

INCOME_TYPES = {
    "EMPLOYED",
    "PRIVATE_SECTOR_EMPLOYEE",
    "SALARIED_GOVT",
    "RETIRED_PENSIONER",
    "SELFEMPLOYED",
    "HANDICAPPED",
    "HANDICAPPED_2",
    "HANDICAPPED_3",
    "OTHER",
}


@dataclass(frozen=True)
class FeatureBuildResult:
    features: dict[str, Any]
    imputed_features: list[str]


def build_model_input(
    payload: ApplicationBase,
    artifact: dict[str, Any],
    *,
    previous_applications: Iterable[Any] | None = None,
    bureau_features: dict[str, Any] | None = None,
) -> FeatureBuildResult:
    feature_cols = artifact.get("feature_cols")
    if not feature_cols:
        raise ValueError("Model artifact is missing feature_cols")

    defaults = artifact.get("feature_defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}

    monthly_income = _number(payload.monthly_income)
    loan_amount    = _number(payload.loan_amount)
    term           = payload.term
    cic_monthly    = _number(getattr(payload, "cic_monthly_installment", None))

    # DTI includes existing CIC debt so the model sees total repayment burden.
    # The training contract has both dti and payment_to_income, and in training
    # they were the same value; keep them synchronized at inference time.
    dti = compute_combined_dti(
        monthly_income,
        loan_amount,
        term,
        cic_monthly,
    )
    total_overdue = _number(payload.total_overdue_amount)
    emp_group     = _employment_group(payload.employment_status)
    occupation    = _income_type(payload.occupation_type, emp_group)

    # ── History from DB ────────────────────────────────────────────────────
    history = _history_features(
        list(previous_applications or []),
        float(artifact.get("thresholds", {}).get("high", 0.4)),
    )

    values: dict[str, Any] = {
        # Income & loan
        "monthly_income":         monthly_income,
        "loan_amount":            loan_amount,
        "term":                   term,
        "dti":                    dti,
        "loan_amount_to_income":  loan_amount / (monthly_income * 12) if monthly_income else 0.0,
        "log_monthly_income":     math.log1p(max(monthly_income, 0)),
        "high_dti_flag":          int(dti > float(artifact.get("dti_p75", 0.4))),
        "payment_to_income":      dti,
        # Debt burden
        "current_debt_ratio":     total_overdue / loan_amount if loan_amount > 0 else 0.0,
        "total_debt_to_income":   total_overdue / (monthly_income * 12) if monthly_income > 0 else 0.0,
        # DPD and bureau proxies available from application data
        "max_dpd_24m":            (payload.max_credit_overdue_days or 0),
        "num_active_credit":      (payload.num_active_credit or 0),
        "num_bureau_records":     (payload.num_bureau_records or 0),
        "num_active_credit_bureau": (payload.num_active_credit or 0),
        "total_overdue_amount":   total_overdue,
        "max_credit_overdue_days": (payload.max_credit_overdue_days or 0),
        "has_bad_debt":           int(payload.has_bad_debt or False),
        "max_overdue_amount":     total_overdue,
        # Previous applications from local DB
        **history,
        # Demographics and categoricals
        "age_years":              payload.age_years,
        "years_employed":         _number(payload.years_employed),
        "education_ordinal":      payload.education_ordinal,
        "is_homeowner":           int(payload.is_homeowner),
        "income_verifiable_flag": int(payload.income_verifiable_flag or False),
        "is_married_flag":        int(payload.is_married_flag),
        "income_missing_flag":    0,
        "dti_missing_flag":       0,
        "employment_status":      emp_group,
        "occupation_type":        occupation,
    }

    # Bureau features derived from CIC mock (cic_service.derive_bureau_features).
    # Overrides constant aliases (max_dpd_24m, max_overdue_amount) and fills
    # previously-imputed features (avg_dpd_recent, num_installs_dpd10, num_cb_queries).
    # Keys not present here continue to fall through to artifact defaults.
    if bureau_features:
        for col, val in bureau_features.items():
            if val is not None:
                values[col] = val

    ordered: dict[str, Any] = {}
    imputed: list[str] = []
    for col in feature_cols:
        if col in values:
            ordered[col] = values[col]
            continue

        ordered[col] = defaults.get(col, _fallback_default(col))
        imputed.append(col)

    return FeatureBuildResult(features=ordered, imputed_features=imputed)


def compute_combined_dti(
    monthly_income: Any,
    loan_amount: Any,
    term: Any,
    existing_monthly_debt: Any = 0.0,
) -> float:
    income = _number(monthly_income)
    amount = _number(loan_amount)
    term_value = int(term) if term else 0
    existing_debt = max(_number(existing_monthly_debt), 0.0)
    requested_installment = amount / term_value if term_value > 0 else 0.0
    return (requested_installment + existing_debt) / income if income > 0 else 0.0


def apply_dti_risk_floor(
    probability: float,
    dti: Any,
    *,
    low_threshold: float,
    high_threshold: float,
) -> float:
    """
    Apply a DTI-based probability floor aligned with banking standards.

    Real-world DTI guidelines (personal/consumer loans):
      - ≤ 40%: acceptable, no adjustment needed
      - 40–55%: caution zone, gradual floor from low to high threshold
      - 55–70%: high strain, floor at/above high threshold
      - > 70%: extremely risky, hard floor near ceiling

    This replaces the previous aggressive cutoff at 43% which was too strict
    and caused counterintuitive rejections (e.g. 36-month term rejected but
    24-month accepted because the model's raw prediction for longer terms
    was already borderline, and the tight floor pushed it over).
    """
    dti_value = _ratio(dti)

    # ── No adjustment below 40% DTI ──
    if dti_value <= 0.40:
        return probability

    # ── Caution zone: 40% – 55% DTI ──
    # Gradually raise floor from low_threshold to high_threshold
    if dti_value <= 0.55:
        progress = (dti_value - 0.40) / 0.15
        floor = low_threshold + (high_threshold - low_threshold) * progress
    # ── High strain: 55% – 70% DTI ──
    # Floor continues rising above high_threshold
    elif dti_value <= 0.70:
        progress = (dti_value - 0.55) / 0.15
        floor = high_threshold + 0.05 * progress
    # ── Extreme: > 70% DTI ──
    # Hard floor well above auto-reject
    else:
        progress = min((dti_value - 0.70) / 0.30, 1.0)
        floor = high_threshold + 0.05 + 0.20 * progress

    return min(max(probability, floor), 0.95)


def infer_existing_monthly_debt(
    monthly_income: Any,
    loan_amount: Any,
    term: Any,
    combined_dti: Any,
) -> float:
    income = _number(monthly_income)
    amount = _number(loan_amount)
    term_value = int(term) if term else 0
    dti_value = _ratio(combined_dti)
    requested_installment = amount / term_value if term_value > 0 else 0.0
    return max(dti_value * income - requested_installment, 0.0)


def fetch_previous_applications(db: Any, user_id: Any) -> list[Any]:
    if db is None or user_id is None:
        return []
    from models.application import LoanApplication
    import datetime
    all_apps = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .all()
    )
    if not all_apps:
        return []
    # Exclude applications submitted in the last 30 minutes to prevent counting
    # the current session's rejection as a historical default.
    if all_apps[0].submitted_at.tzinfo:
        now = datetime.datetime.now(all_apps[0].submitted_at.tzinfo)
    else:
        now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(minutes=30)
    return [app for app in all_apps if app.submitted_at < cutoff]


def _history_features(previous_applications: list[Any], high_threshold: float) -> dict[str, Any]:
    if not previous_applications:
        return {"num_previous_loans": 0, "previous_default_rate": 0.0}

    default_like = 0
    for app in previous_applications:
        status = str(getattr(app, "status", "") or "").upper()
        risk_level = str(getattr(app, "risk_level", "") or "").lower()
        prob = getattr(app, "default_probability", None)
        prob_val = _number(prob) if prob is not None else None
        if status in {"AUTO_REJECTED", "ADMIN_REJECTED", "REJECTED"}:
            default_like += 1
        elif risk_level == "high":
            default_like += 1
        elif prob_val is not None and prob_val > high_threshold:
            default_like += 1

    return {
        "num_previous_loans":    len(previous_applications),
        "previous_default_rate": default_like / len(previous_applications),
    }


def _employment_group(value: Any) -> str:
    raw = str(value or "Other/Unknown").strip()
    return EMPLOYMENT_GROUPS.get(raw, "Other/Unknown")


def _income_type(value: Any, employment_group: str) -> str:
    raw = str(value or "").strip()
    if raw in INCOME_TYPES:
        return raw
    return INCOME_TYPE_BY_EMPLOYMENT.get(employment_group, "OTHER")


def _fallback_default(feature: str) -> Any:
    if feature in {"employment_status", "occupation_type"}:
        return "Other/Unknown" if feature == "employment_status" else "OTHER"
    return 0


def _ratio(value: Any) -> float:
    number = _number(value)
    return number / 100 if number > 5 else number


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)
