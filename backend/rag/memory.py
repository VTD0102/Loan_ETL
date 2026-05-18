"""
memory.py - Conversation memory for the RAG pipeline.

V1: sliding window of recent turns + lazy summary buffer for older turns.
Token-aware (rough char-based estimate). Per-session scope.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage

from core.config import settings
from models.chat import ChatMessage

logger = logging.getLogger(__name__)


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


def load_memory(db, session) -> MemoryContext:
    """Build the memory context for a chat session."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .filter(ChatMessage.error.is_(False))
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
    rows = sorted(rows, key=lambda row: row.created_at, reverse=True)
    if not rows:
        return MemoryContext(summary=session.summary, recent_messages=[])

    _older, recent = _split_window(rows, settings.rag_memory_window_token_budget)
    return MemoryContext(
        summary=session.summary,
        recent_messages=_to_langchain_messages(recent),
    )
