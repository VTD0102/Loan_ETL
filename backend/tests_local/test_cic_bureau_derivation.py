"""
test_cic_bureau_derivation.py — verifies Cấp A wiring of CIC-derived bureau
features through the ML inference pipeline.

Covers:
- derive_bureau_features with empty / missing loan_history
- derive_bureau_features math on a representative loan_history
- build_model_input applies bureau_features overrides (aliases + imputed)
- ml_service.predict yields a different probability with vs without bureau
  features (sanity check that the new path is wired and changes inference)
"""
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from schemas.application import ApplicationCreate
from services import cic_service, ml_service
from services.model_feature_builder import build_model_input


def _sample_payload() -> ApplicationCreate:
    return ApplicationCreate(
        monthly_income=Decimal("5000"),
        loan_amount=Decimal("10000"),
        term=36,
        employment_status="Employed",
        dti=Decimal("0.25"),
        is_homeowner=True,
        listing_category=1,
        credit_score=720,
        occupation_type="PRIVATE_SECTOR_EMPLOYEE",
        years_employed=Decimal("4.5"),
        num_bureau_records=3,
        num_active_credit=2,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=41,
        education_ordinal=4,
        is_married_flag=True,
    )


def test_derive_empty_history_returns_only_num_cb_queries():
    cic = SimpleNamespace(num_credit_inquiries=5, loan_history=None)
    out = cic_service.derive_bureau_features(cic)
    assert out == {"num_cb_queries": 5}, out

    cic2 = SimpleNamespace(num_credit_inquiries=0, loan_history=[])
    out2 = cic_service.derive_bureau_features(cic2)
    assert out2 == {"num_cb_queries": 0}, out2


def test_derive_with_loan_history_math():
    history = [
        {"lender": "A", "amount": 1000, "status": "closed",  "dpd_max": 0},
        {"lender": "B", "amount": 2000, "status": "overdue", "dpd_max": 20},
        {"lender": "C", "amount": 5000, "status": "overdue", "dpd_max": 60},
        {"lender": "D", "amount": 3000, "status": "active",  "dpd_max": 5},
    ]
    cic = SimpleNamespace(num_credit_inquiries=4, loan_history=history)
    out = cic_service.derive_bureau_features(cic)

    assert out["num_cb_queries"] == 4
    assert out["avg_dpd_recent"] == (0 + 20 + 60 + 5) / 4
    assert out["max_dpd_24m"] == 60
    assert out["num_installs_dpd10"] == 2          # dpd_max > 10 in B and C
    assert out["max_overdue_amount"] == 5000.0     # max amount among overdue
    # Keys we cannot derive must stay absent so artifact defaults take over.
    assert "cb_queries_30d" not in out
    assert "total_prolongations" not in out


def test_build_model_input_applies_bureau_overrides():
    artifact = ml_service._load()
    payload = _sample_payload()

    baseline = build_model_input(payload, artifact)
    bureau = {
        "num_cb_queries": 7,
        "avg_dpd_recent": 12.5,
        "num_installs_dpd10": 3,
        "max_dpd_24m": 60,
        "max_overdue_amount": 5000.0,
    }
    overridden = build_model_input(payload, artifact, bureau_features=bureau)

    for k, v in bureau.items():
        assert overridden.features[k] == v, (k, overridden.features[k], v)
    # 5 features that were imputed should no longer appear as imputed when
    # bureau_features supplies them.
    assert "num_cb_queries"     not in overridden.imputed_features
    assert "avg_dpd_recent"     not in overridden.imputed_features
    assert "num_installs_dpd10" not in overridden.imputed_features
    # max_dpd_24m and max_overdue_amount were aliases (not imputed) — verify
    # they were overridden away from the alias value.
    assert overridden.features["max_dpd_24m"] != baseline.features["max_dpd_24m"] \
        or baseline.features["max_dpd_24m"] == 60
    assert overridden.features["max_overdue_amount"] != baseline.features["max_overdue_amount"] \
        or baseline.features["max_overdue_amount"] == 5000.0


def test_predict_probability_changes_with_bureau_features():
    payload = _sample_payload()
    baseline = ml_service.predict(payload)
    # Bureau features that suggest a worse credit profile than defaults
    # (defaults: avg_dpd_recent=0, num_installs_dpd10=0, max_dpd_24m=0)
    risky_bureau = {
        "num_cb_queries":     12,
        "avg_dpd_recent":     30.0,
        "num_installs_dpd10": 5,
        "max_dpd_24m":        90,
        "max_overdue_amount": 8000.0,
    }
    risky = ml_service.predict(payload, bureau_features=risky_bureau)

    # Wire-up sanity: providing different bureau features must change
    # the probability (otherwise the override never reached the model).
    assert baseline["default_probability"] != risky["default_probability"], (
        baseline["default_probability"], risky["default_probability"]
    )


if __name__ == "__main__":
    test_derive_empty_history_returns_only_num_cb_queries()
    test_derive_with_loan_history_math()
    test_build_model_input_applies_bureau_overrides()
    test_predict_probability_changes_with_bureau_features()
    print("cic_bureau_derivation tests passed")
