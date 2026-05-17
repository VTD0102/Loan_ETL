import joblib
import pandas as pd
from pathlib import Path
from typing import Any

from schemas.application import ApplicationBase
from services.model_feature_builder import build_model_input, fetch_previous_applications
from services.loan_suggestion_service import compute_suggestion

MODEL_PATH = Path(__file__).parents[2] / "machinelearning" / "ml" / "models" / "customer_risk_model_2.pkl"

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


def predict(payload: ApplicationBase, db: Any = None, user_id: Any = None) -> dict:
    """
    Runs ML prediction + binary-search loan suggestion.
    Returns full evaluation dict including suggestion and perfect_fit flag.
    """
    try:
        artifact  = _load()
        _validate_artifact(artifact)
        pipeline  = artifact["pipeline"]
        threshold = artifact["thresholds"]

        previous = fetch_previous_applications(db, user_id)

        # ── Core prediction ────────────────────────────────────────────────
        built = build_model_input(payload, artifact, previous_applications=previous)
        row   = pd.DataFrame([built.features], columns=artifact["feature_cols"])
        prob  = float(pipeline.predict_proba(row)[0, 1])

        # ── Suggestion via binary search ───────────────────────────────────
        suggestion = compute_suggestion(payload, artifact, previous_applications=previous)
        risk_level = suggestion["risk_level"] if prob < threshold["high"] else "High"

        return {
            "default_probability": round(prob, 4),
            "risk_level":          risk_level,
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
