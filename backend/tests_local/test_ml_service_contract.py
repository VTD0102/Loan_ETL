import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from schemas.application import ApplicationCreate
from services import ml_service


def test_predict_raises_instead_of_mocking_invalid_artifact():
    original = ml_service._artifact
    try:
        ml_service._artifact = {"pipeline": object(), "thresholds": {}}
        payload = ApplicationCreate(
            monthly_income=Decimal("5000"),
            loan_amount=Decimal("10000"),
            term=36,
            employment_status="Employed",
            dti=Decimal("0.25"),
            is_homeowner=True,
            listing_category=1,
            credit_score=720,
            occupation_type="Laborers",
            years_employed=Decimal("4.5"),
            num_bureau_records=3,
            num_active_credit=2,
            total_overdue_amount=Decimal("0"),
            max_credit_overdue_days=0,
            has_bad_debt=False,
            income_verifiable_flag=True,
            age_years=41,
            gender_male_flag=True,
            education_ordinal=4,
            cnt_children=2,
            cnt_fam_members=4,
            is_married_flag=True,
        )
        try:
            ml_service.predict(payload)
        except ml_service.ModelPredictionError as exc:
            assert "missing required keys" in str(exc)
        else:
            raise AssertionError("ml_service.predict returned a mock prediction instead of raising")
    finally:
        ml_service._artifact = original


if __name__ == "__main__":
    test_predict_raises_instead_of_mocking_invalid_artifact()
    print("ml_service_contract tests passed")
