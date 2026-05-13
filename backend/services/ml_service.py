from decimal import Decimal
from pathlib import Path

import joblib
import pandas as pd

from schemas.application import ApplicationCreate

MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "customer_risk_model.pkl"

CATEGORY_TO_NUMERIC = {
    "Debt Consolidation": 1,
    "Home Improvement": 2,
    "Business": 3,
    "Personal Loan": 4,
    "Auto/Vehicle": 5,
    "Medical/Dental": 6,
    "Education": 7,
    "Other": 8,
}

_artifact = None


def _load():
    global _artifact
    if _artifact is None:
        _artifact = joblib.load(MODEL_PATH)
    return _artifact


def _to_float(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _normalize_dti(value) -> float:
    dti = _to_float(value)
    return dti / 100 if dti > 1 else dti


def _normalize_listing_category(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return CATEGORY_TO_NUMERIC.get(text, CATEGORY_TO_NUMERIC["Other"])


def _risk_level(probability: float, thresholds: dict) -> str:
    if probability < thresholds["low"]:
        return "LOW"
    if probability <= thresholds["high"]:
        return "MEDIUM"
    return "HIGH"


def _recommendation(payload: ApplicationCreate, risk_level: str) -> tuple[float | None, int | None]:
    if risk_level == "HIGH":
        return None, None

    loan_amount = _to_float(payload.loan_amount)
    monthly_income = _to_float(payload.monthly_income)
    term = int(payload.term)
    dti = _normalize_dti(payload.dti)

    available_payment = max(monthly_income * max(0.0, 0.36 - dti), 0.0)
    affordability_cap = available_payment * term
    risk_multiplier = 1.0 if risk_level == "LOW" else 0.8
    recommended_amount = min(loan_amount, affordability_cap) * risk_multiplier

    return round(max(recommended_amount, 0.0), 2), term


def predict(payload: ApplicationCreate) -> dict:
    artifact = _load()
    pipeline = artifact["pipeline"]
    feature_cols = artifact.get("feature_cols")
    thresholds = artifact["thresholds"]

    row = pd.DataFrame([{
        "monthly_income": _to_float(payload.monthly_income),
        "loan_amount": _to_float(payload.loan_amount),
        "term": int(payload.term),
        "dti": _normalize_dti(payload.dti),
        "is_homeowner": int(payload.is_homeowner),
        "listing_category": _normalize_listing_category(payload.listing_category),
        "credit_score": int(payload.credit_score),
        "employment_status": str(payload.employment_status),
    }])

    if feature_cols:
        row = row[feature_cols]

    probability = float(pipeline.predict_proba(row)[0, 1])
    risk_level = _risk_level(probability, thresholds)
    recommended_amount, recommended_term = _recommendation(payload, risk_level)

    return {
        "default_probability": round(probability, 4),
        "risk_level": risk_level,
        "risk_score": round(probability * 100),
        "recommended_amount": recommended_amount,
        "recommended_term": recommended_term,
    }
