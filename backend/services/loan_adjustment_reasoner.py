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
