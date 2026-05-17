"""
router.py

Intent classification for CreditIntel RAG pipeline.
Classifies user messages into one of six intents, then routes to the
appropriate handler (retrieval strategy + prompt template).

Intents:
    loan_inquiry     – questions about loan amounts, terms, status
    risk_explanation – questions about ML results, risk level, default prob
    policy_question  – questions about CreditIntel policies & processes
    personal_advice  – requests for financial improvement advice
    greeting         – greetings, thanks, small talk
    off_topic        – questions unrelated to credit/loans
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_openai import ChatOpenAI

from core.config import settings
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

# ── Valid intents ─────────────────────────────────────────────────────────────

VALID_INTENTS = frozenset({
    "loan_inquiry",
    "risk_explanation",
    "policy_question",
    "personal_advice",
    "greeting",
    "off_topic",
})

DEFAULT_INTENT = "loan_inquiry"

# Intents that require document retrieval
RETRIEVAL_INTENTS = frozenset({
    "loan_inquiry",
    "risk_explanation",
    "policy_question",
    "personal_advice",
})


# ── Keyword fast-path ────────────────────────────────────────────────────────

_GREETING_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^(xin\s+)?chào(\s+bạn)?[.!?\s]*$",
        r"^hello[.!?\s]*$",
        r"^hi[.!?\s]*$",
        r"^hey[.!?\s]*$",
        r"^(cảm\s+ơn|cám\s+ơn|thank|thanks)[.!?\s]*$",
        r"^(tạm\s+biệt|bye|goodbye)[.!?\s]*$",
        r"^(bạn\s+)?khoẻ\s+không[?.\s]*$",
        r"^(bạn\s+)?là\s+ai[?.\s]*$",
        r"^(giúp\s+với|help|help\s+me)[.!?\s]*$",
    ]
]

_PERSONAL_RISK_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"xác\s+suất\s+vỡ\s+nợ\s+của\s+tôi",
        r"hệ\s+thống\s+đề\s+xuất\s+tôi\s+vay",
        r"điểm\s+mạnh\s+và\s+điểm\s+yếu\s+trong\s+hồ\s+sơ",
        r"mức\s+vay\s+đề\s+xuất\s+.*(thấp\s+hơn|cao\s+hơn).*số\s+tiền\s+tôi\s+xin\s+vay",
        r"với\s+mức\s+thu\s+nhập\s+và\s+nợ\s+hiện\s+tại",
    ]
]

_POLICY_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"auto_rejected",
        r"bị\s+từ\s+chối",
        r"thu\s+nhập\s+.*cao\s+.*vẫn\s+bị\s+từ\s+chối",
        r"awaiting_info",
        r"dti\s+.*an\s+toàn",
        r"low.*medium.*high\s+risk",
        r"hạn\s+mức\s+vay\s+tối\s+đa",
        r"admin\s+xét\s+duyệt",
        r"quyết\s+định\s+của\s+ai",
        r"thông\s+tin\s+cá\s+nhân\s+.*bảo\s+mật",
    ]
]

_OFF_TOPIC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(thời\s+tiết|weather|bóng\s+đá|football|soccer)",
        r"(nấu\s+ăn|recipe|công\s+thức)",
        r"(phim\s+ảnh|movie|film)",
        r"(viết\s+code|programming|python|javascript)",
        r"(bầu\s+trời|\bsao\b|vũ\s+trụ|universe|galaxy)",
        r"(chính\s+trị|politics|bầu\s+cử|election)",
    ]
]


# ── LLM-based classifier ────────────────────────────────────────────────────

_ROUTER_SYSTEM_PROMPT = """Bạn là bộ phân loại ý định (intent classifier) cho trợ lý tín dụng CreditIntel.

Phân loại câu hỏi của khách hàng vào ĐÚNG MỘT trong các intent sau:
- loan_inquiry: hỏi về khoản vay, số tiền, kỳ hạn, trạng thái đơn vay
- risk_explanation: hỏi về kết quả đánh giá rủi ro, xác suất vỡ nợ, risk score, model ML
- policy_question: hỏi về chính sách CreditIntel, quy trình xét duyệt, yêu cầu hồ sơ
- personal_advice: xin tư vấn cải thiện tài chính, giảm DTI, tăng điểm tín dụng
- greeting: chào hỏi, cảm ơn, small talk, hỏi thăm
- off_topic: câu hỏi hoàn toàn không liên quan đến tài chính/tín dụng

Trả lời CHỈ bằng JSON: {"intent": "<intent>", "confidence": <0.0-1.0>}
Không giải thích thêm."""

_classifier_llm = None


def _get_classifier_llm() -> ChatOpenAI:
    global _classifier_llm
    if _classifier_llm is None:
        _classifier_llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0,
            max_tokens=60,
        )
    return _classifier_llm


def classify_intent(question: str, chat_history: list[Any] | None = None) -> str:
    """Classify user question into an intent string.

    Uses keyword fast-path first, then falls back to LLM classification.
    Returns one of the VALID_INTENTS strings; defaults to ``loan_inquiry``
    on any error.
    """
    stripped = question.strip()

    # ── Fast-path: greeting ───────────────────────────────────────────────
    for pattern in _GREETING_PATTERNS:
        if pattern.search(stripped):
            return "greeting"

    # ── Fast-path: domain intents that should be deterministic ────────────
    for pattern in _PERSONAL_RISK_PATTERNS:
        if pattern.search(stripped):
            return "risk_explanation"

    for pattern in _POLICY_PATTERNS:
        if pattern.search(stripped):
            return "policy_question"

    # ── Fast-path: off-topic (only for short messages) ────────────────────
    if len(stripped) < 100:
        for pattern in _OFF_TOPIC_PATTERNS:
            if pattern.search(stripped):
                return "off_topic"

    # ── LLM classification ────────────────────────────────────────────────
    try:
        llm = _get_classifier_llm()
        messages = [
            {"role": "system", "content": _ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": stripped},
        ]
        response = llm.invoke(messages)
        content = response.content.strip()

        # Parse JSON — handle markdown-wrapped JSON as well
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        parsed = json.loads(content)
        intent = parsed.get("intent", DEFAULT_INTENT)

        if intent not in VALID_INTENTS:
            logger.warning("LLM returned invalid intent '%s', falling back", intent)
            return DEFAULT_INTENT

        return intent

    except Exception:
        logger.exception("Intent classification failed, using default")
        return DEFAULT_INTENT


def needs_retrieval(intent: str) -> bool:
    """Return True if the intent requires document retrieval from Qdrant."""
    return intent in RETRIEVAL_INTENTS
