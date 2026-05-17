"""
model_feature_builder.py — v4 (two-stage pipeline)

Stage 1 (Scorecard LR) features: 22 features — all derived from user input + DB history.
Stage 2 (LightGBM) features: 26 features — Stage 1 features + credit_score_computed + loan params.

Key change from v3:
  - Removed from form: credit_score, dti, listing_category, has_bad_debt
  - Added: loan_purpose → loan_type mapping
  - DTI computed HC-style: (loan_amount / term) / monthly_income
  - high_dti_flag now correctly compared to HC-range dti_p75 (~2.683)
"""
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from schemas.application import ApplicationBase

# loan_purpose → loan_type: 1 = Cash (most loans), 0 = Revolving credit
LOAN_PURPOSE_TO_TYPE: dict[str, int] = {
    "Education": 1,
    "Home":      1,
    "Car":       1,
    "Business":  1,
    "Medical":   1,
    "Personal":  1,
    "Revolving": 0,
}

_EMPLOYMENT_NORMALIZE = {
    "Employed":     "Employed",
    "Self-employed":"Self-employed",
    "Retired":      "Retired",
    "Not employed": "Not employed",
    "Unemployed":   "Not employed",
}


@dataclass(frozen=True)
class FeatureBuildResult:
    features: dict[str, Any]
    imputed_features: list[str]  # always empty in v4 — kept for API compat


def build_stage1_input(
    payload: ApplicationBase,
    stage1_artifact: dict[str, Any],
    *,
    previous_applications: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Build feature dict for Stage 1 (Scorecard LR — 22 features)."""
    dti_p75 = float(stage1_artifact.get("dti_p75", 2.683))
    history = _history_features(
        list(previous_applications or []),
        float(stage1_artifact.get("thresholds", {}).get("high", 0.4)),
    )
    base = _base_features(payload, dti_p75, history)
    feat_cols = stage1_artifact["feature_cols"]
    return {col: base[col] for col in feat_cols}


def build_model_input(
    payload: ApplicationBase,
    artifact: dict[str, Any],
    *,
    credit_score_computed: float | int | None = None,
    previous_applications: Iterable[Any] | None = None,
) -> FeatureBuildResult:
    """Build FeatureBuildResult for Stage 2 (LightGBM — 26 features)."""
    dti_p75 = float(artifact.get("dti_p75", 2.683))
    history = _history_features(
        list(previous_applications or []),
        float(artifact.get("thresholds", {}).get("high", 0.4)),
    )
    base = _base_features(payload, dti_p75, history)

    # credit_score_computed from Stage 1 (fallback to artifact default if not provided)
    if credit_score_computed is not None:
        base["credit_score_computed"] = float(credit_score_computed)
    else:
        base["credit_score_computed"] = float(
            artifact.get("feature_defaults", {}).get("credit_score_computed", 550)
        )

    feat_cols = artifact.get("feature_cols", [])
    ordered = {col: base[col] for col in feat_cols if col in base}
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


# ── Internal helpers ───────────────────────────────────────────────────────────

def _base_features(payload: ApplicationBase, dti_p75: float, history: dict) -> dict[str, Any]:
    """Compute all features shared between Stage 1 and Stage 2."""
    mi   = _number(payload.monthly_income)
    la   = _number(payload.loan_amount)
    term = int(payload.term)

    # HC-style DTI: monthly_payment / monthly_income
    hc_dti = (la / term) / mi if mi > 0 and term > 0 else 0.0

    loan_to_income = la / (mi * 12) if mi > 0 else 0.0
    log_income     = math.log1p(max(mi, 0))
    high_dti       = int(hc_dti > dti_p75)
    loan_type      = LOAN_PURPOSE_TO_TYPE.get(str(payload.loan_purpose or "Personal"), 1)
    emp_raw        = str(payload.employment_status or "Other/Unknown")
    emp_grouped    = _EMPLOYMENT_NORMALIZE.get(emp_raw, "Other/Unknown")
    occ_type       = str(payload.occupation_type or "Unknown")

    return {
        # Stage 2 feature names
        "monthly_income":          mi,
        "loan_amount":             la,
        "term":                    term,
        "dti":                     hc_dti,
        "is_homeowner":            int(bool(payload.is_homeowner)),
        "years_employed":          float(_number(payload.years_employed)),
        "num_previous_loans":      history["num_previous_loans"],
        "previous_default_rate":   history["previous_default_rate"],
        "num_bureau_records":      int(payload.num_bureau_records),
        "num_active_credit":       int(payload.num_active_credit),
        "total_overdue_amount":    float(_number(payload.total_overdue_amount)),
        "max_credit_overdue_days": int(payload.max_credit_overdue_days),
        "income_verifiable_flag":  int(bool(payload.income_verifiable_flag)),
        "high_dti_flag":           high_dti,
        "log_monthly_income":      log_income,
        "loan_amount_to_income":   loan_to_income,
        "age_years":               int(payload.age_years),
        "gender_male_flag":        int(bool(payload.gender_male_flag)),
        "education_ordinal":       int(payload.education_ordinal),
        "cnt_children":            int(payload.cnt_children),
        "cnt_fam_members":         int(payload.cnt_fam_members),
        "is_married_flag":         int(bool(payload.is_married_flag)),
        "loan_type":               loan_type,
        "employment_status":       emp_grouped,
        "occupation_type":         occ_type,
        # Stage 1 aliases (same values, different column names)
        "debt_to_income_ratio":    hc_dti,
        "is_homeowner_flag":       int(bool(payload.is_homeowner)),
        "employment_status_grouped": emp_grouped,
    }


def _history_features(previous_applications: list[Any], high_threshold: float) -> dict[str, Any]:
    if not previous_applications:
        return {"num_previous_loans": 0, "previous_default_rate": 0.0}
    default_like = 0
    for app in previous_applications:
        status    = str(getattr(app, "status", "") or "").upper()
        risk_level = str(getattr(app, "risk_level", "") or "").lower()
        prob      = getattr(app, "default_probability", None)
        prob_val  = _number(prob) if prob is not None else None
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


def _number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)
