import joblib
import pandas as pd
from pathlib import Path

from schemas.application import ApplicationCreate

MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "customer_risk_model.pkl"

_artifact = None


def _load():
    global _artifact
    if _artifact is None:
        _artifact = joblib.load(MODEL_PATH)
    return _artifact


def predict(payload: ApplicationCreate) -> dict:
    try:
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
    except Exception as e:
        # TODO(TEAM ML): LƯU Ý KHI TÍCH HỢP!
        # Khi team ML hoàn thiện file `loan_risk_model.pkl` map chuẩn 8 tính năng từ Backend 
        # (như liệt kê trong file ML_INTEGRATION_CHECKLIST.md), sự cố mismatch sẽ tự mất.
        # Khi luồng Catch Exception này không còn kích hoạt nữa, hãy cấu hình hoàn lại Model Prediction
        # Hiện tại Backend đang bảo vệ Server khỏi bị Crash bằng cách giả định/Mock Logic Random.
        print(f"ML Warning: using Mock values until ML matches Backend schema. ({e})")
        mock_prob = 0.5 if payload.credit_score < 650 else 0.15
        return {
            "default_probability": mock_prob,
            "risk_level"         : "High" if mock_prob > 0.4 else "Low",
            "risk_score"         : round((1 - mock_prob) * 100),
            "recommended_amount" : float(payload.loan_amount) * 0.8,
            "recommended_term"   : payload.term,
        }
