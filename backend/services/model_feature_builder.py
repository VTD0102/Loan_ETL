import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from schemas.application import ApplicationCreate


OPTIONAL_MODEL_INPUTS = [
    "ext_source_1",
    "ext_source_3",
    "num_bureau_records",
    "num_active_credit",
    "total_overdue_amount",
    "max_credit_overdue_days",
    "has_bad_debt",
    "income_verifiable_flag",
    "age_years",
    "gender_male_flag",
    "education_ordinal",
    "cnt_children",
    "cnt_fam_members",
    "is_married_flag",
]

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
    imputed_features: list[str]


def build_model_input(
    payload: ApplicationCreate,
    artifact: dict[str, Any],
    *,
    previous_applications: Iterable[Any] | None = None,
) -> FeatureBuildResult:
    feature_cols = artifact.get("feature_cols")
    defaults = artifact.get("feature_defaults")
    if not feature_cols:
        raise ValueError("Model artifact is missing feature_cols")
    if not isinstance(defaults, dict):
        raise ValueError("Model artifact is missing feature_defaults")

    dti = _ratio(payload.dti)
    monthly_income = _number(payload.monthly_income)
    loan_amount = _number(payload.loan_amount)

    values: dict[str, Any] = {
        "monthly_income": monthly_income,
        "loan_amount": loan_amount,
        "term": int(payload.term),
        "employment_status": payload.employment_status or defaults.get("employment_status", "Other/Unknown"),
        "dti": dti,
        "is_homeowner": int(bool(payload.is_homeowner)),
        "listing_category": _listing_category(payload.listing_category),
        "credit_score": int(payload.credit_score),
        "log_monthly_income": math.log1p(max(monthly_income, 0)),
        "loan_amount_to_income": loan_amount / monthly_income if monthly_income else defaults.get("loan_amount_to_income", 0),
        "rating_ordinal": _rating_ordinal(int(payload.credit_score)),
        "high_dti_flag": int(dti > float(artifact.get("dti_p75", defaults.get("dti", 0.4)))),
    }

    history = _history_features(previous_applications or [], float(artifact.get("thresholds", {}).get("high", 0.4)))
    values.update(history)

    imputed: list[str] = []
    for field in OPTIONAL_MODEL_INPUTS:
        supplied = getattr(payload, field, None)
        if supplied is None:
            values[field] = defaults.get(field)
            imputed.append(field)
        else:
            values[field] = _coerce_model_value(supplied)

    ordered: dict[str, Any] = {}
    for feature in feature_cols:
        if feature in values and values[feature] is not None:
            ordered[feature] = values[feature]
        elif feature in defaults:
            ordered[feature] = defaults[feature]
            imputed.append(feature)
        else:
            raise ValueError(f"No value or default available for model feature '{feature}'")

    return FeatureBuildResult(features=ordered, imputed_features=_unique(imputed))


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


def optional_application_values(payload: ApplicationCreate) -> dict[str, Any]:
    return {
        field: getattr(payload, field)
        for field in OPTIONAL_MODEL_INPUTS
        if getattr(payload, field, None) is not None
    }


def _history_features(previous_applications: Iterable[Any], high_threshold: float) -> dict[str, Any]:
    apps = list(previous_applications)
    if not apps:
        return {"num_previous_loans": 0, "previous_default_rate": 0}

    default_like = 0
    for app in apps:
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
        "num_previous_loans": len(apps),
        "previous_default_rate": default_like / len(apps),
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


def _coerce_model_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
