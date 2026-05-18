"""
memory.py - Conversation memory for the RAG pipeline.

V1: sliding window of recent turns + lazy summary buffer for older turns.
Token-aware (rough char-based estimate). Per-session scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
