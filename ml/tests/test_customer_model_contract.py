import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.check_customer_model_contract import validate_artifact_contract
from ml.retrain_customer_model import ALL_FEATURES, MODEL_PATH


def test_customer_model_artifact_contract():
    artifact = joblib.load(MODEL_PATH)
    validate_artifact_contract(artifact)
    assert artifact["feature_cols"] == ALL_FEATURES


if __name__ == "__main__":
    test_customer_model_artifact_contract()
    print("customer_model_contract tests passed")
