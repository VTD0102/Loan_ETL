import math
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from machinelearning.ml.retrain_customer_model import ALL_FEATURES
from schemas.application import ApplicationCreate
from services.model_feature_builder import build_model_input


def _artifact():
    defaults = {
        feature: 0
        for feature in ALL_FEATURES
    }
    defaults.update({
        "employment_status": "Other/Unknown",
        "occupation_type": "Unknown",
        "years_employed": 0,
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
        occupation_type="Laborers",
        years_employed=Decimal("4.5"),
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
    assert result.features["occupation_type"] == "Laborers"
    assert result.features["years_employed"] == 4.5
    assert result.features["total_overdue_amount"] == 125.50
    assert result.features["has_bad_debt"] == 0
    assert result.features["gender_male_flag"] == 1
    assert result.features["log_monthly_income"] == math.log1p(5000)
    assert result.features["loan_amount_to_income"] == 2
    assert result.features["high_dti_flag"] == 1
    assert result.features["rating_ordinal"] == 6
    assert result.features["num_previous_loans"] == 2
    assert result.features["previous_default_rate"] == 0.5


def test_required_payload_without_history_derives_features_without_imputation():
    payload = ApplicationCreate(
        monthly_income=Decimal("4000"),
        loan_amount=Decimal("8000"),
        term=36,
        employment_status="Self-employed",
        dti=Decimal("0.20"),
        is_homeowner=False,
        listing_category="Other",
        credit_score=650,
        occupation_type="Unknown",
        years_employed=Decimal("0"),
        num_bureau_records=2,
        num_active_credit=1,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=38,
        gender_male_flag=False,
        education_ordinal=3,
        cnt_children=0,
        cnt_fam_members=2,
        is_married_flag=True,
    )

    result = build_model_input(payload, _artifact(), previous_applications=[])

    assert result.imputed_features == []
    assert result.features["occupation_type"] == "Unknown"
    assert result.features["years_employed"] == 0
    assert result.features["age_years"] == 38
    assert result.features["num_previous_loans"] == 0
    assert result.features["previous_default_rate"] == 0
    assert result.features["high_dti_flag"] == 0


if __name__ == "__main__":
    test_full_payload_uses_supplied_optional_values_and_derives_history()
    test_required_payload_without_history_derives_features_without_imputation()
    print("model_feature_builder tests passed")
