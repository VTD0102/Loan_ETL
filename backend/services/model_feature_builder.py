"""
model_feature_builder.py — v3

Builds the ordered feature vector for LightGBM inference.
All 22 user-input features are now required (no median imputation).
Auto-computes 4 derived features and pulls 2 from DB history.
"""
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from schemas.application import ApplicationBase

CATEGORY_ORDINALS = {
    "debt consolidation": 1,
    "home improvement": 2,
    "business": 3,
    "personal loan": 4,
    "auto/vehicle": 5,
    "medical/dental": 6,
    "education": 7,
    "other": 8,
}


@dataclass(frozen=True)
class FeatureBuildResult:
    features: dict[str, Any]
    imputed_features: list[str]  # always empty in v3 — kept for API compat


def build_model_input(
    payload: ApplicationBase,
    artifact: dict[str, Any],
    *,
    previous_applications: Iterable[Any] | None = None,
) -> FeatureBuildResult:
    feature_cols = artifact.get("feature_cols")
    if not feature_cols:
        raise ValueError("Model artifact is missing feature_cols")

    dti = _ratio(payload.dti)
    monthly_income = _number(payload.monthly_income)
    loan_amount = _number(payload.loan_amount)

    # ── History from DB ────────────────────────────────────────────────────
    history = _history_features(
        list(previous_applications or []),
        float(artifact.get("thresholds", {}).get("high", 0.4)),
    )

    values: dict[str, Any] = {
        # Core 8
        "monthly_income":         monthly_income,
        "loan_amount":            loan_amount,
        "term":                   int(payload.term),
        "employment_status":      str(payload.employment_status or "Other/Unknown"),
        "dti":                    dti,
        "is_homeowner":           int(bool(payload.is_homeowner)),
        "listing_category":       _listing_category(payload.listing_category),
        "credit_score":           int(payload.credit_score),
        # v3 new
        "occupation_type":        str(payload.occupation_type or "Unknown"),
        "years_employed":         float(_number(payload.years_employed)),
        # Bureau (now required)
        "num_bureau_records":     int(payload.num_bureau_records),
        "num_active_credit":      int(payload.num_active_credit),
        "total_overdue_amount":   float(_number(payload.total_overdue_amount)),
        "max_credit_overdue_days": int(payload.max_credit_overdue_days),
        "has_bad_debt":           int(bool(payload.has_bad_debt)),
        "income_verifiable_flag": int(bool(payload.income_verifiable_flag)),
        # Demographics (now required)
        "age_years":              int(payload.age_years),
        "gender_male_flag":       int(bool(payload.gender_male_flag)),
        "education_ordinal":      int(payload.education_ordinal),
        "cnt_children":           int(payload.cnt_children),
        "cnt_fam_members":        int(payload.cnt_fam_members),
        "is_married_flag":        int(bool(payload.is_married_flag)),
        # Auto-computed
        "log_monthly_income":     math.log1p(max(monthly_income, 0)),
        "loan_amount_to_income":  loan_amount / monthly_income if monthly_income else 0.0,
        "rating_ordinal":         _rating_ordinal(int(payload.credit_score)),
        "high_dti_flag":          int(dti > float(artifact.get("dti_p75", 0.4))),
        # DB history
        **history,
    }

    ordered: dict[str, Any] = {col: values[col] for col in feature_cols if col in values}

    return FeatureBuildResult(features=ordered, imputed_features=[])


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


def _listing_category(value: Any) -> int:
    if isinstance(value, (int, float, Decimal)):
        return int(value)
    raw = str(value or "Other").strip().lower()
    return CATEGORY_ORDINALS.get(raw, CATEGORY_ORDINALS["other"])


def _rating_ordinal(credit_score: int) -> int:
    if credit_score >= 760:
        return 7
    if credit_score >= 700:
        return 6
    if credit_score >= 660:
        return 5
    if credit_score >= 620:
        return 4
    if credit_score >= 580:
        return 3
    if credit_score >= 540:
        return 2
    return 1


def _ratio(value: Any) -> float:
    number = _number(value)
    return number / 100 if number > 1 else number


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)
