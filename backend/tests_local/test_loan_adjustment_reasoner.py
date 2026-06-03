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


def _C(amount, term, strategy="both", rationale=None):
    return reasoner.Candidate(
        amount=Decimal(str(amount)), term=term, strategy=strategy, rationale=rationale
    )


def test_merge_dedupes_and_keeps_llm_rationale_first():
    llm = [_C(30000, 36, "reduce_amount", "DTI cao")]
    grid = [_C(30000, 36, "reduce_amount", None), _C(50000, 24, "extend_term", None)]
    merged = reasoner.merge_candidates(
        llm, grid, original_amount=Decimal("50000"), current_term=12
    )
    keys = [(c.amount, c.term) for c in merged]
    assert (Decimal("30000"), 36) in keys
    assert (Decimal("50000"), 24) in keys
    assert len(keys) == len(set(keys))  # không trùng
    rationale = next(c.rationale for c in merged if (c.amount, c.term) == (Decimal("30000"), 36))
    assert rationale == "DTI cao"


def test_merge_rejects_invalid_candidates():
    cands = [
        _C(60000, 36),   # amount > original -> bỏ
        _C(50000, 6),    # term không hợp lệ -> bỏ
        _C(50000, 12),   # form không đổi -> bỏ
        _C(50000, 8, "extend_term"),  # term < current (8<12) và không hợp lệ -> bỏ
        _C(100, 24),     # amount < min -> kẹp lên 500
    ]
    merged = reasoner.merge_candidates(
        cands, [], original_amount=Decimal("50000"), current_term=12
    )
    keys = [(c.amount, c.term) for c in merged]
    assert keys == [(Decimal("500"), 24)]


def test_merge_drops_term_below_current():
    cands = [_C(40000, 12, "reduce_amount")]  # term == current, amount < original -> hợp lệ
    merged = reasoner.merge_candidates(
        cands, [], original_amount=Decimal("50000"), current_term=12
    )
    assert [(c.amount, c.term) for c in merged] == [(Decimal("40000"), 12)]


if __name__ == "__main__":
    test_build_risk_summary_extracts_fields()
    test_merge_dedupes_and_keeps_llm_rationale_first()
    test_merge_rejects_invalid_candidates()
    test_merge_drops_term_below_current()
    print("loan adjustment reasoner tests passed")
