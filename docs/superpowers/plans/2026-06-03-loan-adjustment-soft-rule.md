# Luật mềm cho công cụ điều chỉnh khoản vay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho LLM (RAG) suy luận hướng và tham số điều chỉnh khoản vay cho đơn bị `AUTO_REJECTED`, trong khi model rủi ro vẫn là trọng tài cuối kiểm chứng mọi phương án.

**Architecture:** Soft-propose / hard-verify. Một module mới `loan_adjustment_reasoner.py` gọi LLM để đề xuất ứng viên `(số tiền, kỳ hạn)` từ hồ sơ rủi ro; các ứng viên này được gộp với lưới cứng hiện có, làm sạch, rồi đưa toàn bộ qua đúng vòng `ml_service.predict` + `validate_confirmed_values` + rank của `loan_adjustment_tool.py`. Worst case (LLM lỗi/trả rỗng) = lưới cứng thuần. Contract đầu ra `LoanAdjustmentResult` giữ nguyên nên `chat_service`/frontend không đổi.

**Tech Stack:** Python, FastAPI, SQLAlchemy ORM, LangChain `ChatOpenAI` qua OpenRouter (Gemini 2.5 Flash), LightGBM artifact, test theo style `backend/tests_local/test_*.py` (script standalone, monkeypatch, không pytest).

**Spec:** `docs/superpowers/specs/2026-06-03-loan-adjustment-soft-rule-design.md`

**Quy ước chạy test:** mọi lệnh chạy từ thư mục `backend/`:
```bash
cd backend
../.venv/bin/python tests_local/test_<name>.py
```
Mỗi file test có khối `if __name__ == "__main__":` tự gọi từng hàm và in dòng "... passed".

---

## File Structure

- **Create** `backend/services/loan_adjustment_reasoner.py` — toàn bộ logic LLM: `Candidate` dataclass, `build_risk_summary`, `propose_candidates`, `merge_candidates`, singleton LLM. KHÔNG import `loan_adjustment_tool` (tránh vòng lặp import).
- **Modify** `backend/core/config.py` — thêm cờ `rag_loan_reasoner_enabled`.
- **Modify** `backend/services/loan_adjustment_tool.py` — thêm `rationale` vào `LoanAdjustmentProposal`; thêm `_grid_candidates`, `_change_magnitude`, `_unified_rank`; viết lại `find_best_reapplication_option` (bỏ dừng-sớm-theo-stage, gộp + verify + rank một lần); cập nhật `_proposal_from_prediction`, `format_result_for_rag`, `_proposal_message`, `_strategy_text`.
- **Create** `backend/tests_local/test_loan_adjustment_reasoner.py` — test cho module mới.
- **Modify** `backend/tests_local/test_loan_adjustment_tool.py` — cập nhật helper `_patch_tool` để stub reasoner (giữ test không chạm mạng) + thêm test tích hợp luật mềm.

---

## Task 1: Thêm cờ cấu hình `rag_loan_reasoner_enabled`

**Files:**
- Modify: `backend/core/config.py` (vùng các cờ RAG, quanh dòng 80)
- Test: `backend/tests_local/test_loan_reasoner_config.py` (create)

- [ ] **Step 1: Viết test thất bại**

Create `backend/tests_local/test_loan_reasoner_config.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from core.config import settings


def test_loan_reasoner_flag_defaults_true():
    assert hasattr(settings, "rag_loan_reasoner_enabled")
    assert settings.rag_loan_reasoner_enabled is True


if __name__ == "__main__":
    test_loan_reasoner_flag_defaults_true()
    print("loan reasoner config test passed")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_reasoner_config.py`
Expected: FAIL — `AssertionError` hoặc `AttributeError` vì cờ chưa tồn tại.

- [ ] **Step 3: Thêm cờ vào Settings**

Trong `backend/core/config.py`, ngay sau dòng `rag_reranker_top_k: int = 12` (kết thúc khối reranker, ~dòng 82), thêm:

```python

    # RAG loan adjustment reasoner (soft-propose / hard-verify)
    rag_loan_reasoner_enabled: bool = True
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_reasoner_config.py`
Expected: PASS — in "loan reasoner config test passed".

- [ ] **Step 5: Commit**

```bash
git add backend/core/config.py backend/tests_local/test_loan_reasoner_config.py
git commit -m "feat: thêm cờ rag_loan_reasoner_enabled"
```

---

## Task 2: Module reasoner — `Candidate` + `build_risk_summary`

**Files:**
- Create: `backend/services/loan_adjustment_reasoner.py`
- Test: `backend/tests_local/test_loan_adjustment_reasoner.py` (create)

- [ ] **Step 1: Viết test thất bại**

Create `backend/tests_local/test_loan_adjustment_reasoner.py`:

```python
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
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.loan_adjustment_reasoner'`.

- [ ] **Step 3: Tạo module với Candidate + build_risk_summary**

Create `backend/services/loan_adjustment_reasoner.py`:

```python
"""
loan_adjustment_reasoner.py

LLM "soft proposer" cho công cụ điều chỉnh khoản vay. Module này CHỈ đề xuất ứng
viên (số tiền, kỳ hạn) dựa trên hồ sơ rủi ro; việc kiểm chứng an toàn (predict +
validate) do loan_adjustment_tool đảm nhiệm. KHÔNG import loan_adjustment_tool ở
đây để tránh vòng lặp import.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any

import httpx
import openai

from core.config import settings
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

SUPPORTED_TERMS = (12, 24, 36, 48, 60)
MIN_LOAN_AMOUNT = 500
MAX_LLM_CANDIDATES = 6
_REASONER_MAX_TOKENS = 300


@dataclass(frozen=True)
class Candidate:
    amount: Decimal
    term: int
    strategy: str
    rationale: str | None = None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def build_risk_summary(
    app: Any,
    previous_applications: list[Any] | None,
    existing_monthly_debt: float,
) -> dict[str, Any]:
    """Trích hồ sơ rủi ro tất định từ đơn bị AUTO_REJECTED để làm input cho LLM."""
    return {
        "rejected_amount": float(app.loan_amount),
        "rejected_term": int(app.term),
        "default_probability": _float_or_none(getattr(app, "default_probability", None)),
        "dti": _float_or_none(getattr(app, "dti", None)),
        "monthly_income": float(app.monthly_income),
        "existing_monthly_debt": float(existing_monthly_debt),
        "employment_status": getattr(app, "employment_status", None) or "",
        "years_employed": _float_or_none(getattr(app, "years_employed", None)),
        "has_bad_debt": bool(getattr(app, "has_bad_debt", False)),
        "total_overdue_amount": float(getattr(app, "total_overdue_amount", 0) or 0),
        "num_previous_loans": len(previous_applications or []),
        "supported_terms": list(SUPPORTED_TERMS),
        "min_loan_amount": MIN_LOAN_AMOUNT,
    }
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py`
Expected: PASS — in "loan adjustment reasoner tests passed".

- [ ] **Step 5: Commit**

```bash
git add backend/services/loan_adjustment_reasoner.py backend/tests_local/test_loan_adjustment_reasoner.py
git commit -m "feat: reasoner module với Candidate và build_risk_summary"
```

---

## Task 3: `merge_candidates` — gộp, làm sạch, khử trùng

**Files:**
- Modify: `backend/services/loan_adjustment_reasoner.py`
- Test: `backend/tests_local/test_loan_adjustment_reasoner.py`

Quy tắc làm sạch: `term` phải thuộc `SUPPORTED_TERMS` và `>= current_term`; `amount` kẹp dưới về `MIN_LOAN_AMOUNT`, và **bỏ** nếu `amount > original_amount` (không bao giờ tăng khoản vay); **bỏ** form không đổi `(original_amount, current_term)`; khử trùng theo `(amount, term)`, ưu tiên giữ ứng viên LLM (đứng trước) để rationale của nó thắng.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `backend/tests_local/test_loan_adjustment_reasoner.py` (trước khối `__main__`):

```python
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
```

Và thêm các dòng gọi vào khối `__main__`:

```python
    test_merge_dedupes_and_keeps_llm_rationale_first()
    test_merge_rejects_invalid_candidates()
    test_merge_drops_term_below_current()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py`
Expected: FAIL — `AttributeError: module ... has no attribute 'merge_candidates'`.

- [ ] **Step 3: Thêm merge_candidates + helper**

Thêm vào `backend/services/loan_adjustment_reasoner.py` (sau `build_risk_summary`):

```python
def _clean_amount(value: Any, original_amount: Decimal) -> Decimal | None:
    try:
        amount = Decimal(str(value)).quantize(Decimal("1"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount < MIN_LOAN_AMOUNT:
        amount = Decimal(MIN_LOAN_AMOUNT)
    if amount > original_amount:
        return None  # không bao giờ tăng khoản vay để giảm rủi ro
    return amount


def merge_candidates(
    llm_candidates: list[Candidate],
    grid_candidates: list[Candidate],
    *,
    original_amount: Any,
    current_term: Any,
) -> list[Candidate]:
    """Gộp ứng viên LLM (ưu tiên) với lưới cứng, làm sạch và khử trùng."""
    original_amount = Decimal(str(original_amount))
    current_term = int(current_term)
    seen: set[tuple[Decimal, int]] = set()
    cleaned: list[Candidate] = []
    for cand in [*llm_candidates, *grid_candidates]:
        amount = _clean_amount(cand.amount, original_amount)
        if amount is None:
            continue
        try:
            term = int(cand.term)
        except (TypeError, ValueError):
            continue
        if term not in SUPPORTED_TERMS or term < current_term:
            continue
        if amount == original_amount and term == current_term:
            continue  # form không đổi (đã bị từ chối)
        key = (amount, term)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            Candidate(amount=amount, term=term, strategy=cand.strategy, rationale=cand.rationale)
        )
    return cleaned
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/loan_adjustment_reasoner.py backend/tests_local/test_loan_adjustment_reasoner.py
git commit -m "feat: merge_candidates làm sạch và khử trùng ứng viên"
```

---

## Task 4: `propose_candidates` — gọi LLM, parse JSON chịu lỗi

**Files:**
- Modify: `backend/services/loan_adjustment_reasoner.py`
- Test: `backend/tests_local/test_loan_adjustment_reasoner.py`

`propose_candidates` phải trả `[]` trên mọi lỗi (timeout, API, JSON hỏng). Test inject một LLM giả qua `reasoner._reasoner_llm` để không chạm mạng.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `backend/tests_local/test_loan_adjustment_reasoner.py`:

```python
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
```

Thêm vào khối `__main__`:

```python
    test_propose_parses_valid_json()
    test_propose_parses_markdown_fenced_json()
    test_propose_returns_empty_on_bad_json()
    test_propose_returns_empty_on_llm_error()
    test_propose_caps_at_max_candidates()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py`
Expected: FAIL — `AttributeError` cho `_reasoner_llm` / `propose_candidates`.

- [ ] **Step 3: Thêm singleton LLM + prompt + propose_candidates**

Thêm vào `backend/services/loan_adjustment_reasoner.py`:

```python
_REASONER_SYSTEM_PROMPT = (
    "Bạn là chuyên viên tín dụng CreditIntel. Khách hàng vừa bị TỪ CHỐI TỰ ĐỘNG vì "
    "rủi ro vỡ nợ cao. Dựa trên hồ sơ rủi ro được cung cấp, hãy đề xuất tối đa 6 phương "
    "án điều chỉnh (số tiền vay, kỳ hạn) nhằm đưa xác suất vỡ nợ xuống dưới ngưỡng an "
    "toàn. Chỉ được GIẢM số tiền (không tăng) và chỉ được GIỮ NGUYÊN hoặc TĂNG kỳ hạn. "
    "Kỳ hạn phải thuộc {12, 24, 36, 48, 60} tháng. Ưu tiên hướng phù hợp với yếu tố rủi "
    "ro chính: nếu DTI hoặc nợ hàng tháng cao thì giảm số tiền thường hiệu quả hơn kéo "
    "dài kỳ hạn.\n"
    'CHỈ trả về JSON đúng dạng: {"candidates": [{"amount": <số USD>, "term": <tháng>, '
    '"strategy": "reduce_amount|extend_term|both", "rationale": "<lý do ngắn>"}]}\n'
    "Không giải thích gì thêm ngoài JSON."
)


def _format_summary(summary: dict[str, Any]) -> str:
    return (
        f"Số tiền bị từ chối: {summary['rejected_amount']:.0f} USD\n"
        f"Kỳ hạn hiện tại: {summary['rejected_term']} tháng\n"
        f"Xác suất vỡ nợ: {summary['default_probability']}\n"
        f"DTI: {summary['dti']}\n"
        f"Thu nhập hàng tháng: {summary['monthly_income']:.0f} USD\n"
        f"Nợ hàng tháng hiện có: {summary['existing_monthly_debt']:.0f} USD\n"
        f"Tình trạng việc làm: {summary['employment_status']}\n"
        f"Số năm làm việc: {summary['years_employed']}\n"
        f"Có nợ xấu: {summary['has_bad_debt']}\n"
        f"Tổng nợ quá hạn: {summary['total_overdue_amount']:.0f} USD\n"
        f"Số khoản vay trước đây: {summary['num_previous_loans']}\n"
        f"Kỳ hạn cho phép: {summary['supported_terms']}\n"
        f"Số tiền vay tối thiểu: {summary['min_loan_amount']} USD"
    )


_reasoner_llm_lock = Lock()
_reasoner_llm = None


def _get_reasoner_llm():
    global _reasoner_llm
    if _reasoner_llm is None:
        with _reasoner_llm_lock:
            if _reasoner_llm is None:
                from langchain_openai import ChatOpenAI
                _reasoner_llm = ChatOpenAI(
                    model=LLM_MODEL,
                    openai_api_key=settings.openrouter_api_key,
                    openai_api_base=OPENROUTER_BASE_URL,
                    temperature=0,
                    max_tokens=_REASONER_MAX_TOKENS,
                    timeout=settings.rag_llm_timeout_seconds,
                    max_retries=settings.rag_llm_max_retries,
                )
    return _reasoner_llm


def propose_candidates(summary: dict[str, Any]) -> list[Candidate]:
    """Gọi LLM đề xuất ứng viên. Trả [] trên mọi lỗi để caller fallback về lưới."""
    if not summary:
        return []
    try:
        llm = _get_reasoner_llm()
        messages = [
            {"role": "system", "content": _REASONER_SYSTEM_PROMPT},
            {"role": "user", "content": _format_summary(summary)},
        ]
        response = llm.invoke(messages)
        content = (response.content or "").strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)
        raw = parsed.get("candidates", []) if isinstance(parsed, dict) else []
        out: list[Candidate] = []
        for item in raw[:MAX_LLM_CANDIDATES]:
            try:
                amount = Decimal(str(item["amount"]))
                term = int(item["term"])
            except (KeyError, TypeError, ValueError, InvalidOperation):
                continue
            strategy = str(item.get("strategy") or "both")
            rationale = item.get("rationale")
            out.append(
                Candidate(
                    amount=amount,
                    term=term,
                    strategy=strategy,
                    rationale=str(rationale) if rationale else None,
                )
            )
        return out
    except (openai.APITimeoutError, openai.APIError, httpx.TimeoutException) as exc:
        logger.warning("Loan reasoner upstream error: %s", exc)
        return []
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.info("Loan reasoner returned non-JSON, ignoring (%s)", exc)
        return []
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py`
Expected: PASS — tất cả hàm reasoner.

- [ ] **Step 5: Commit**

```bash
git add backend/services/loan_adjustment_reasoner.py backend/tests_local/test_loan_adjustment_reasoner.py
git commit -m "feat: propose_candidates gọi LLM với parse JSON chịu lỗi"
```

---

## Task 5: `LoanAdjustmentProposal.rationale` + diễn giải trong RAG context

**Files:**
- Modify: `backend/services/loan_adjustment_tool.py` (dataclass dòng 21-30; `format_result_for_rag` dòng 274-289; `_proposal_from_prediction` dòng 401-414; `_strategy_text` dòng 393-398)
- Test: `backend/tests_local/test_loan_adjustment_tool.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `backend/tests_local/test_loan_adjustment_tool.py` (trước khối `__main__`):

```python
def test_format_result_includes_rationale_when_present():
    proposal = tool.LoanAdjustmentProposal(
        loan_amount=Decimal("30000"),
        term=36,
        default_probability=0.30,
        risk_level="Medium",
        risk_score=70,
        model_version="test-model",
        adjustment_strategy="reduce_amount",
        rationale="DTI cao nên giảm số tiền",
    )
    result = tool.LoanAdjustmentResult(
        status="proposal",
        source_application_id="x",
        current_loan_amount=Decimal("50000"),
        current_term=12,
        current_default_probability=0.55,
        proposal=proposal,
        best_observed=None,
        message="msg",
        proposals=[proposal],
    )
    text = tool.format_result_for_rag(result)
    assert "DTI cao nên giảm số tiền" in text
    assert "giảm số tiền vay" in text
```

Thêm vào khối `__main__`:

```python
    test_format_result_includes_rationale_when_present()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_tool.py`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'rationale'`.

- [ ] **Step 3: Thêm field + cập nhật helpers**

Trong `backend/services/loan_adjustment_tool.py`:

(a) Thêm field vào `LoanAdjustmentProposal` (sau `adjustment_strategy: str | None = None`):

```python
    rationale: str | None = None
```

(b) Cập nhật `_proposal_from_prediction` để nhận `rationale`:

```python
def _proposal_from_prediction(
    payload: ApplicationConfirm,
    prediction: dict[str, Any],
    strategy: str | None = None,
    rationale: str | None = None,
) -> LoanAdjustmentProposal:
    return LoanAdjustmentProposal(
        loan_amount=_to_decimal(payload.loan_amount),
        term=int(payload.term),
        default_probability=float(prediction["default_probability"]),
        risk_level=prediction.get("risk_level") or "",
        risk_score=int(prediction.get("risk_score") or 0),
        model_version=prediction.get("model_version"),
        adjustment_strategy=strategy,
        rationale=rationale,
    )
```

(c) Cập nhật `_strategy_text` thêm nhánh `both`:

```python
def _strategy_text(strategy: str | None) -> str:
    if strategy == "reduce_amount":
        return "giảm số tiền vay"
    if strategy == "extend_term":
        return "tăng kỳ hạn"
    if strategy == "both":
        return "điều chỉnh số tiền và kỳ hạn"
    return "điều chỉnh khoản vay"
```

(d) Cập nhật `format_result_for_rag` để chèn rationale:

```python
def format_result_for_rag(result: LoanAdjustmentResult) -> str:
    if result.proposal is None:
        return result.message

    proposals = result.proposals or [result.proposal]
    option_lines = []
    for index, proposal in enumerate(proposals, start=1):
        line = (
            f"Phương án {index} ({_strategy_text(proposal.adjustment_strategy)}): "
            f"số tiền {proposal.loan_amount}, "
            f"kỳ hạn {proposal.term} tháng, "
            f"xác suất vỡ nợ {proposal.default_probability:.2%}, "
            f"mức rủi ro {proposal.risk_level}."
        )
        if proposal.rationale:
            line += f" Lý do đề xuất: {proposal.rationale}"
        option_lines.append(line)
    return f"{result.message}\n" + "\n".join(option_lines)
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_tool.py`
Expected: PASS — toàn bộ file (rationale là field optional nên các test cũ không đổi).

- [ ] **Step 5: Commit**

```bash
git add backend/services/loan_adjustment_tool.py backend/tests_local/test_loan_adjustment_tool.py
git commit -m "feat: rationale trên LoanAdjustmentProposal và đưa vào RAG context"
```

---

## Task 6: Khoá rank thống nhất — `_change_magnitude` + `_unified_rank`

**Files:**
- Modify: `backend/services/loan_adjustment_tool.py` (thêm gần `_passing_rank` dòng 356-370)
- Test: `backend/tests_local/test_loan_adjustment_tool.py`

Khoá rank: `(change_magnitude, default_probability, -loan_amount, term)`. `change_magnitude` = tỉ lệ giảm tiền cộng tỉ lệ tăng kỳ hạn (chuẩn hoá), nhỏ = gần đơn gốc hơn = ưu tiên. Tie-break: prob thấp hơn, rồi số tiền lớn hơn, rồi kỳ hạn ngắn hơn.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `backend/tests_local/test_loan_adjustment_tool.py`:

```python
def test_change_magnitude_amount_and_term():
    app = _rejected_app(loan_amount=Decimal("50000"), term=12)
    # giảm 50% số tiền, cùng kỳ hạn -> 0.5
    p_reduce = tool.LoanAdjustmentProposal(
        loan_amount=Decimal("25000"), term=12, default_probability=0.3,
        risk_level="Medium", risk_score=70,
    )
    assert tool._change_magnitude(app, p_reduce) == 0.5
    # giữ tiền, tăng kỳ hạn 12 -> 36 = (36-12)/12 = 2.0
    p_extend = tool.LoanAdjustmentProposal(
        loan_amount=Decimal("50000"), term=36, default_probability=0.3,
        risk_level="Medium", risk_score=70,
    )
    assert tool._change_magnitude(app, p_extend) == 2.0


def test_unified_rank_prefers_smaller_change():
    app = _rejected_app(loan_amount=Decimal("50000"), term=12)
    small = tool.LoanAdjustmentProposal(
        loan_amount=Decimal("45000"), term=12, default_probability=0.39,
        risk_level="Medium", risk_score=61,
    )  # magnitude 0.1
    big_but_safer = tool.LoanAdjustmentProposal(
        loan_amount=Decimal("10000"), term=12, default_probability=0.10,
        risk_level="Low", risk_score=90,
    )  # magnitude 0.8
    ranked = sorted([big_but_safer, small], key=lambda p: tool._unified_rank(app, p))
    assert ranked[0] is small  # thay đổi ít nhất thắng dù prob cao hơn
```

Thêm vào khối `__main__`:

```python
    test_change_magnitude_amount_and_term()
    test_unified_rank_prefers_smaller_change()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_tool.py`
Expected: FAIL — `AttributeError: module ... has no attribute '_change_magnitude'`.

- [ ] **Step 3: Thêm hàm**

Thêm vào `backend/services/loan_adjustment_tool.py` (ngay sau `_passing_rank`):

```python
def _change_magnitude(app: Any, proposal: LoanAdjustmentProposal) -> float:
    """Tổng tỉ lệ thay đổi so với đơn gốc (giảm tiền + tăng kỳ hạn). Nhỏ = gần gốc."""
    original_amount = _to_decimal(app.loan_amount)
    current_term = int(app.term)
    amount_change = 0.0
    if original_amount > 0:
        reduction = max(original_amount - proposal.loan_amount, Decimal("0"))
        amount_change = float(reduction) / float(original_amount)
    term_change = 0.0
    if current_term > 0:
        term_change = max(proposal.term - current_term, 0) / current_term
    return round(amount_change + term_change, 6)


def _unified_rank(app: Any, proposal: LoanAdjustmentProposal) -> tuple[Any, ...]:
    """Khoá sort liên-strategy: ưu tiên thay đổi ít nhất, rồi prob thấp, rồi số tiền
    lớn hơn, rồi kỳ hạn ngắn hơn."""
    return (
        _change_magnitude(app, proposal),
        proposal.default_probability,
        -proposal.loan_amount,
        proposal.term,
    )
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_tool.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/loan_adjustment_tool.py backend/tests_local/test_loan_adjustment_tool.py
git commit -m "feat: khoá rank thống nhất ưu tiên thay đổi ít nhất so với đơn gốc"
```

---

## Task 7: Viết lại `find_best_reapplication_option` (bỏ dừng-sớm, gộp + verify + rank một lần)

**Files:**
- Modify: `backend/services/loan_adjustment_tool.py` (imports đầu file; `find_best_reapplication_option` dòng 45-159; `_proposal_message` dòng 381-390)
- Modify: `backend/tests_local/test_loan_adjustment_tool.py` (helper `_patch_tool` dòng 105-139, thêm stub reasoner)
- Test: `backend/tests_local/test_loan_adjustment_tool.py`

- [ ] **Step 1: Cập nhật helper `_patch_tool` để stub reasoner (giữ test không chạm mạng)**

Trong `backend/tests_local/test_loan_adjustment_tool.py`, thêm import gần đầu (sau `import services.loan_adjustment_tool as tool`):

```python
import services.loan_adjustment_reasoner as reasoner
```

Trong hàm `_patch_tool`, thêm tham số `llm_candidates=None` và stub `reasoner.propose_candidates`. Thay toàn bộ thân hàm `_patch_tool` bằng:

```python
def _patch_tool(predictions, validation_failures=None, llm_candidates=None):
    validation_failures = set(validation_failures or [])
    original_predict = tool.ml_service.predict
    original_load = tool.ml_service._load
    original_fetch_previous = tool.fetch_previous_applications
    original_validate = tool.validate_confirmed_values
    original_propose = reasoner.propose_candidates

    def fake_predict(payload, db=None, user_id=None):
        prob = predictions.get((Decimal(str(payload.loan_amount)), int(payload.term)), 0.99)
        return {
            "default_probability": prob,
            "risk_level": "High" if prob > 0.4 else "Medium",
            "risk_score": int(round((1 - prob) * 100)),
            "suggested_amount": 35000,
            "suggested_term": 36,
            "model_version": "test-model",
        }

    def fake_validate(payload, artifact, previous_applications=None):
        key = (Decimal(str(payload.loan_amount)), int(payload.term))
        if key in validation_failures:
            raise ValueError("candidate exceeds safe amount")

    tool.ml_service.predict = fake_predict
    tool.ml_service._load = lambda: {"thresholds": {"low": 0.2, "high": 0.4}}
    tool.fetch_previous_applications = lambda db, user_id: []
    tool.validate_confirmed_values = fake_validate
    reasoner.propose_candidates = lambda summary: list(llm_candidates or [])

    def restore():
        tool.ml_service.predict = original_predict
        tool.ml_service._load = original_load
        tool.fetch_previous_applications = original_fetch_previous
        tool.validate_confirmed_values = original_validate
        reasoner.propose_candidates = original_propose

    return restore
```

> Lưu ý: `fetch_previous_applications` và `validate_confirmed_values` được dùng qua tên trong `tool`. Sau khi Task 7 thêm `from services import loan_adjustment_reasoner as reasoner` vào tool, `tool.find_best_reapplication_option` sẽ gọi `reasoner.propose_candidates`, mà ở đây ta đã patch trên chính object `reasoner` dùng chung. Vì cờ mặc định `rag_loan_reasoner_enabled=True`, stub trả `[]` giữ hành vi lưới-cứng cho mọi test cũ.

- [ ] **Step 2: Viết test tích hợp thất bại**

Thêm vào `backend/tests_local/test_loan_adjustment_tool.py`:

```python
def test_llm_candidate_can_win_top1_when_smaller_change_and_safe():
    # Đơn gốc 50000/term12. Lưới (extend_term) có 50000/36 = 0.30 (magnitude 2.0).
    # LLM đề xuất 45000/12 = 0.35 (magnitude 0.1) -> thay đổi nhỏ hơn nhiều -> top1.
    app = _rejected_app(recommended_amount=None, loan_amount=Decimal("50000"), term=12)
    db = FakeDB([app])
    predictions = {
        (Decimal("50000"), 24): 0.45,
        (Decimal("50000"), 36): 0.30,
        (Decimal("50000"), 48): 0.34,
        (Decimal("50000"), 60): 0.38,
        (Decimal("45000"), 12): 0.35,
    }
    llm = [reasoner.Candidate(amount=Decimal("45000"), term=12,
                              strategy="reduce_amount", rationale="DTI cao")]
    restore = _patch_tool(predictions, llm_candidates=llm)
    try:
        result = tool.find_best_reapplication_option(db, app.user_id)
    finally:
        restore()

    assert result.status == "proposal"
    assert result.proposal.loan_amount == Decimal("45000")
    assert result.proposal.term == 12
    assert result.proposal.rationale == "DTI cao"


def test_empty_llm_matches_grid_only_passing_set():
    # LLM trả [] -> kết quả phải đúng tập passing của lưới cứng.
    app = _rejected_app(recommended_amount=None, loan_amount=Decimal("50000"), term=12)
    db = FakeDB([app])
    predictions = {
        (Decimal("50000"), 24): 0.45,
        (Decimal("50000"), 36): 0.32,
        (Decimal("50000"), 48): 0.34,
        (Decimal("50000"), 60): 0.38,
    }
    restore = _patch_tool(predictions, llm_candidates=[])
    try:
        result = tool.find_best_reapplication_option(db, app.user_id)
    finally:
        restore()

    assert result.status == "proposal"
    assert {(p.loan_amount, p.term) for p in result.proposals} == {
        (Decimal("50000"), 36),
        (Decimal("50000"), 48),
        (Decimal("50000"), 60),
    }
    assert result.proposal.term == 36  # thay đổi ít nhất (kỳ hạn tăng ít nhất)
```

Thêm vào khối `__main__`:

```python
    test_llm_candidate_can_win_top1_when_smaller_change_and_safe()
    test_empty_llm_matches_grid_only_passing_set()
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_tool.py`
Expected: FAIL — `test_llm_candidate_can_win_top1...` fail vì tool chưa gọi reasoner/chưa gộp; có thể vài test cũ cũng fail do hành vi dừng-sớm chưa bị bỏ.

- [ ] **Step 4: Viết lại tool**

Trong `backend/services/loan_adjustment_tool.py`:

(a) Thêm imports gần đầu file (sau `from services.model_feature_builder import ...`):

```python
from core.config import settings
from services import loan_adjustment_reasoner as reasoner
```

(b) Thêm helper `_grid_candidates` (đặt ngay trước `_candidate_stages`):

```python
def _grid_candidates(app: Any) -> list[reasoner.Candidate]:
    """Làm phẳng các stage lưới cứng thành danh sách Candidate (không rationale)."""
    out: list[reasoner.Candidate] = []
    for strategy, pairs in _candidate_stages(app):
        for amount, term in pairs:
            out.append(
                reasoner.Candidate(
                    amount=_to_decimal(amount), term=int(term), strategy=strategy, rationale=None
                )
            )
    return out
```

(c) Thay phần thân `find_best_reapplication_option` từ sau khối kiểm tra `cic_blacklist` (tức từ dòng `artifact = ml_service._load()` cho tới hết hàm) bằng:

```python
    artifact = ml_service._load()
    previous = fetch_previous_applications(db, user_id)

    existing_debt = infer_existing_monthly_debt(
        app.monthly_income, app.loan_amount, app.term, app.dti or Decimal("0")
    )
    llm_candidates: list[reasoner.Candidate] = []
    if settings.rag_loan_reasoner_enabled:
        summary = reasoner.build_risk_summary(app, previous, existing_debt)
        llm_candidates = reasoner.propose_candidates(summary)
    grid_candidates = _grid_candidates(app)
    candidates = reasoner.merge_candidates(
        llm_candidates,
        grid_candidates,
        original_amount=app.loan_amount,
        current_term=app.term,
    )

    best_observed: LoanAdjustmentProposal | None = None
    observed: list[tuple[tuple[float, int, Decimal], LoanAdjustmentProposal]] = []
    passing: list[tuple[tuple[Any, ...], LoanAdjustmentProposal]] = []

    for cand in candidates:
        payload = application_to_confirm_payload(app, loan_amount=cand.amount, term=cand.term)
        prediction = ml_service.predict(payload, db=db, user_id=user_id)
        proposal = _proposal_from_prediction(
            payload, prediction, strategy=cand.strategy, rationale=cand.rationale
        )

        if best_observed is None or proposal.default_probability < best_observed.default_probability:
            best_observed = proposal
        observed.append((_fallback_rank(proposal), proposal))

        if proposal.default_probability > AUTO_REVIEW_THRESHOLD:
            continue

        try:
            validate_confirmed_values(payload, artifact, previous_applications=previous)
        except ValueError:
            continue

        passing.append((_unified_rank(app, proposal), proposal))

    if passing:
        passing.sort(key=lambda item: item[0])
        proposal_options = [proposal for _, proposal in passing[:3]]
        top = proposal_options[0]
        return LoanAdjustmentResult(
            status="proposal",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=top,
            best_observed=best_observed,
            message=_proposal_message(top.adjustment_strategy),
            proposals=proposal_options,
        )

    if not observed:
        return LoanAdjustmentResult(
            status="no_passing_option",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=None,
            best_observed=best_observed,
            message="No safe adjustment candidate was found.",
        )

    # Fallback: hiển thị các form đã đổi tốt nhất, không bao giờ trả form gốc đã bị từ chối.
    observed.sort(key=lambda item: item[0])
    fallback_options = [proposal for _, proposal in observed[:3]]
    if fallback_options:
        return LoanAdjustmentResult(
            status="fallback_proposal",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=fallback_options[0],
            best_observed=best_observed,
            message="Không tìm được khoản vay nào dưới ngưỡng tự động duyệt. "
                    "Các phương án dưới đây là form khác tốt nhất hiện có nhưng vẫn cần cải thiện thêm.",
            proposals=fallback_options,
        )

    return LoanAdjustmentResult(
        status="no_passing_option",
        source_application_id=str(app.id),
        current_loan_amount=app.loan_amount,
        current_term=app.term,
        current_default_probability=_float_or_none(app.default_probability),
        proposal=None,
        best_observed=best_observed,
        message="No safe adjustment candidate was found.",
    )
```

(d) Cập nhật `_proposal_message` (bỏ giả định "đã thử kỳ hạn tối đa", thêm nhánh `both`):

```python
def _proposal_message(strategy: str | None) -> str:
    if strategy == "reduce_amount":
        return "Có thể nộp form khác bằng cách giảm số tiền vay."
    if strategy == "both":
        return "Có thể nộp form khác bằng cách điều chỉnh cả số tiền vay và kỳ hạn."
    return (
        "Có thể nộp form khác bằng cách giữ nguyên số tiền vay "
        "và tăng kỳ hạn trả nợ."
    )
```

- [ ] **Step 5: Chạy toàn bộ file test tool, xác nhận PASS**

Run: `cd backend && ../.venv/bin/python tests_local/test_loan_adjustment_tool.py`
Expected: PASS — in "loan adjustment tool tests passed". Tất cả test cũ vẫn đúng (đã đối chiếu: ranking relative-change cho cùng thứ tự với mọi prediction dict hiện có) + 2 test tích hợp mới pass.

- [ ] **Step 6: Commit**

```bash
git add backend/services/loan_adjustment_tool.py backend/tests_local/test_loan_adjustment_tool.py
git commit -m "feat: gộp đề xuất LLM với lưới cứng, verify và rank một lần (bỏ dừng-sớm-theo-stage)"
```

---

## Task 8: Hồi quy toàn diện + cập nhật tài liệu

**Files:**
- Modify: `docs/superpowers/specs/2026-06-03-loan-adjustment-soft-rule-design.md` (đánh dấu trạng thái Đã triển khai)
- Modify: `CLAUDE.md` (mục RAG Chat Flow — một câu mô tả reasoner) — chỉ nếu cần
- Test: chạy các file test liên quan

- [ ] **Step 1: Chạy các test liên quan loan adjustment + chat**

Run:
```bash
cd backend
../.venv/bin/python tests_local/test_loan_reasoner_config.py
../.venv/bin/python tests_local/test_loan_adjustment_reasoner.py
../.venv/bin/python tests_local/test_loan_adjustment_tool.py
../.venv/bin/python tests_local/test_chat_service_loan_adjustment.py
../.venv/bin/python tests_local/test_chat_pending_action_schema.py
../.venv/bin/python tests_local/test_loan_suggestion_minimize_burden.py
```
Expected: tất cả in dòng "... passed", không exception. (`test_chat_*` xác nhận contract `LoanAdjustmentResult`/`pending_action` không đổi nên `chat_service` và frontend không bị ảnh hưởng.)

- [ ] **Step 2: Nếu `test_chat_service_loan_adjustment.py` chạm mạng/đỏ vì reasoner**

Mở `backend/tests_local/test_chat_service_loan_adjustment.py`, kiểm tra xem nó có gọi `find_best_reapplication_option` thật không. Nếu có và bị treo do gọi LLM, thêm stub đầu test:

```python
import services.loan_adjustment_reasoner as reasoner
reasoner.propose_candidates = lambda summary: []
```
đặt ngay sau các import, để ép nhánh lưới-cứng. Chạy lại Step 1.

> Nếu test này vốn đã monkeypatch `find_best_reapplication_option` hoặc không kích hoạt nhánh tool, bỏ qua Step 2.

- [ ] **Step 3: Cập nhật trạng thái spec**

Trong `docs/superpowers/specs/2026-06-03-loan-adjustment-soft-rule-design.md`, đổi dòng trạng thái đầu file thành:

```markdown
Trạng thái: Đã triển khai (2026-06-03)
```

Và ghi chú dưới phần "Kiến trúc": khoá rank đã chốt là **thay đổi ít nhất so với đơn gốc** (`_change_magnitude` = tỉ lệ giảm tiền + tỉ lệ tăng kỳ hạn), prob là tiêu chí phụ.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-06-03-loan-adjustment-soft-rule-design.md
git commit -m "docs: đánh dấu spec luật mềm đã triển khai"
```

---

## Self-Review Notes (đã kiểm khi viết plan)

- **Bao phủ spec:** cờ (T1), summarizer (T2), proposer (T4), merger (T3), rationale→context (T5), khoá rank liên-strategy (T6), gộp+verify+bỏ dừng-sớm (T7), test + bất biến #2 (T7 Step 2 `test_empty_llm_matches_grid_only_passing_set`), không đổi contract/frontend (T8 chạy `test_chat_*`).
- **Bất biến an toàn:** mọi ứng viên (LLM/lưới) đều qua `validate_confirmed_values` trong vòng lặp T7; `merge_candidates` chặn `amount > original` và term không hợp lệ trước khi tới `predict`.
- **Nhất quán type:** `Candidate` (reasoner) là kiểu chung cho cả LLM và lưới; `propose_candidates`/`_grid_candidates`/`merge_candidates` đều dùng nó. `_proposal_from_prediction(strategy, rationale)` khớp lời gọi trong T7. `_unified_rank` thay cho `_passing_rank` cũ trong vòng lặp mới (`_passing_rank` để lại nhưng không còn được gọi — KHÔNG xoá theo nguyên tắc "không xoá dead code có sẵn trừ khi được yêu cầu"; nếu reviewer muốn gọn, có thể xoá trong một commit riêng).
- **Không network trong test:** T7 Step 1 stub `reasoner.propose_candidates` trong `_patch_tool` dùng chung.
```
