"""
memory.py - Conversation memory for the RAG pipeline.

V1: sliding window of recent turns + lazy summary buffer for older turns.
Token-aware (rough char-based estimate). Per-session scope.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from models.chat import ChatMessage
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL
from rag.exceptions import LLMError, RAGTimeoutError

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "Bạn là trợ lý tóm tắt hội thoại tín dụng cho hệ thống CreditIntel. "
    "Viết tóm tắt bằng tiếng Việt, tối đa khoảng 500 tokens, tập trung vào: "
    "(1) câu hỏi/quan tâm chính của khách hàng, "
    "(2) dữ kiện đã trao đổi (số tiền, kỳ hạn, DTI, trạng thái đơn), "
    "(3) quyết định / hướng dẫn đã đưa ra. "
    "Không bịa thêm thông tin ngoài hội thoại."
)


@dataclass
class MemoryContext:
    """Result of a memory load - what to pass into the LLM prompt."""

    summary: str | None = None
    recent_messages: list = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ``len(text) // 4``."""
    if not text:
        return 0
    return len(text) // 4


def _to_langchain_messages(rows: list) -> list:
    """Convert ChatMessage rows (oldest -> newest) to LangChain messages."""
    out = []
    for row in rows:
        if row.role == "user":
            out.append(HumanMessage(content=row.content))
        elif row.role == "assistant":
            out.append(AIMessage(content=row.content))
    return out


def _split_window(rows_newest_first: list, budget: int) -> tuple[list, list]:
    """Split rows into older portion and recent token-budget window.

    Returns ``(older_portion_oldest_first, recent_window_oldest_first)``.
    A single message larger than the budget is still kept if it is the most
    recent row, so the latest turn is never dropped.
    """
    used = 0
    recent: list = []
    for row in rows_newest_first:
        cost = _estimate_tokens(row.content)
        if recent and used + cost > budget:
            break
        recent.append(row)
        used += cost

    keep_set = {id(row) for row in recent}
    older = [row for row in rows_newest_first if id(row) not in keep_set]
    older.reverse()
    recent.reverse()
    return older, recent


def _needs_summarize(older: list, session) -> bool:
    """Return true when the older portion has enough uncovered messages."""
    if len(older) < settings.rag_memory_min_messages_to_summarize:
        return False
    last_id = older[-1].id
    return session.summary_covers_until_id != last_id


def _format_messages_for_summary(rows: list) -> str:
    lines = []
    for row in rows:
        prefix = "Khách" if row.role == "user" else "Trợ lý"
        lines.append(f"{prefix}: {row.content}")
    return "\n".join(lines)


def _summarize(db, session, messages_to_summarize: list, previous_summary: str | None) -> str:
    """Call the main LLM to produce an updated summary and persist it."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=OPENROUTER_BASE_URL,
        temperature=0.2,
        max_tokens=settings.rag_memory_summary_max_tokens,
        timeout=settings.rag_llm_timeout_seconds,
        max_retries=settings.rag_llm_max_retries,
    )

    user_block = (
        f"Tóm tắt cũ:\n{previous_summary or '(chưa có)'}\n\n"
        "Các lượt hội thoại mới cần đưa vào tóm tắt:\n"
        f"{_format_messages_for_summary(messages_to_summarize)}\n\n"
        "Hãy viết tóm tắt MỚI bao trùm toàn bộ hội thoại."
    )

    try:
        response = llm.invoke([
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_block},
        ])
    except (openai.APITimeoutError, httpx.TimeoutException) as exc:
        raise RAGTimeoutError(f"Summary LLM timed out: {exc}") from exc
    except (openai.APIConnectionError, openai.APIError) as exc:
        raise LLMError(f"Summary LLM failed: {exc}") from exc

    old_summary = session.summary
    old_covers_until_id = session.summary_covers_until_id
    old_updated_at = session.summary_updated_at
    new_summary = (response.content or "").strip()
    session.summary = new_summary
    session.summary_covers_until_id = messages_to_summarize[-1].id
    session.summary_updated_at = datetime.utcnow()
    try:
        db.commit()
    except SQLAlchemyError as exc:
        if hasattr(db, "rollback"):
            db.rollback()
        session.summary = old_summary
        session.summary_covers_until_id = old_covers_until_id
        session.summary_updated_at = old_updated_at
        raise LLMError(f"Summary persistence failed: {exc}") from exc
    return new_summary


def load_memory(db, session, exclude_message_id: Any | None = None) -> MemoryContext:
    """Build the memory context for a chat session."""
    query = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .filter(ChatMessage.error.is_(False))
    )
    if exclude_message_id is not None:
        query = query.filter(ChatMessage.id != exclude_message_id)

    rows = query.order_by(ChatMessage.created_at.desc()).all()
    if exclude_message_id is not None:
        rows = [row for row in rows if row.id != exclude_message_id]
    if not rows:
        return MemoryContext(summary=session.summary, recent_messages=[])

    older, recent = _split_window(rows, settings.rag_memory_window_token_budget)

    if older and _needs_summarize(older, session):
        try:
            _summarize(db, session, older, session.summary)
        except (LLMError, RAGTimeoutError) as exc:
            logger.warning("Summary update failed, keeping previous summary: %s", exc)

    return MemoryContext(
        summary=session.summary,
        recent_messages=_to_langchain_messages(recent),
    )
