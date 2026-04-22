import joblib
import pandas as pd
from pathlib import Path

from backend.models.application import ApplicationCreate

MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "customer_risk_model.pkl"

_artifact = None


def _load():
    global _artifact
    if _artifact is None:
        _artifact = joblib.load(MODEL_PATH)
    return _artifact


def predict(payload: ApplicationCreate) -> dict:
    artifact  = _load()
    pipeline  = artifact["pipeline"]
    threshold = artifact["thresholds"]

    row = pd.DataFrame([{
        "monthly_income"  : payload.monthly_income,
        "loan_amount"     : payload.loan_amount,
        "term"            : payload.term,
        "employment_status": payload.employment_status,
        "dti"             : payload.dti,
        "is_homeowner"    : int(payload.is_homeowner),
        "listing_category": payload.listing_category,
        "credit_score"    : payload.credit_score,
    }])

    prob = float(pipeline.predict_proba(row)[0, 1])

    if prob < threshold["low"]:
        risk_level          = "Low"
        recommended_amount  = 15_000
        recommended_term    = 36
    elif prob <= threshold["high"]:
        risk_level          = "Medium"
        recommended_amount  = 8_000
        recommended_term    = 24
    else:
        risk_level          = "High"
        recommended_amount  = 3_000
        recommended_term    = 12

    return {
        "default_probability": round(prob, 4),
        "risk_level"         : risk_level,
        "risk_score"         : round((1 - prob) * 100),
        "recommended_amount" : recommended_amount,
        "recommended_term"   : recommended_term,
    }
