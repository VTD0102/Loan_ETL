"""Smoke test: ml_service.predict() returns a valid contract for a complete payload.

Run from backend/:
    PYTHONPATH=. ../.venv/bin/python tests_local/test_ml.py
"""
from schemas.application import ApplicationCreate
from services import ml_service


def _build_payload() -> ApplicationCreate:
    return ApplicationCreate(
        monthly_income=5000,
        loan_amount=10000,
        term=24,
        employment_status="Employed",
        dti=0.3,
        is_homeowner=True,
        listing_category=1,
        credit_score=700,
        occupation_type="Laborers",
        years_employed=5,
        num_bureau_records=2,
        num_active_credit=1,
        total_overdue_amount=0,
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=35,
        education_ordinal=3,
        is_married_flag=True,
        gender_male_flag=True,
        cnt_children=1,
        cnt_fam_members=3,
    )


def test_ml_predict_returns_contract():
    payload = _build_payload()
    res = ml_service.predict(payload)

    assert isinstance(res, dict), f"expected dict, got {type(res)}"
    assert "default_probability" in res
    assert 0.0 <= res["default_probability"] <= 1.0
    assert "risk_level" in res
    assert res["risk_level"] in {"Low", "Medium", "High"}
    assert "risk_score" in res
    assert "model_version" in res and res["model_version"]


if __name__ == "__main__":
    test_ml_predict_returns_contract()
    print("ml_service smoke test passed")
