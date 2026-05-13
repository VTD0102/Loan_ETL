import math
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from ml.retrain_customer_model import ALL_FEATURES
from schemas.application import ApplicationCreate
from services.model_feature_builder import build_model_input


def _artifact():
    defaults = {
        feature: 0
        for feature in ALL_FEATURES
    }
    defaults.update({
        "employment_status": "Other/Unknown",
        "ext_source_1": 0.42,
        "ext_source_3": 0.51,
        "num_bureau_records": 2,
        "num_active_credit": 1,
        "total_overdue_amount": 0,
        "max_credit_overdue_days": 0,
        "has_bad_debt": 0,
        "income_verifiable_flag": 1,
        "age_years": 38,
        "gender_male_flag": 0,
        "education_ordinal": 3,
        "cnt_children": 0,
        "cnt_fam_members": 2,
        "is_married_flag": 1,
    })
    return {
        "feature_cols": ALL_FEATURES,
        "feature_defaults": defaults,
        "dti_p75": 0.4,
    }


def test_full_payload_uses_supplied_optional_values_and_derives_history():
    payload = ApplicationCreate(
        monthly_income=Decimal("5000"),
        loan_amount=Decimal("10000"),
        term=36,
        employment_status="Employed",
        dti=Decimal("0.45"),
        is_homeowner=True,
        listing_category="Debt Consolidation",
        credit_score=720,
        ext_source_1=Decimal("0.70"),
        ext_source_3=Decimal("0.65"),
        num_bureau_records=5,
        num_active_credit=2,
        total_overdue_amount=Decimal("125.50"),
        max_credit_overdue_days=15,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=41,
        gender_male_flag=True,
        education_ordinal=4,
        cnt_children=2,
        cnt_fam_members=4,
        is_married_flag=True,
    )
    previous = [
        SimpleNamespace(default_probability=Decimal("0.55"), risk_level="High", status="AUTO_REJECTED"),
        SimpleNamespace(default_probability=Decimal("0.10"), risk_level="Low", status="APPROVED"),
    ]

    result = build_model_input(payload, _artifact(), previous_applications=previous)

    assert list(result.features) == ALL_FEATURES
    assert result.imputed_features == []
    assert result.features["ext_source_1"] == 0.70
    assert result.features["total_overdue_amount"] == 125.50
    assert result.features["has_bad_debt"] == 0
    assert result.features["gender_male_flag"] == 1
    assert result.features["log_monthly_income"] == math.log1p(5000)
    assert result.features["loan_amount_to_income"] == 2
    assert result.features["high_dti_flag"] == 1
    assert result.features["rating_ordinal"] == 6
    assert result.features["num_previous_loans"] == 2
    assert result.features["previous_default_rate"] == 0.5


def test_missing_optional_payload_uses_artifact_defaults_and_records_imputation():
    payload = ApplicationCreate(
        monthly_income=Decimal("4000"),
        loan_amount=Decimal("8000"),
        term=24,
        employment_status="Self-employed",
        dti=Decimal("0.20"),
        is_homeowner=False,
        listing_category="Other",
        credit_score=650,
    )

    result = build_model_input(payload, _artifact(), previous_applications=[])

    assert result.features["ext_source_1"] == 0.42
    assert result.features["age_years"] == 38
    assert result.features["num_previous_loans"] == 0
    assert result.features["previous_default_rate"] == 0
    assert result.features["high_dti_flag"] == 0
    assert "ext_source_1" in result.imputed_features
    assert "age_years" in result.imputed_features
    assert "num_previous_loans" not in result.imputed_features


if __name__ == "__main__":
    test_full_payload_uses_supplied_optional_values_and_derives_history()
    test_missing_optional_payload_uses_artifact_defaults_and_records_imputation()
    print("model_feature_builder tests passed")
