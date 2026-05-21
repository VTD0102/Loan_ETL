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
from services.model_feature_builder import apply_dti_risk_floor, build_model_input


def _artifact():
    defaults = {
        feature: 0
        for feature in ALL_FEATURES
    }
    defaults.update({
        "employment_status": "Other/Unknown",
        "occupation_type": "OTHER",
        "years_employed": 0,
        "num_bureau_records": 2,
        "num_active_credit": 1,
        "num_active_credit_bureau": 1,
        "total_overdue_amount": 0,
        "max_credit_overdue_days": 0,
        "max_dpd_24m": 0,
        "avg_dpd_recent": 0,
        "num_installs_dpd10": 0,
        "total_prolongations": 0,
        "max_overdue_amount": 0,
        "cb_queries_30d": 0,
        "num_cb_queries": 0,
        "has_bad_debt": 0,
        "income_verifiable_flag": 1,
        "age_years": 38,
        "education_ordinal": 3,
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
        dti=None,
        cic_monthly_installment=Decimal("2000"),
        is_homeowner=True,
        listing_category="Debt Consolidation",
        occupation_type="EMPLOYED",
        years_employed=Decimal("4.5"),
        num_bureau_records=5,
        num_active_credit=2,
        total_overdue_amount=Decimal("125.50"),
        max_credit_overdue_days=15,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=41,
        education_ordinal=4,
        is_married_flag=True,
    )
    previous = [
        SimpleNamespace(default_probability=Decimal("0.55"), risk_level="High", status="AUTO_REJECTED"),
        SimpleNamespace(default_probability=Decimal("0.10"), risk_level="Low", status="APPROVED"),
    ]

    result = build_model_input(payload, _artifact(), previous_applications=previous)

    assert list(result.features) == ALL_FEATURES
    assert "credit_score" not in result.features
    assert "rating_ordinal" not in result.features
    assert "gender_male_flag" not in result.features
    assert "cnt_children" not in result.features
    assert "cnt_fam_members" not in result.features
    assert set(result.imputed_features) == {
        "avg_dpd_recent",
        "num_installs_dpd10",
        "total_prolongations",
        "cb_queries_30d",
        "num_cb_queries",
    }
    assert result.features["occupation_type"] == "EMPLOYED"
    assert result.features["years_employed"] == 4.5
    assert result.features["total_overdue_amount"] == 125.50
    assert result.features["has_bad_debt"] == 0
    assert result.features["log_monthly_income"] == math.log1p(5000)
    expected_dti = ((10000 / 36) + 2000) / 5000
    assert result.features["loan_amount_to_income"] == 10000 / (5000 * 12)
    assert result.features["dti"] == expected_dti
    assert result.features["payment_to_income"] == expected_dti
    assert result.features["current_debt_ratio"] == 125.50 / 10000
    assert result.features["total_debt_to_income"] == 125.50 / (5000 * 12)
    assert result.features["max_dpd_24m"] == 15
    assert result.features["num_active_credit_bureau"] == 2
    assert result.features["max_overdue_amount"] == 125.50
    assert result.features["high_dti_flag"] == 1
    assert result.features["num_previous_loans"] == 2
    assert result.features["previous_default_rate"] == 0.5


def test_v4_payload_without_deprecated_fields_derives_features_with_defaults():
    payload = ApplicationCreate(
        monthly_income=Decimal("4000"),
        loan_amount=Decimal("8000"),
        term=36,
        employment_status="Self-employed",
        dti=Decimal("0.20"),
        is_homeowner=False,
        listing_category="Other",
        occupation_type="SELFEMPLOYED",
        years_employed=Decimal("0"),
        num_bureau_records=2,
        num_active_credit=1,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=38,
        education_ordinal=3,
        is_married_flag=True,
    )

    result = build_model_input(payload, _artifact(), previous_applications=[])

    assert list(result.features) == ALL_FEATURES
    assert "credit_score" not in result.features
    assert "rating_ordinal" not in result.features
    assert result.features["occupation_type"] == "SELFEMPLOYED"
    assert result.features["years_employed"] == 0
    assert result.features["age_years"] == 38
    assert result.features["num_previous_loans"] == 0
    assert result.features["previous_default_rate"] == 0
    assert result.features["high_dti_flag"] == 0


def test_high_dti_risk_floor_never_lowers_model_probability():
    low = apply_dti_risk_floor(0.18, 0.30, low_threshold=0.2, high_threshold=0.4)
    medium = apply_dti_risk_floor(0.18, 0.40, low_threshold=0.2, high_threshold=0.4)
    high = apply_dti_risk_floor(0.18, 0.60, low_threshold=0.2, high_threshold=0.4)

    assert low == 0.18
    assert medium > low
    assert high > 0.4


if __name__ == "__main__":
    test_full_payload_uses_supplied_optional_values_and_derives_history()
    test_v4_payload_without_deprecated_fields_derives_features_with_defaults()
    test_high_dti_risk_floor_never_lowers_model_probability()
    print("model_feature_builder tests passed")
