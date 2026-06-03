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


class _FakeLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, messages):
        return SimpleNamespace(content=self._content)


class _RaisingLLM:
    def invoke(self, messages):
        raise ValueError("boom")


def _summary():
    return {
        "rejected_amount": 50000.0, "rejected_term": 12, "default_probability": 0.55,
        "dti": 0.42, "monthly_income": 8000.0, "existing_monthly_debt": 1200.0,
        "employment_status": "Employed", "years_employed": 5.0, "has_bad_debt": False,
        "total_overdue_amount": 0.0, "num_previous_loans": 0,
        "supported_terms": [12, 24, 36, 48, 60], "min_loan_amount": 500,
    }


def _with_fake_llm(llm, fn):
    original = reasoner._reasoner_llm
    reasoner._reasoner_llm = llm
    try:
        return fn()
    finally:
        reasoner._reasoner_llm = original


def test_propose_parses_valid_json():
    content = (
        '{"candidates": [{"amount": 30000, "term": 36, "strategy": "reduce_amount", '
        '"rationale": "DTI cao nên giảm số tiền"}]}'
    )
    out = _with_fake_llm(_FakeLLM(content), lambda: reasoner.propose_candidates(_summary()))
    assert len(out) == 1
    assert out[0].amount == Decimal("30000")
    assert out[0].term == 36
    assert out[0].strategy == "reduce_amount"
    assert out[0].rationale == "DTI cao nên giảm số tiền"


def test_propose_parses_markdown_fenced_json():
    content = '```json\n{"candidates": [{"amount": 25000, "term": 48}]}\n```'
    out = _with_fake_llm(_FakeLLM(content), lambda: reasoner.propose_candidates(_summary()))
    assert len(out) == 1
    assert out[0].amount == Decimal("25000")
    assert out[0].strategy == "both"  # mặc định khi thiếu


def test_propose_returns_empty_on_bad_json():
    out = _with_fake_llm(_FakeLLM("not json at all"), lambda: reasoner.propose_candidates(_summary()))
    assert out == []


def test_propose_returns_empty_on_llm_error():
    out = _with_fake_llm(_RaisingLLM(), lambda: reasoner.propose_candidates(_summary()))
    assert out == []


def test_propose_caps_at_max_candidates():
    items = ",".join(
        '{"amount": %d, "term": 36}' % (1000 + i) for i in range(10)
    )
    content = '{"candidates": [%s]}' % items
    out = _with_fake_llm(_FakeLLM(content), lambda: reasoner.propose_candidates(_summary()))
    assert len(out) == reasoner.MAX_LLM_CANDIDATES


if __name__ == "__main__":
    test_build_risk_summary_extracts_fields()
    test_merge_dedupes_and_keeps_llm_rationale_first()
    test_merge_rejects_invalid_candidates()
    test_merge_drops_term_below_current()
    test_propose_parses_valid_json()
    test_propose_parses_markdown_fenced_json()
    test_propose_returns_empty_on_bad_json()
    test_propose_returns_empty_on_llm_error()
    test_propose_caps_at_max_candidates()
    print("loan adjustment reasoner tests passed")
