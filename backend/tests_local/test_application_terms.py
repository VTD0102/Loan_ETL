import sys
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from schemas.application import ApplicationCreate
from services import loan_suggestion_service


VALID_TERMS = (12, 24, 36, 48, 60)


def _payload(term):
    return {
        "monthly_income": Decimal("5000"),
        "loan_amount": Decimal("10000"),
        "term": term,
        "employment_status": "Employed",
        "dti": Decimal("0.25"),
        "is_homeowner": True,
        "listing_category": 1,
        "credit_score": 720,
        "occupation_type": "Laborers",
        "years_employed": Decimal("4.5"),
        "num_bureau_records": 3,
        "num_active_credit": 2,
        "total_overdue_amount": Decimal("0"),
        "max_credit_overdue_days": 0,
        "has_bad_debt": False,
        "income_verifiable_flag": True,
        "age_years": 41,
        "gender_male_flag": True,
        "education_ordinal": 4,
        "cnt_children": 2,
        "cnt_fam_members": 4,
        "is_married_flag": True,
    }


def test_application_create_accepts_supported_terms():
    for term in VALID_TERMS:
        payload = ApplicationCreate(**_payload(term))
        assert payload.term == term


def test_application_create_rejects_unsupported_terms():
    try:
        ApplicationCreate(**_payload(18))
    except ValidationError as exc:
        assert "term phải là 12, 24, 36, 48 hoặc 60" in str(exc)
    else:
        raise AssertionError("ApplicationCreate accepted an unsupported term")


def test_loan_suggestion_uses_same_supported_terms():
    assert loan_suggestion_service._TERMS == list(VALID_TERMS)


if __name__ == "__main__":
    test_application_create_accepts_supported_terms()
    test_application_create_rejects_unsupported_terms()
    test_loan_suggestion_uses_same_supported_terms()
    print("application term tests passed")
