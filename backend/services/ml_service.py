"""
ml_service.py — v4 (two-stage pipeline)

Stage 1: Scorecard LR (scorecard_model.pkl) → credit_score_computed (300–850)
Stage 2: LightGBM (customer_risk_model.pkl) → P(default) → risk classification

Inference flow:
  1. Build Stage 1 features from payload
  2. Run Stage 1 → P1(default) → credit_score_computed via FICO PDO formula
  3. Build Stage 2 features = payload features + credit_score_computed
  4. Run Stage 2 → prob → risk_level
"""
import math
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any

from schemas.application import ApplicationBase
from services.model_feature_builder import (
    build_stage1_input,
    build_model_input,
    fetch_previous_applications,
)
from services.loan_suggestion_service import compute_suggestion

_ML_DIR = Path(__file__).parents[2] / "machinelearning" / "ml" / "models"
SCORECARD_PATH = _ML_DIR / "scorecard_model.pkl"
MODEL_PATH     = _ML_DIR / "customer_risk_model.pkl"

_stage1_artifact: dict | None = None
_stage2_artifact: dict | None = None


class ModelPredictionError(RuntimeError):
    pass


def _load_stage1() -> dict:
    global _stage1_artifact
    if _stage1_artifact is None:
        try:
            _stage1_artifact = joblib.load(SCORECARD_PATH)
        except Exception as exc:
            raise ModelPredictionError(
                f"Cannot load Stage 1 scorecard at {SCORECARD_PATH}: {exc}"
            ) from exc
    return _stage1_artifact


def _load() -> dict:
    """Load Stage 2 LightGBM artifact (kept for backward compat with application_service)."""
    global _stage2_artifact
    if _stage2_artifact is None:
        try:
            _stage2_artifact = joblib.load(MODEL_PATH)
        except Exception as exc:
            raise ModelPredictionError(
                f"Cannot load Stage 2 model at {MODEL_PATH}: {exc}"
            ) from exc
    return _stage2_artifact


def _load_both() -> tuple[dict, dict]:
    return _load_stage1(), _load()


def _prob_to_score(prob: float, fico_params: dict) -> int:
    """Convert P(default) → FICO-style score using scorecard's PDO params."""
    factor     = float(fico_params.get("factor", 28.854))
    base_score = float(fico_params.get("base_score", 600))
    base_logit = float(fico_params.get("base_logit", -3.912))
    score_min  = int(fico_params.get("score_min", 300))
    score_max  = int(fico_params.get("score_max", 850))

    p = max(min(float(prob), 1 - 1e-9), 1e-9)
    logit = math.log(p / (1 - p))
    score = base_score - factor * (logit - base_logit)
    return int(max(score_min, min(score_max, round(score))))


def _run_stage1(payload: ApplicationBase, stage1: dict, previous: list) -> tuple[int, float]:
    """Run Stage 1 → (credit_score_computed, stage1_prob)."""
    features = build_stage1_input(payload, stage1, previous_applications=previous)
    feat_cols = stage1["feature_cols"]
    row = pd.DataFrame([features], columns=feat_cols)
    stage1_prob = float(stage1["pipeline"].predict_proba(row)[0, 1])
    credit_score_computed = _prob_to_score(stage1_prob, stage1.get("fico_params", {}))
    return credit_score_computed, stage1_prob


def predict(payload: ApplicationBase, db: Any = None, user_id: Any = None) -> dict:
    """
    Runs two-stage ML prediction + binary-search loan suggestion.
    Returns full evaluation dict including suggestion, credit_score_computed, and perfect_fit flag.
    """
    try:
        stage1 = _load_stage1()
        stage2 = _load()
        _validate_artifact(stage2)

        previous = fetch_previous_applications(db, user_id)

        # ── Stage 1: compute credit_score_computed ─────────────────────────
        credit_score_computed, stage1_prob = _run_stage1(payload, stage1, previous)

        # ── Stage 2: predict risk ──────────────────────────────────────────
        built = build_model_input(
            payload, stage2,
            credit_score_computed=credit_score_computed,
            previous_applications=previous,
        )
        row  = pd.DataFrame([built.features], columns=stage2["feature_cols"])
        prob = float(stage2["pipeline"].predict_proba(row)[0, 1])

        threshold = stage2["thresholds"]

        # ── Loan suggestion via binary search ──────────────────────────────
        suggestion = compute_suggestion(
            payload, stage1, stage2, previous_applications=previous
        )
        risk_level = suggestion["risk_level"] if prob < threshold["high"] else "High"

        # HC-style DTI for DB storage
        mi   = float(payload.monthly_income) if payload.monthly_income else 0.0
        la   = float(payload.loan_amount) if payload.loan_amount else 0.0
        term = int(payload.term) if payload.term else 1
        hc_dti = (la / term) / mi if mi > 0 and term > 0 else 0.0

        return {
            "default_probability":  round(prob, 4),
            "risk_level":           risk_level,
            "risk_score":           round((1 - prob) * 100),
            "credit_score_computed": credit_score_computed,
            "hc_dti":               round(hc_dti, 6),
            "is_perfect_fit":       suggestion["is_perfect_fit"],
            "suggested_amount":     suggestion["suggested_amount"],
            "suggested_term":       suggestion["suggested_term"],
            "model_version":        f"{stage1.get('model_version', 'scorecard_v4')}/{stage2.get('model_version', 'lgbm_v4')}",
            "feature_snapshot":     built.features,
            "imputed_features":     built.imputed_features,
        }
    except ModelPredictionError:
        raise
    except Exception as e:
        raise ModelPredictionError(f"Model prediction failed: {e}") from e


def _validate_artifact(artifact: dict) -> None:
    required = {"pipeline", "feature_cols", "thresholds", "model_version"}
    missing  = sorted(required - set(artifact))
    if missing:
        raise ModelPredictionError(
            f"Stage 2 artifact missing required keys: {', '.join(missing)}"
        )
