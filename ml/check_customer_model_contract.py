"""
Validate the customer risk model artifact contract.

Run from project root:
    python -m ml.check_customer_model_contract
"""
from __future__ import annotations

import joblib

from ml.retrain_customer_model import ALL_FEATURES, MODEL_PATH

REQUIRED_KEYS = {
    "pipeline",
    "feature_cols",
    "feature_names_out",
    "feature_defaults",
    "thresholds",
    "dti_p75",
    "model_version",
    "trained_at",
}


def validate_artifact_contract(artifact: dict) -> None:
    missing = sorted(REQUIRED_KEYS - set(artifact))
    if missing:
        raise AssertionError(f"Artifact missing required keys: {', '.join(missing)}")

    if artifact["feature_cols"] != ALL_FEATURES:
        raise AssertionError("Artifact feature_cols does not match retrain_customer_model.ALL_FEATURES")

    defaults = artifact["feature_defaults"]
    if not isinstance(defaults, dict):
        raise AssertionError("Artifact feature_defaults must be a dict")

    missing_defaults = [feature for feature in ALL_FEATURES if feature not in defaults]
    if missing_defaults:
        raise AssertionError(f"Artifact feature_defaults missing: {', '.join(missing_defaults)}")

    names_out = artifact["feature_names_out"]
    if not isinstance(names_out, list) or len(names_out) != len(ALL_FEATURES):
        raise AssertionError("Artifact feature_names_out must list every transformed model feature")


def main() -> None:
    artifact = joblib.load(MODEL_PATH)
    validate_artifact_contract(artifact)
    print(f"Artifact contract OK: {MODEL_PATH}")


if __name__ == "__main__":
    main()
