from decimal import Decimal
from types import SimpleNamespace

from services.chat_service import _application_to_payload


def main():
    legacy_application = SimpleNamespace(
        monthly_income=Decimal("5000"),
        loan_amount=Decimal("10000"),
        term=24,
        employment_status="Employed",
        occupation_type=None,
        years_employed=None,
        dti=Decimal("0.25"),
        is_homeowner=False,
        listing_category="personal loan",
        credit_score=680,
        num_bureau_records=None,
        num_active_credit=None,
        total_overdue_amount=None,
        max_credit_overdue_days=None,
        has_bad_debt=None,
        income_verifiable_flag=None,
        age_years=None,
        gender_male_flag=None,
        education_ordinal=None,
        cnt_children=None,
        cnt_fam_members=None,
        is_married_flag=None,
    )

    payload = _application_to_payload(legacy_application)
    assert payload.term == 24
    print("Legacy chat application payload test passed")


if __name__ == "__main__":
    main()
