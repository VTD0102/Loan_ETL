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
) -> FeatureBuildResult:
    feature_cols = artifact.get("feature_cols")
    if not feature_cols:
        raise ValueError("Model artifact is missing feature_cols")

    defaults = artifact.get("feature_defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}

    dti            = _ratio(payload.dti)
    monthly_income = _number(payload.monthly_income)
    loan_amount    = _number(payload.loan_amount)
    term           = int(payload.term)
    payment_to_income = (
        (loan_amount / term) / monthly_income
        if monthly_income > 0 and term > 0
        else 0.0
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
        "payment_to_income":      payment_to_income,
        # Debt burden
        "current_debt_ratio":     total_overdue / loan_amount if loan_amount > 0 else 0.0,
        "total_debt_to_income":   total_overdue / (monthly_income * 12) if monthly_income > 0 else 0.0,
        # DPD and bureau proxies available from application data
        "max_dpd_24m":            int(payload.max_credit_overdue_days),
        "num_active_credit":      int(payload.num_active_credit),
        "num_bureau_records":     int(payload.num_bureau_records),
        "num_active_credit_bureau": int(payload.num_active_credit),
        "total_overdue_amount":   total_overdue,
        "max_credit_overdue_days": int(payload.max_credit_overdue_days),
        "has_bad_debt":           int(bool(payload.has_bad_debt)),
        "max_overdue_amount":     total_overdue,
        # Previous applications from local DB
        **history,
        # Demographics and categoricals
        "age_years":              int(payload.age_years),
        "years_employed":         float(_number(payload.years_employed)),
        "education_ordinal":      int(payload.education_ordinal),
        "is_homeowner":           int(bool(payload.is_homeowner)),
        "income_verifiable_flag": int(bool(payload.income_verifiable_flag)),
        "is_married_flag":        int(bool(payload.is_married_flag)),
        "income_missing_flag":    0,
        "dti_missing_flag":       0,
        "employment_status":      emp_group,
        "occupation_type":        occupation,
    }

    ordered: dict[str, Any] = {}
    imputed: list[str] = []
    for col in feature_cols:
        if col in values:
            ordered[col] = values[col]
            continue

        ordered[col] = defaults.get(col, _fallback_default(col))
        imputed.append(col)

    return FeatureBuildResult(features=ordered, imputed_features=imputed)


def fetch_previous_applications(db: Any, user_id: Any) -> list[Any]:
    if db is None or user_id is None:
        return []
    from models.application import LoanApplication
    return (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .all()
    )


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
    return number / 100 if number > 1 else number


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)
