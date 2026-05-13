import joblib
import pandas as pd
from pathlib import Path
from typing import Any

from schemas.application import ApplicationCreate
from services.model_feature_builder import build_model_input, fetch_previous_applications

MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "customer_risk_model.pkl"

_artifact = None


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


def predict(payload: ApplicationCreate, db: Any = None, user_id: Any = None) -> dict:
    try:
        artifact  = _load()
        _validate_artifact(artifact)
        pipeline  = artifact["pipeline"]
        threshold = artifact["thresholds"]

        previous = fetch_previous_applications(db, user_id)
        built = build_model_input(payload, artifact, previous_applications=previous)
        row = pd.DataFrame([built.features], columns=artifact["feature_cols"])

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
            "model_version"      : artifact.get("model_version"),
            "feature_snapshot"   : built.features,
            "imputed_features"   : built.imputed_features,
        }
    except Exception as e:
        if isinstance(e, ModelPredictionError):
            raise
        raise ModelPredictionError(f"Model prediction failed: {e}") from e


def _validate_artifact(artifact: dict) -> None:
    required = {"pipeline", "feature_cols", "feature_defaults", "thresholds", "model_version"}
    missing = sorted(required - set(artifact))
    if missing:
        raise ModelPredictionError(f"Model artifact missing required keys: {', '.join(missing)}")
