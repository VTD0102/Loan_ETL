import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import services.loan_adjustment_reasoner as reasoner


def _app():
    return SimpleNamespace(
        loan_amount=Decimal("50000"),
        term=12,
        default_probability=Decimal("0.55"),
        dti=Decimal("0.42"),
        monthly_income=Decimal("8000"),
        employment_status="Employed",
        years_employed=Decimal("5"),
        has_bad_debt=False,
        total_overdue_amount=Decimal("0"),
    )


def test_build_risk_summary_extracts_fields():
    summary = reasoner.build_risk_summary(
        _app(), previous_applications=[], existing_monthly_debt=1200.0
    )
    assert summary["rejected_amount"] == 50000.0
    assert summary["rejected_term"] == 12
    assert summary["default_probability"] == 0.55
    assert summary["dti"] == 0.42
    assert summary["monthly_income"] == 8000.0
    assert summary["existing_monthly_debt"] == 1200.0
    assert summary["employment_status"] == "Employed"
    assert summary["num_previous_loans"] == 0
    assert summary["supported_terms"] == [12, 24, 36, 48, 60]
    assert summary["min_loan_amount"] == 500


if __name__ == "__main__":
    test_build_risk_summary_extracts_fields()
    print("loan adjustment reasoner tests passed")
