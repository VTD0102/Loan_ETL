import logging
import warnings

import joblib
import pandas as pd
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names",
    category=UserWarning,
    module="sklearn",
)

from schemas.application import ApplicationBase
from services.model_feature_builder import (
    apply_dti_risk_floor,
    build_model_input,
    fetch_previous_applications,
)
from services.loan_suggestion_service import compute_suggestion

MODEL_PATH = Path(__file__).parents[2] / "machinelearning" / "ml" / "models" / "customer_risk_model.pkl"

_artifact = None
logger = logging.getLogger(__name__)


class ModelPredictionError(RuntimeError):
    pass


def _load():
    global _artifact
    if _artifact is None:
        try:
            _artifact = joblib.load(MODEL_PATH)
        except Exception as exc:
            raise ModelPredictionError(f"Cannot load model artifact at {MODEL_PATH}: {exc}") from exc
    return _artifact


def predict(
    payload: ApplicationBase,
    db: Any = None,
    user_id: Any = None,
    bureau_features: dict[str, Any] | None = None,
) -> dict:
    """
    Runs ML prediction + binary-search loan suggestion.
    Returns full evaluation dict including suggestion and perfect_fit flag.

    `bureau_features` is an optional dict of CIC-derived features
    (see cic_service.derive_bureau_features) that override the constant
    artifact defaults for imputed/aliased features.
    """
    try:
        artifact  = _load()
        _validate_artifact(artifact)
        pipeline  = artifact["pipeline"]
        threshold = artifact["thresholds"]

        previous = fetch_previous_applications(db, user_id)

        # ── Core prediction ────────────────────────────────────────────────
        built = build_model_input(
            payload,
            artifact,
            previous_applications=previous,
            bureau_features=bureau_features,
        )
        row   = pd.DataFrame([built.features], columns=artifact["feature_cols"])
        # Xác suất vỡ nợ thô từ LightGBM — chưa qua hiệu chỉnh
        raw_prob = float(pipeline.predict_proba(row)[0, 1])
        # [Lớp 1 — Sàn DTI] Hiệu chỉnh xác suất lên nếu DTI ≥ 40%; kết quả = max(raw, sàn)
        prob = apply_dti_risk_floor(
            raw_prob,
            built.features.get("dti", 0.0),
            low_threshold=float(threshold["low"]),
            high_threshold=float(threshold["high"]),
        )
        dti_value = float(built.features.get("dti", 0.0))
        payment_to_income = float(built.features.get("payment_to_income", 0.0))
        logger.info(
            "ML prediction DTI input user_id=%s model_version=%s dti=%.4f "
            "payment_to_income=%.4f cic_monthly_installment=%.2f high_dti_flag=%s "
            "raw_probability=%.4f adjusted_probability=%.4f",
            user_id,
            artifact.get("model_version"),
            dti_value,
            payment_to_income,
            float(getattr(payload, "cic_monthly_installment", 0) or 0),
            built.features.get("high_dti_flag"),
            raw_prob,
            prob,
        )

        # ── Suggestion via binary search ───────────────────────────────────
        suggestion = compute_suggestion(
            payload,
            artifact,
            previous_applications=previous,
            bureau_features=bureau_features,
        )
        risk_level = suggestion["risk_level"] if prob < threshold["high"] else "High"

        return {
            "default_probability": round(prob, 4),
            "raw_default_probability": round(raw_prob, 4),
            "dti_risk_floor_applied": round(prob, 4) != round(raw_prob, 4),
            "risk_level":          risk_level,
            # Điểm rủi ro hiển thị cho người dùng: thang 0–100, điểm cao = an toàn hơn
            # Ngưỡng từ chối 0.4 tương đương điểm 60 (round((1-0.4)*100))
            "risk_score":          round((1 - prob) * 100),
            "is_perfect_fit":      suggestion["is_perfect_fit"],
            "suggested_amount":    suggestion["suggested_amount"],
            "suggested_term":      suggestion["suggested_term"],
            "model_version":       artifact.get("model_version"),
            "feature_snapshot":    built.features,
            "imputed_features":    built.imputed_features,
        }
    except Exception as e:
        if isinstance(e, ModelPredictionError):
            raise
        raise ModelPredictionError(f"Model prediction failed: {e}") from e


def _validate_artifact(artifact: dict) -> None:
    required = {"pipeline", "feature_cols", "thresholds", "model_version"}
    missing  = sorted(required - set(artifact))
    if missing:
        raise ModelPredictionError(f"Model artifact missing required keys: {', '.join(missing)}")
