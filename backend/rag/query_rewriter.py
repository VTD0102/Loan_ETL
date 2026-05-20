"""Conversation-aware query rewriting for RAG retrieval.

The rewritten query is only for retrieval. Generation still uses the user's
original message.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from core.config import settings
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

MAX_REWRITE_CHARS = 500
MAX_HISTORY_MESSAGES = 6

_REWRITE_SYSTEM_PROMPT = (
    "Bạn viết lại câu hỏi truy xuất tài liệu cho hệ thống RAG tín dụng CreditIntel. "
    "Hãy biến câu hỏi hiện tại thành một câu hỏi độc lập bằng tiếng Việt. "
    "Chỉ dùng thông tin có trong câu hỏi hiện tại, tóm tắt hội thoại và các lượt gần đây. "
    "Không bịa thêm trạng thái hồ sơ, số tiền, DTI, điểm tín dụng hoặc kết quả duyệt. "
    "Nếu câu hỏi đã độc lập, giữ nguyên hoặc chỉnh rất nhẹ. "
    "Chỉ trả về một câu truy vấn, không giải thích, không nhãn."
)

_rewrite_llm = None


def _get_rewrite_llm():
    global _rewrite_llm
    if _rewrite_llm is None:
        _rewrite_llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0.0,
            timeout=settings.rag_llm_timeout_seconds,
            max_retries=settings.rag_llm_max_retries,
        )
    return _rewrite_llm


def rewrite_for_retrieval(
    question: str,
    chat_history: list,
    conversation_summary: str | None = None,
) -> str:
    """Return a standalone retrieval query, falling back to the original question."""
    original = str(question or "").strip()
    if not original:
        return original
    if not _has_conversation_context(chat_history, conversation_summary):
        return original

    try:
        response = _get_rewrite_llm().invoke(
            [
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_rewrite_prompt(
                        original,
                        chat_history,
                        conversation_summary,
                    ),
                },
            ]
        )
    except Exception as exc:
        logger.warning("Query rewrite failed, using original question: %s", exc)
        return original

    rewritten = _clean_rewrite(getattr(response, "content", response))
    return rewritten or original


def _has_conversation_context(chat_history: list, conversation_summary: str | None) -> bool:
    return bool((conversation_summary or "").strip()) or bool(chat_history)


def _build_rewrite_prompt(
    question: str,
    chat_history: list,
    conversation_summary: str | None,
) -> str:
    summary = (conversation_summary or "").strip() or "(không có)"
    recent = _format_chat_history(chat_history)
    return (
        f"Tóm tắt hội thoại:\n{summary}\n\n"
        f"Các lượt gần đây:\n{recent}\n\n"
        f"Câu hỏi hiện tại:\n{question}\n\n"
        "Viết lại thành một câu truy vấn độc lập để tìm tài liệu liên quan."
    )


def _format_chat_history(chat_history: list) -> str:
    if not chat_history:
        return "(không có)"

    lines = []
    for message in chat_history[-MAX_HISTORY_MESSAGES:]:
        role = _message_role_label(message)
        content = str(getattr(message, "content", message)).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(không có)"


def _message_role_label(message: Any) -> str:
    class_name = message.__class__.__name__.lower()
    if "human" in class_name:
        return "Khách"
    if "ai" in class_name:
        return "Trợ lý"
    return "Tin nhắn"


def _clean_rewrite(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if "\n" in text:
        return ""
    if len(text) > MAX_REWRITE_CHARS:
        return ""
    lowered = text.lower()
    label_prefixes = (
        "query:",
        "retrieval query:",
        "rewritten query:",
        "câu truy vấn:",
        "cau truy van:",
    )
    if lowered.startswith(label_prefixes):
        return ""
    return " ".join(text.split())
