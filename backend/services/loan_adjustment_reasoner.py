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
    except Exception as exc:  # noqa: BLE001
        logger.warning("Loan reasoner unexpected error: %s", exc)
        return []
