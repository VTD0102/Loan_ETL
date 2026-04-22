import pickle
from pathlib import Path

from backend.models.application import ApplicationCreate

MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "loan_risk_model.pkl"

_model = None


def _load_model():
    global _model
    if _model is None:
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
    return _model


def predict(payload: ApplicationCreate) -> dict:
    # TODO: load retrained model (8 customer features)
    # TODO: build feature vector from payload
    # TODO: run pipeline.predict_proba()
    # TODO: determine risk_level and recommended_amount/term
    # TODO: return dict with default_probability, risk_level, risk_score, recommended_*
    raise NotImplementedError
