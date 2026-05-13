"""
Predict Customer Module
Runs risk prediction from raw customer form inputs (8 features).
Uses customer_risk_model.pkl — NOT loan_risk_model.pkl.

Called by FastAPI endpoint: POST /predict
Input : raw form values from customer
Output: probability, risk_level, risk_score, recommendation
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
from datetime import datetime, timezone

from utils.db_connection import get_engine, load_config

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"

# ── Valid input values (for validation before prediction) ────────────────────
VALID_TERMS = [12, 36, 60]
VALID_EMPLOYMENT = [
    "Employed",
    "Self-employed",
    "Retired",
    "Not employed",
    "Other",
]


# ── Business rules ───────────────────────────────────────────────────────────

def get_risk_level(pd_val: float, thresholds: dict) -> str:
    if pd_val < thresholds["low"]:
        return "Low"
    elif pd_val <= thresholds["high"]:
        return "Medium"
    else:
        return "High"


def recommend_loan(pd_val: float, thresholds: dict) -> dict:
    if pd_val < thresholds["low"]:
        return {"recommended_amount": 15000, "recommended_term": 36}
    elif pd_val <= thresholds["high"]:
        return {"recommended_amount": 8000,  "recommended_term": 24}
    else:
        return {"recommended_amount": 3000,  "recommended_term": 12}


def get_auto_decision(pd_val: float, thresholds: dict) -> str:
    """
    Returns application status based on ML result.
    Matches APP_DEVELOPMENT_PLAN.md §5 status flow:
      P(default) > HIGH_THRESHOLD → AUTO_REJECTED
      otherwise                  → PENDING_REVIEW
    """
    if pd_val > thresholds["high"]:
        return "AUTO_REJECTED"
    return "PENDING_REVIEW"


# ── Main prediction function ─────────────────────────────────────────────────

def predict_from_form(
    monthly_income   : float,
    loan_amount      : float,
    term             : int,
    employment_status: str,
    dti              : float,
    is_homeowner     : bool,
    listing_category : int,
    credit_score     : float,
) -> dict:
    """
    Takes raw customer form inputs, runs customer_risk_model.pkl,
    returns full prediction result dict.

    Called by:
      - FastAPI POST /predict endpoint
      - predict_and_save_customer() below (saves to DB)

    Args:
        monthly_income    : stated monthly income (USD)
        loan_amount       : requested loan amount (USD)
        term              : loan term in months (12 / 36 / 60)
        employment_status : one of VALID_EMPLOYMENT
        dti               : debt-to-income ratio (e.g. 0.25)
        is_homeowner      : True / False
        listing_category  : numeric category id (0–20)
        credit_score      : self-reported credit score (300–850)

    Returns:
        dict with keys:
            probability_of_default, risk_level, risk_score_internal,
            auto_decision, recommended_amount, recommended_term,
            assessed_at
    """
    # ── 1. Load model artifact ───────────────────────────
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. "
            "Run: python -m ml.retrain_customer_model"
        )

    artifact   = joblib.load(MODEL_PATH)
    pipeline   = artifact["pipeline"]
    thresholds = artifact.get("thresholds", {"low": 0.2, "high": 0.4})

    # ── 2. Build input DataFrame ─────────────────────────
    # Column order MUST match ALL_FEATURES in retrain_customer_model.py:
    # NUMERIC first, then CATEGORICAL
    input_data = pd.DataFrame([{
        "monthly_income"   : float(monthly_income),
        "loan_amount"      : float(loan_amount),
        "term"             : int(term),
        "dti"              : float(dti),
        "is_homeowner"     : int(is_homeowner),       # bool → 0/1
        "listing_category" : int(listing_category),
        "credit_score"     : float(credit_score),
        "employment_status": str(employment_status),  # categorical last
    }])

    # Reorder to match training column order exactly
    input_data = input_data[[
        "monthly_income", "loan_amount", "term", "dti",
        "is_homeowner", "listing_category", "credit_score",
        "employment_status",
    ]]

    # ── 3. Predict ───────────────────────────────────────
    probs  = pipeline.predict_proba(input_data)
    pd_val = float(probs[0, 1]) if probs.shape[1] > 1 else float(probs[0, 0])

    risk_level          = get_risk_level(pd_val, thresholds)
    risk_score_internal = int((1 - pd_val) * 100)
    recommendation      = recommend_loan(pd_val, thresholds)
    auto_decision       = get_auto_decision(pd_val, thresholds)
    assessed_at         = datetime.now(timezone.utc)

    return {
        "probability_of_default": round(pd_val, 4),
        "risk_level"            : risk_level,
        "risk_score_internal"   : risk_score_internal,
        "auto_decision"         : auto_decision,         # AUTO_REJECTED | PENDING_REVIEW
        "recommended_amount"    : recommendation["recommended_amount"],
        "recommended_term"      : recommendation["recommended_term"],
        "assessed_at"           : assessed_at.isoformat(),
    }


def predict_and_save_customer(application_id: int, form_data: dict) -> dict:
    """
    Runs prediction and saves result back to loan_applications table.
    Called after a customer submits an application.

    Args:
        application_id : row id in loan_applications table
        form_data      : dict with all 8 form fields

    Returns:
        prediction result dict (same as predict_from_form)
    """
    from sqlalchemy import text

    # ── Run prediction ───────────────────────────────────
    result = predict_from_form(**form_data)

    # ── Save to loan_applications ────────────────────────
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE loan_applications SET
                        default_probability = :prob,
                        risk_level          = :risk_level,
                        risk_score          = :risk_score,
                        recommended_amount  = :rec_amount,
                        recommended_term    = :rec_term,
                        status              = :status
                    WHERE id = :app_id
                """),
                {
                    "prob"      : result["probability_of_default"],
                    "risk_level": result["risk_level"],
                    "risk_score": result["risk_score_internal"],
                    "rec_amount": result["recommended_amount"],
                    "rec_term"  : result["recommended_term"],
                    "status"    : result["auto_decision"],
                    "app_id"    : application_id,
                }
            )
        print(f"  Saved prediction for application_id {application_id} "
              f"→ {result['auto_decision']} | P={result['probability_of_default']:.4f}")
    except Exception as e:
        print(f"  ERROR saving prediction to DB: {e}")
        raise

    return result


# ── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing predict_from_form with sample data...\n")

    sample = {
        "monthly_income"   : 5000,
        "loan_amount"      : 15000,
        "term"             : 36,
        "employment_status": "Employed",
        "dti"              : 0.25,
        "is_homeowner"     : True,
        "listing_category" : 1,
        "credit_score"     : 700,
    }

    try:
        result = predict_from_form(**sample)
        print("Input:")
        for k, v in sample.items():
            print(f"  {k}: {v}")
        print("\nPrediction Result:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")