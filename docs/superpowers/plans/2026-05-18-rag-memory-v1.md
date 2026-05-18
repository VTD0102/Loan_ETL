# RAG Memory V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dead `rag/memory.py` and the inline 10-turn history-fetch in `chat_service` with a token-aware sliding window + lazy summary-buffer memory layer per session.

**Architecture:** New `rag/memory.py` exposes `load_memory(db, session) → MemoryContext(summary, recent_messages)`. Token budget controls the recent window; older messages get lazily summarised into `chat_sessions.summary`. `chain.invoke` gains an optional `conversation_summary` parameter wired into the prompt. Summarisation uses the main Gemini LLM with graceful degradation on failure.

**Tech Stack:** SQLAlchemy 2 (Mapped/mapped_column, Postgres on Supabase), LangChain (`langchain_core.messages`, ChatPromptTemplate), `langchain_openai.ChatOpenAI` via OpenRouter, FastAPI, standalone test scripts in `backend/tests_local/`.

**Spec:** [docs/superpowers/specs/2026-05-18-rag-memory-v1-design.md](../specs/2026-05-18-rag-memory-v1-design.md)

---

## File Structure

**New files:**
- `backend/tests_local/test_memory_token_estimation.py`
- `backend/tests_local/test_memory_short_conversation_no_summary.py`
- `backend/tests_local/test_memory_long_conversation_summarizes.py`
- `backend/tests_local/test_memory_skips_summarize_if_already_covered.py`
- `backend/tests_local/test_memory_excludes_error_rows.py`
- `backend/tests_local/test_memory_summarize_failure_graceful.py`
- `backend/tests_local/test_chat_service_uses_memory.py`

**Modified files (full rewrite or surgical edits — noted per task):**
- `backend/rag/memory.py` — full rewrite (currently 43 lines of dead code).
- `backend/models/chat.py` — add 3 columns to `ChatSession`.
- `backend/init_db.py` — append 3 idempotent ALTERs.
- `backend/core/config.py` — add 3 settings.
- `backend/rag/prompts.py` — add `{conversation_summary}` slot.
- `backend/rag/chain.py` — add optional `conversation_summary` param.
- `backend/services/chat_service.py` — replace inline history-fetch with `load_memory`.
- `backend/tests_local/test_chat_service_atomic_save.py` — extend `FakeDB` to handle the memory layer.

Each file keeps one clear responsibility:
- `memory.py` owns conversation memory (window + summarise + persist).
- `chat_service.py` orchestrates the request and stays slim.
- `chain.py` and `prompts.py` only know about the prompt variables, not how memory is computed.

---

## Task 1: Schema migration — add summary columns to `ChatSession`

**Files:**
- Modify: `backend/models/chat.py:1-29` (imports + `ChatSession` class)
- Modify: `backend/init_db.py:5-9` (`_COLUMN_MIGRATIONS`)

- [ ] **Step 1: Add 3 columns to `ChatSession`**

Open `backend/models/chat.py`. The existing imports already include everything we need (`uuid` from line 1, `DateTime`, `Text` from the sqlalchemy import line) — no import changes required. Append three columns inside `ChatSession` after the existing `updated_at` line (around line 21), so the class becomes:

```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_covers_until_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
```

Note: `summary_covers_until_id` is intentionally **not** a `ForeignKey` — see spec rationale (avoid cascade-delete surprises; informational only).

- [ ] **Step 2: Append migrations to `init_db.py`**

Open `backend/init_db.py`. The current `_COLUMN_MIGRATIONS` list is:

```python
_COLUMN_MIGRATIONS = [
    "ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS loan_purpose VARCHAR",
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error BOOLEAN NOT NULL DEFAULT FALSE",
]
```

Replace with:

```python
_COLUMN_MIGRATIONS = [
    "ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS loan_purpose VARCHAR",
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_covers_until_id UUID",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMP",
]
```

- [ ] **Step 3: Verify imports load cleanly**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python -c "from models.chat import ChatSession; print(list(ChatSession.__table__.columns.keys()))"
```

Expected output includes `summary`, `summary_covers_until_id`, `summary_updated_at`:

```
['id', 'user_id', 'title', 'created_at', 'updated_at', 'summary', 'summary_covers_until_id', 'summary_updated_at']
```

And verify migrations list:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python -c "import init_db; print(len(init_db._COLUMN_MIGRATIONS))"
```

Expected: `5`.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/models/chat.py backend/init_db.py
git commit -m "feat: add summary/summary_covers_until_id/summary_updated_at to ChatSession"
```

---

## Task 2: Memory settings in `core/config.py`

**Files:**
- Modify: `backend/core/config.py:8-42`

- [ ] **Step 1: Add 3 new settings**

Open `backend/core/config.py`. After the existing line `rag_qdrant_timeout_seconds: float = 5.0`, add:

```python
    # RAG memory (V1: window + summary buffer)
    rag_memory_window_token_budget: int = 2000
    rag_memory_summary_max_tokens: int = 500
    rag_memory_min_messages_to_summarize: int = 6
```

- [ ] **Step 2: Verify settings load**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python -c "from core.config import settings; print(settings.rag_memory_window_token_budget, settings.rag_memory_summary_max_tokens, settings.rag_memory_min_messages_to_summarize)"
```

Expected: `2000 500 6`.

- [ ] **Step 3: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/core/config.py
git commit -m "feat: add rag_memory_* settings (window budget, summary cap, min messages)"
```

---

## Task 3: Token estimation helper

**Files:**
- Create: `backend/rag/memory.py` (this task adds only the helper + dataclass; later tasks fill in the rest)
- Test: `backend/tests_local/test_memory_token_estimation.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_memory_token_estimation.py`:

```python
"""Verify rough char-based token estimation in rag.memory."""
from rag.memory import _estimate_tokens


def test_empty_string():
    assert _estimate_tokens("") == 0


def test_short_text():
    # "Hello world" is 11 chars → 11 // 4 = 2
    assert _estimate_tokens("Hello world") == 2


def test_long_text():
    text = "a" * 1000
    assert _estimate_tokens(text) == 250


def test_handles_unicode():
    # Vietnamese with diacritics, all characters count by char length
    text = "Xin chào, tôi muốn vay 100 triệu"  # 32 chars
    assert _estimate_tokens(text) == 32 // 4


if __name__ == "__main__":
    test_empty_string()
    test_short_text()
    test_long_text()
    test_handles_unicode()
    print("memory token estimation tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_token_estimation.py
```

Expected: `ImportError: cannot import name '_estimate_tokens'` (current `memory.py` has `load_chat_history`, not `_estimate_tokens`).

- [ ] **Step 3: Rewrite `backend/rag/memory.py` with the helper + dataclass only**

Replace the entire file body:

```python
"""
memory.py — Conversation memory for the RAG pipeline.

V1: sliding window of recent turns + lazy summary buffer for older turns.
Token-aware (rough char-based estimate). Per-session scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryContext:
    """Result of a memory load — what to pass into the LLM prompt."""
    summary: str | None = None
    recent_messages: list = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ``len(text) // 4``.

    Not exact for any specific tokenizer, but consistent and dependency-free.
    Slightly under-counts → conservative trigger for summarization.
    """
    if not text:
        return 0
    return len(text) // 4
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_token_estimation.py
```

Expected: `memory token estimation tests passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/memory.py backend/tests_local/test_memory_token_estimation.py
git commit -m "feat: rag.memory MemoryContext dataclass + char-based token estimate"
```

---

## Task 4: Window selection — short conversations (no summary)

**Files:**
- Modify: `backend/rag/memory.py`
- Test: `backend/tests_local/test_memory_short_conversation_no_summary.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_memory_short_conversation_no_summary.py`:

```python
"""Short conversation under the token budget → no summary triggered."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages):
        self._messages = messages
        self.added = []
        self.committed = 0

    def query(self, model):
        from models.chat import ChatMessage
        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        self.committed += 1


def _msg(role, content, error=False, idx=0):
    base = datetime.utcnow() + timedelta(seconds=idx)
    return SimpleNamespace(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=error,
        created_at=base,
    )


def test_short_conversation_returns_all_messages_no_summary():
    session = SimpleNamespace(id=uuid.uuid4(), summary=None, summary_covers_until_id=None, summary_updated_at=None)
    messages = [
        _msg("user", "Xin chào", idx=0),
        _msg("assistant", "Chào bạn, tôi giúp gì được?", idx=1),
        _msg("user", "Tôi muốn vay 50 triệu", idx=2),
    ]
    db = FakeDB(messages)

    ctx = load_memory(db, session)

    assert ctx.summary is None
    assert len(ctx.recent_messages) == 3
    assert isinstance(ctx.recent_messages[0], HumanMessage)
    assert ctx.recent_messages[0].content == "Xin chào"
    assert isinstance(ctx.recent_messages[1], AIMessage)
    assert ctx.recent_messages[2].content == "Tôi muốn vay 50 triệu"
    assert db.committed == 0, "no commit when no summarization needed"


if __name__ == "__main__":
    test_short_conversation_returns_all_messages_no_summary()
    print("memory short-conversation test passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_short_conversation_no_summary.py
```

Expected: `ImportError: cannot import name 'load_memory'`.

- [ ] **Step 3: Implement `load_memory` (window + no-op when under budget)**

Replace the body of `backend/rag/memory.py` with (keep imports + `MemoryContext` + `_estimate_tokens` from Task 3, add new code):

```python
"""
memory.py — Conversation memory for the RAG pipeline.

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
    """Result of a memory load — what to pass into the LLM prompt."""
    summary: str | None = None
    recent_messages: list = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ``len(text) // 4``.

    Not exact for any specific tokenizer, but consistent and dependency-free.
    Slightly under-counts → conservative trigger for summarization.
    """
    if not text:
        return 0
    return len(text) // 4


def _to_langchain_messages(rows: list) -> list:
    """Convert ChatMessage rows (oldest → newest) to LangChain message objects."""
    out = []
    for row in rows:
        if row.role == "user":
            out.append(HumanMessage(content=row.content))
        elif row.role == "assistant":
            out.append(AIMessage(content=row.content))
    return out


def _split_window(rows_newest_first: list, budget: int) -> tuple[list, list]:
    """Walk newest → oldest, accumulating tokens until budget exceeded.

    Returns (older_portion_oldest_first, recent_window_oldest_first).

    Edge case: a single message larger than the budget is kept anyway —
    we never drop the most recent turn.
    """
    used = 0
    recent: list = []
    for row in rows_newest_first:
        cost = _estimate_tokens(row.content)
        if recent and used + cost > budget:
            break
        recent.append(row)
        used += cost
    # Older portion = everything else, in chronological order.
    keep_set = {id(r) for r in recent}
    older = [r for r in rows_newest_first if id(r) not in keep_set]
    older.reverse()      # oldest → newest
    recent.reverse()     # oldest → newest
    return older, recent


def load_memory(db, session) -> MemoryContext:
    """Build the memory context for a chat session.

    1. Fetch session's non-error ChatMessage rows.
    2. Split into older portion + recent window using the token budget.
    3. (Later tasks) summarize older portion if needed.
    4. Return MemoryContext(summary, recent_messages).
    """
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .filter(ChatMessage.error.is_(False))
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
    if not rows:
        return MemoryContext(summary=session.summary, recent_messages=[])

    older, recent = _split_window(rows, settings.rag_memory_window_token_budget)

    # Task 5 will add the summarization branch here. For now: if there's
    # an older portion but no summary trigger, just drop it (will be added next).
    return MemoryContext(
        summary=session.summary,
        recent_messages=_to_langchain_messages(recent),
    )
```

Notes:
- Uses `.filter(ChatMessage.error.is_(False))` to exclude failed-assistant rows.
- Ordering uses `created_at.desc()` then reverse — matches existing pattern in `chat_service.send`.
- The "drop older portion silently" behaviour is temporary; Task 5 adds summarisation.

- [ ] **Step 4: Run the short-conversation test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_short_conversation_no_summary.py
```

Expected: `memory short-conversation test passed`.

- [ ] **Step 5: Re-run token estimation test (no regression)**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_token_estimation.py
```

Expected: `memory token estimation tests passed`.

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/memory.py backend/tests_local/test_memory_short_conversation_no_summary.py
git commit -m "feat: rag.memory.load_memory with sliding window (no summary yet)"
```

---

## Task 5: Lazy summarisation — long conversations

**Files:**
- Modify: `backend/rag/memory.py` (add `_summarize` + summarise branch in `load_memory`)
- Test: `backend/tests_local/test_memory_long_conversation_summarizes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_memory_long_conversation_summarizes.py`:

```python
"""Long conversation over the token budget → summary updated, recent window kept."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages):
        self._messages = messages
        self.added = []
        self.committed = 0

    def query(self, model):
        from models.chat import ChatMessage
        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        self.committed += 1


def _msg(role, content, idx=0, error=False):
    base = datetime.utcnow() + timedelta(seconds=idx)
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=error,
        created_at=base,
    )


def test_long_conversation_triggers_summary():
    # 20 messages, each 800 chars → 20 * 200 = 4000 tokens total.
    # Budget = 2000 → most recent ~10 in window, ~10 in older portion.
    msgs = []
    for i in range(20):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(_msg(role, "x" * 800, idx=i))

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )
    db = FakeDB(msgs)

    summarize_calls = []

    def fake_summarize(db_arg, session_arg, messages_to_summarize, previous_summary):
        summarize_calls.append({
            "count": len(messages_to_summarize),
            "previous_summary": previous_summary,
        })
        session_arg.summary = "TÓM TẮT MỚI"
        session_arg.summary_covers_until_id = messages_to_summarize[-1].id
        session_arg.summary_updated_at = datetime.utcnow()
        return "TÓM TẮT MỚI"

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    assert len(summarize_calls) == 1, "summarize should run once for over-budget convo"
    assert summarize_calls[0]["previous_summary"] is None
    assert summarize_calls[0]["count"] >= 6, "older portion should have ≥ min messages"
    assert ctx.summary == "TÓM TẮT MỚI"
    assert len(ctx.recent_messages) > 0
    assert len(ctx.recent_messages) < 20, "recent window must be strictly smaller than full history"
    assert db.committed >= 1, "summary update must commit"


if __name__ == "__main__":
    test_long_conversation_triggers_summary()
    print("memory long-conversation summarise test passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_long_conversation_summarizes.py
```

Expected: `AttributeError: module 'rag.memory' has no attribute '_summarize'`.

- [ ] **Step 3: Add `_summarize` + summarise branch to `load_memory`**

Replace `backend/rag/memory.py` with the full final form:

```python
"""
memory.py — Conversation memory for the RAG pipeline.

V1: sliding window of recent turns + lazy summary buffer for older turns.
Token-aware (rough char-based estimate). Per-session scope.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage

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
    """Result of a memory load — what to pass into the LLM prompt."""
    summary: str | None = None
    recent_messages: list = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ``len(text) // 4``."""
    if not text:
        return 0
    return len(text) // 4


def _to_langchain_messages(rows: list) -> list:
    out = []
    for row in rows:
        if row.role == "user":
            out.append(HumanMessage(content=row.content))
        elif row.role == "assistant":
            out.append(AIMessage(content=row.content))
    return out


def _split_window(rows_newest_first: list, budget: int) -> tuple[list, list]:
    """Walk newest → oldest, accumulating tokens until budget exceeded.

    Returns ``(older_portion_oldest_first, recent_window_oldest_first)``.
    A single message larger than the budget is still kept in the window
    so we never drop the most recent turn.
    """
    used = 0
    recent: list = []
    for row in rows_newest_first:
        cost = _estimate_tokens(row.content)
        if recent and used + cost > budget:
            break
        recent.append(row)
        used += cost
    keep_set = {id(r) for r in recent}
    older = [r for r in rows_newest_first if id(r) not in keep_set]
    older.reverse()
    recent.reverse()
    return older, recent


def _needs_summarize(older: list, session) -> bool:
    """True iff there are enough new old-portion messages not yet covered by the summary."""
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
    """Call the main LLM to produce an updated summary; persist + commit.

    Raises LLMError / RAGTimeoutError on upstream failures — caller decides
    whether to swallow.
    """
    # Lazy import to avoid bringing ChatOpenAI into module-load if memory isn't used.
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
        f"Các lượt hội thoại mới cần đưa vào tóm tắt:\n"
        f"{_format_messages_for_summary(messages_to_summarize)}\n\n"
        f"Hãy viết tóm tắt MỚI bao trùm toàn bộ hội thoại."
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

    new_summary = (response.content or "").strip()
    session.summary = new_summary
    session.summary_covers_until_id = messages_to_summarize[-1].id
    session.summary_updated_at = datetime.utcnow()
    db.commit()
    return new_summary


def load_memory(db, session) -> MemoryContext:
    """Build the memory context for a chat session.

    1. Fetch session's non-error ChatMessage rows.
    2. Split into older portion + recent window via the token budget.
    3. Summarize older portion if needed (lazy, graceful on failure).
    4. Return MemoryContext.
    """
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .filter(ChatMessage.error.is_(False))
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
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
```

- [ ] **Step 4: Run the long-conversation test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_long_conversation_summarizes.py
```

Expected: `memory long-conversation summarise test passed`.

- [ ] **Step 5: Run all memory tests so far**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_token_estimation.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_short_conversation_no_summary.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_long_conversation_summarizes.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/memory.py backend/tests_local/test_memory_long_conversation_summarizes.py
git commit -m "feat: lazy summarisation in rag.memory.load_memory"
```

---

## Task 6: Skip-summary when already covered

**Files:**
- Test: `backend/tests_local/test_memory_skips_summarize_if_already_covered.py` (no production code change — verifies behaviour added in Task 5)

- [ ] **Step 1: Write the test**

Create `backend/tests_local/test_memory_skips_summarize_if_already_covered.py`:

```python
"""If session.summary_covers_until_id already equals the last older-portion message,
no LLM call should be made."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages):
        self._messages = messages
        self.committed = 0

    def query(self, model):
        from models.chat import ChatMessage
        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        self.committed += 1


def _msg(role, content, idx=0):
    base = datetime.utcnow() + timedelta(seconds=idx)
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=False,
        created_at=base,
    )


def test_no_summary_call_when_already_covered():
    msgs = [_msg("user" if i % 2 == 0 else "assistant", "y" * 800, idx=i) for i in range(20)]

    # The "older portion" will be the oldest ones (depends on budget).
    # Compute what the last older-message id WILL be by running with a fake summarizer first.
    captured = {}

    def fake_summarize_first_run(db, session, messages_to_summarize, previous_summary):
        captured["last_id"] = messages_to_summarize[-1].id
        session.summary = "first"
        session.summary_covers_until_id = messages_to_summarize[-1].id
        session.summary_updated_at = datetime.utcnow()
        return "first"

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize_first_run
    try:
        # Priming run — populates session.summary_covers_until_id.
        load_memory(FakeDB(msgs), session)
    finally:
        memory_mod._summarize = original

    assert session.summary_covers_until_id == captured["last_id"]

    # Second run on the same session + same messages → no new summary call.
    second_calls = []

    def fake_summarize_second_run(*args, **kwargs):
        second_calls.append(1)
        return "should not run"

    memory_mod._summarize = fake_summarize_second_run
    try:
        ctx = load_memory(FakeDB(msgs), session)
    finally:
        memory_mod._summarize = original

    assert second_calls == [], "summarize must NOT be called when summary already covers"
    assert ctx.summary == "first"


if __name__ == "__main__":
    test_no_summary_call_when_already_covered()
    print("memory skip-when-covered test passed")
```

- [ ] **Step 2: Run**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_skips_summarize_if_already_covered.py
```

Expected: `memory skip-when-covered test passed`.

If this FAILS, the bug is in `_needs_summarize` (Task 5). Re-read `_needs_summarize` and fix; do not change the test.

- [ ] **Step 3: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_memory_skips_summarize_if_already_covered.py
git commit -m "test: rag.memory skips summarise when summary_covers_until_id matches"
```

---

## Task 7: Exclude error rows from memory

**Files:**
- Test: `backend/tests_local/test_memory_excludes_error_rows.py` (no production code change — verifies the `.filter(ChatMessage.error.is_(False))` from Task 5)

- [ ] **Step 1: Write the test**

Create `backend/tests_local/test_memory_excludes_error_rows.py`:

```python
"""Rows with error=True must not appear in the window OR in summarize input."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items
        self._error_filter_active = False

    def filter(self, *args, **kwargs):
        # Inspect the SQLAlchemy clause; if it references error.is_(False),
        # drop error=True rows.
        for arg in args:
            text = str(arg)
            if "error" in text.lower() and "false" in text.lower():
                self._items = [m for m in self._items if not getattr(m, "error", False)]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages):
        self._messages = messages
        self.committed = 0

    def query(self, model):
        from models.chat import ChatMessage
        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        self.committed += 1


def _msg(role, content, idx=0, error=False):
    base = datetime.utcnow() + timedelta(seconds=idx)
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=error,
        created_at=base,
    )


def test_error_rows_excluded_from_window_and_summary():
    msgs = [
        _msg("user", "câu hỏi đầu", idx=0),
        _msg("assistant", "câu trả lời 1", idx=1),
        _msg("user", "câu hỏi 2", idx=2),
        _msg("assistant", "ERR PLACEHOLDER", idx=3, error=True),  # <-- must be excluded
        _msg("user", "câu hỏi 3", idx=4),
        _msg("assistant", "câu trả lời 3", idx=5),
    ]

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )
    db = FakeDB(msgs)

    captured = {}
    def fake_summarize(db, sess, to_summarize, prev):
        captured["to_summarize"] = list(to_summarize)
        return "stub"

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    # None of the recent_messages should be the error row
    contents = [m.content for m in ctx.recent_messages]
    assert "ERR PLACEHOLDER" not in contents, "error row leaked into window"

    # Whatever was passed to summarize must also not contain the error row
    if "to_summarize" in captured:
        assert all(m.content != "ERR PLACEHOLDER" for m in captured["to_summarize"]), \
            "error row leaked into summarise input"


if __name__ == "__main__":
    test_error_rows_excluded_from_window_and_summary()
    print("memory excludes-error-rows test passed")
```

- [ ] **Step 2: Run**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_excludes_error_rows.py
```

Expected: `memory excludes-error-rows test passed`.

- [ ] **Step 3: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_memory_excludes_error_rows.py
git commit -m "test: rag.memory excludes error=True rows from window + summary"
```

---

## Task 8: Graceful degradation when summary LLM fails

**Files:**
- Test: `backend/tests_local/test_memory_summarize_failure_graceful.py`

- [ ] **Step 1: Write the test**

Create `backend/tests_local/test_memory_summarize_failure_graceful.py`:

```python
"""If _summarize raises LLMError/RAGTimeoutError, load_memory keeps old summary + window."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.exceptions import LLMError
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages):
        self._messages = messages
        self.committed = 0

    def query(self, model):
        from models.chat import ChatMessage
        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        self.committed += 1


def _msg(role, content, idx=0):
    base = datetime.utcnow() + timedelta(seconds=idx)
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=False,
        created_at=base,
    )


def test_summary_llm_failure_returns_old_summary():
    msgs = [_msg("user" if i % 2 == 0 else "assistant", "z" * 800, idx=i) for i in range(20)]
    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary="OLD SUMMARY",
        summary_covers_until_id=None,
        summary_updated_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db = FakeDB(msgs)

    def fake_summarize(*args, **kwargs):
        raise LLMError("openrouter down")

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    assert ctx.summary == "OLD SUMMARY", "old summary must be preserved on failure"
    assert len(ctx.recent_messages) > 0, "window must still be returned"
    assert session.summary == "OLD SUMMARY", "session.summary must not be cleared"


if __name__ == "__main__":
    test_summary_llm_failure_returns_old_summary()
    print("memory summary-failure-graceful test passed")
```

- [ ] **Step 2: Run**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_summarize_failure_graceful.py
```

Expected: `memory summary-failure-graceful test passed`.

- [ ] **Step 3: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_memory_summarize_failure_graceful.py
git commit -m "test: rag.memory graceful degradation on summary LLM failure"
```

---

## Task 9: Prompt template gets `{conversation_summary}` slot

**Files:**
- Modify: `backend/rag/prompts.py`

- [ ] **Step 1: Update the prompt**

Open `backend/rag/prompts.py`. The current `SYSTEM_TEMPLATE` ends with the `═══════ TÀI LIỆU LIÊN QUAN ═══════` block. Add a new section right BEFORE that block. The new template:

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

SYSTEM_TEMPLATE = """Bạn là trợ lý tín dụng CreditIntel, chuyên giải thích kết quả đánh giá rủi ro \
và tư vấn tài chính cho khách hàng. Tuân thủ nghiêm ngặt các quy tắc:

1. LUÔN trả lời bằng tiếng Việt, giọng điệu thân thiện nhưng chuyên nghiệp.
2. Chỉ trả lời các câu hỏi liên quan đến: khoản vay, rủi ro tín dụng, chỉ số tài chính cá nhân, \
chính sách CreditIntel. Từ chối lịch sự các câu hỏi khác.
3. KHÔNG BAO GIỜ hứa sẽ phê duyệt đơn vay. Kết quả cuối cùng do Admin quyết định.
4. KHÔNG tiết lộ thông tin của khách hàng khác, cấu trúc model nội bộ, hay thao tác với DB.
5. Khi trích dẫn thông tin, ghi rõ nguồn bằng tên file, ví dụ: "(nguồn: policy.md)".
6. Nếu không chắc chắn, nói rõ "Tôi không có đủ thông tin để trả lời chính xác".

═══════ THÔNG TIN CÁ NHÂN ═══════
Tên khách hàng: {user_display_name}
{personalization_instructions}

═══════ HƯỚNG DẪN THEO Ý ĐỊNH ═══════
{intent_instructions}

═══════ THÔNG TIN HỒ SƠ KHÁCH HÀNG ═══════
{user_context}

═══════ TÓM TẮT HỘI THOẠI TRƯỚC ĐÓ ═══════
{conversation_summary}

═══════ TÀI LIỆU LIÊN QUAN ═══════
{context}
"""

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_TEMPLATE),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}"),
])
```

- [ ] **Step 2: Verify prompt loads with the new variable**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python -c "from rag.prompts import chat_prompt; print(sorted(chat_prompt.input_variables))"
```

Expected output (alphabetical):

```
['chat_history', 'context', 'conversation_summary', 'intent_instructions', 'personalization_instructions', 'question', 'user_context', 'user_display_name']
```

- [ ] **Step 3: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/prompts.py
git commit -m "feat: add {conversation_summary} placeholder to chat prompt"
```

---

## Task 10: `chain.invoke` accepts `conversation_summary`

**Files:**
- Modify: `backend/rag/chain.py:54-136` (invoke signature + prompt payload)
- Modify: `backend/tests_local/test_rag_routing_guardrail_personalized.py` (verify the new param flows through)

- [ ] **Step 1: Update `invoke` to accept + pass-through `conversation_summary`**

Open `backend/rag/chain.py`. Replace `invoke()` body (currently lines 54-136) with:

```python
def invoke(
    question: str,
    user_context: str,
    chat_history: list,
    personalization: "PersonalizationContext | None" = None,
    conversation_summary: str | None = None,
) -> dict:
    """Full RAG pipeline: guardrail → route → retrieve → personalise → LLM → guardrail.

    Parameters
    ----------
    question : str
        The user's message.
    user_context : str
        Pre-built textual context from ``context_builder.build_user_context``.
    chat_history : list
        LangChain message objects for the recent conversation window.
    personalization : PersonalizationContext, optional
        Pre-built personalization context. If None, defaults are used.
    conversation_summary : str, optional
        Running summary of older turns (from rag.memory.load_memory). If None,
        the prompt slot is rendered as "(không có)".
    """
    # ── Step 1: Input guardrail ───────────────────────────────────────────
    input_check = check_input(question)
    if not input_check.passed:
        logger.info("Input guardrail blocked message: %s", input_check.reason)
        return {
            "answer": input_check.reason,
            "source_documents": [],
            "intent": "blocked",
            "blocked": True,
        }

    # ── Step 2: Intent routing ────────────────────────────────────────────
    intent = classify_intent(question, chat_history)
    logger.info("Classified intent: %s", intent)

    # ── Step 3: Retrieval (intent-aware) ──────────────────────────────────
    documents: list[Any] = []
    if needs_retrieval(intent):
        try:
            documents = _retrieve_documents(question)
        except RetrievalError:
            logger.exception("Retrieval failed, continuing without docs")
            documents = []
        except RAGTimeoutError:
            logger.warning("Retrieval timed out, continuing without docs")
            documents = []

    # ── Step 4: Personalization (caller-provided) ─────────────────────────
    if personalization is None:
        personalization = PersonalizationContext()
    intent_instructions = get_intent_instructions(intent)

    # ── Step 5: LLM call ─────────────────────────────────────────────────
    try:
        answer = get_chain().invoke({
            "question": question,
            "user_context": user_context,
            "context": _format_documents(documents),
            "chat_history": chat_history,
            "user_display_name": personalization.user_display_name,
            "personalization_instructions": personalization.tone_instructions,
            "intent_instructions": intent_instructions,
            "conversation_summary": conversation_summary or "(không có)",
        })
    except (openai.APITimeoutError, httpx.TimeoutException) as exc:
        raise RAGTimeoutError(f"LLM call timed out: {exc}") from exc
    except (openai.APIConnectionError, openai.APIError) as exc:
        raise LLMError(f"LLM call failed: {exc}") from exc

    # ── Step 6: Output guardrail ──────────────────────────────────────────
    output_check = check_output(answer)
    if output_check.sanitized_text is not None:
        logger.info("Output guardrail modified response (reason=%s)", output_check.reason)
        answer = output_check.sanitized_text

    return {
        "answer": answer,
        "source_documents": documents,
        "intent": intent,
    }
```

- [ ] **Step 2: Update `test_rag_routing_guardrail_personalized.py` to also pass + verify `conversation_summary`**

Open `backend/tests_local/test_rag_routing_guardrail_personalized.py`. Find `test_chain_injects_personalization_into_prompt_payload` and replace it with:

```python
def test_chain_injects_personalization_into_prompt_payload():
    captured_payload = {}

    class FakeChain:
        def invoke(self, payload):
            captured_payload.update(payload)
            return "Xin chào anh Minh"

    class FakePersonalization:
        user_display_name = "Minh"
        tone_instructions = "Giọng điệu: kiểm thử cá nhân hóa."

    original_get_chain = chain.get_chain
    try:
        chain.get_chain = lambda: FakeChain()

        result = chain.invoke(
            "Xin chào", "ctx", [],
            personalization=FakePersonalization(),
            conversation_summary="Khách hỏi vay 50tr trước đó.",
        )

        assert result["intent"] == "greeting"
        assert captured_payload["user_display_name"] == "Minh"
        assert "kiểm thử cá nhân hóa" in captured_payload["personalization_instructions"]
        assert captured_payload["context"] == "Không tìm thấy tài liệu liên quan trong kho kiến thức."
        assert captured_payload["conversation_summary"] == "Khách hỏi vay 50tr trước đó."
    finally:
        chain.get_chain = original_get_chain


def test_chain_renders_no_summary_placeholder_when_missing():
    captured_payload = {}

    class FakeChain:
        def invoke(self, payload):
            captured_payload.update(payload)
            return "ok"

    original_get_chain = chain.get_chain
    try:
        chain.get_chain = lambda: FakeChain()
        chain.invoke("Tôi cần trợ giúp về hồ sơ vay", "ctx", [])
    finally:
        chain.get_chain = original_get_chain

    assert captured_payload["conversation_summary"] == "(không có)"
```

Add the new test name to the `if __name__ == "__main__":` block at the bottom of the file:

```python
if __name__ == "__main__":
    test_off_topic_routing_skips_retrieval()
    test_greeting_routing_skips_retrieval()
    test_vietnamese_prompt_injection_is_blocked_before_rag()
    test_privacy_probe_is_blocked_before_rag()
    test_chain_injects_personalization_into_prompt_payload()
    test_chain_renders_no_summary_placeholder_when_missing()
    print("RAG routing, guardrail, and personalization-focused checks passed.")
```

- [ ] **Step 3: Run the routing test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
```

Expected: `RAG routing, guardrail, and personalization-focused checks passed.`.

- [ ] **Step 4: Run the chain fallback test (no regression — `chain.invoke` call is still 3-arg)**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
```

Expected: `RAG retriever fallback test passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chain.py backend/tests_local/test_rag_routing_guardrail_personalized.py
git commit -m "feat: chain.invoke accepts conversation_summary (renders placeholder if absent)"
```

---

## Task 11: `chat_service` uses `load_memory`

**Files:**
- Modify: `backend/services/chat_service.py:34-99` (inside `send`)
- Modify: `backend/tests_local/test_chat_service_atomic_save.py` (extend FakeDB to handle memory layer)
- Test: `backend/tests_local/test_chat_service_uses_memory.py`

- [ ] **Step 1: Write the new integration test**

Create `backend/tests_local/test_chat_service_uses_memory.py`:

```python
"""chat_service.send must call rag.memory.load_memory and pass summary to _rag_invoke."""
import uuid
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession
from rag.memory import MemoryContext


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def scalar(self):
        return 0

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, user):
        self._user = user
        self.added = []
        self.committed = 0

    def query(self, model):
        if getattr(model, "__name__", None) == "User":
            return FakeQuery([self._user])
        if getattr(model, "__name__", None) == "LoanApplication":
            return FakeQuery([])
        if getattr(model, "__name__", None) == "ChatMessage":
            return FakeQuery([])
        if getattr(model, "__name__", None) == "ChatSession":
            return FakeQuery([])
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def flush(self):
        for obj in self.added:
            if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self):
        self.committed += 1


def test_chat_service_passes_summary_and_window_to_rag():
    user = SimpleNamespace(id=uuid.uuid4(), email="b@b.com", username="Mai")
    db = FakeDB(user)

    rag_call = {}

    def fake_invoke(question, context, chat_history, **kwargs):
        rag_call["question"] = question
        rag_call["chat_history"] = list(chat_history)
        rag_call["conversation_summary"] = kwargs.get("conversation_summary")
        return {"answer": "OK", "source_documents": []}

    def fake_load_memory(db, session):
        return MemoryContext(
            summary="Khách đã hỏi vay 30tr hôm trước.",
            recent_messages=[HumanMessage(content="câu hỏi cũ")],
        )

    def fake_build_user_context(db, user_id):
        return "ctx"

    original_invoke = chat_service._rag_invoke
    original_load_memory = chat_service.load_memory
    original_ctx = chat_service.build_user_context
    chat_service._rag_invoke = fake_invoke
    chat_service.load_memory = fake_load_memory
    chat_service.build_user_context = fake_build_user_context
    try:
        result = chat_service.send(db, "b@b.com", "Tôi muốn vay 50tr")
    finally:
        chat_service._rag_invoke = original_invoke
        chat_service.load_memory = original_load_memory
        chat_service.build_user_context = original_ctx

    assert result["response"] == "OK"
    assert rag_call["conversation_summary"] == "Khách đã hỏi vay 30tr hôm trước."
    assert len(rag_call["chat_history"]) == 1
    assert rag_call["chat_history"][0].content == "câu hỏi cũ"


if __name__ == "__main__":
    test_chat_service_passes_summary_and_window_to_rag()
    print("chat_service uses memory test passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_uses_memory.py
```

Expected: failure (`AttributeError: module 'services.chat_service' has no attribute 'load_memory'`).

- [ ] **Step 3: Refactor `send` to use `load_memory`**

Open `backend/services/chat_service.py`. Add an import to the top-level imports (after the existing `from rag.personalizer import build_personalization`):

```python
from rag.memory import load_memory
```

Find the body of `send` and replace the inline history-fetch + chat_history construction (currently the block that fetches `history_rows` and builds `chat_history`) with a single `load_memory` call. The full new `send` body:

```python
def send(db: Session, user_email: str, payload_message: str, session_id: Any = None) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _enforce_rate_limit(db, user.id)
    app = _ensure_latest_application_has_prediction(db, user.id)
    session = _get_or_create_session(db, user.id, session_id)

    # 1) Persist the user message before invoking RAG so it survives any
    #    upstream failure.
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=payload_message,
    )
    db.add(user_message)
    if not session.title:
        session.title = payload_message.strip()[:80]
    db.commit()

    # 2) Build memory context (window + lazy summary) for the LLM call.
    memory = load_memory(db, session)

    error_flag = False
    sources: list[dict[str, Any]] = []
    try:
        context = build_user_context(db, user.id)
        personalization = build_personalization(user, app)
        response_payload = _rag_invoke(
            payload_message, context, memory.recent_messages,
            personalization=personalization,
            conversation_summary=memory.summary,
        )
        answer = response_payload.get("answer") or ""
        sources = _extract_sources(response_payload.get("source_documents", []))
        if not answer:
            answer = _RAG_ERROR_MESSAGE
            error_flag = True
            sources = []
    except RAGError:
        logger.exception("RAG pipeline failed")
        answer = _RAG_ERROR_MESSAGE
        error_flag = True

    # 3) Save the assistant turn (success or error placeholder).
    db.add(ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources=sources,
        error=error_flag,
    ))
    session.updated_at = datetime.utcnow()
    db.commit()

    if error_flag:
        raise HTTPException(status_code=503, detail=answer)

    return {
        "response": answer,
        "session_id": session.id,
        "sources": sources,
    }
```

Key diff from the previous version:
- Imports `load_memory` at top level (so `chat_service.load_memory` is patchable).
- The block that fetched `history_rows`, ran the `[r for r in history_rows if ...]` filter, and converted to `HumanMessage`/`AIMessage` is **gone**.
- `memory.recent_messages` is passed as `chat_history`.
- `memory.summary` is passed as the new `conversation_summary=` kwarg.

- [ ] **Step 4: Update the existing atomic-save test to mock `load_memory`**

Open `backend/tests_local/test_chat_service_atomic_save.py`. In the body of `test_user_message_persists_when_rag_fails`, just before `chat_service._rag_invoke = fake_invoke`, add:

```python
    def fake_load_memory(db, session):
        from rag.memory import MemoryContext
        return MemoryContext(summary=None, recent_messages=[])

    original_load_memory = chat_service.load_memory
    chat_service.load_memory = fake_load_memory
```

And in the `finally:` block, restore it:

```python
    finally:
        chat_service._rag_invoke = original_invoke
        chat_service.build_user_context = original_ctx
        chat_service.load_memory = original_load_memory
```

This keeps the atomic-save test focused on the RAGError path without engaging the real memory layer.

- [ ] **Step 5: Run all chat / memory tests**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_uses_memory.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_atomic_save.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_legacy_application_payload.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_token_estimation.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_short_conversation_no_summary.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_long_conversation_summarizes.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_skips_summarize_if_already_covered.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_excludes_error_rows.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_summarize_failure_graceful.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
```

Expected: all 11 print their pass message.

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/services/chat_service.py backend/tests_local/test_chat_service_uses_memory.py backend/tests_local/test_chat_service_atomic_save.py
git commit -m "feat: chat_service.send uses rag.memory.load_memory (window + summary)"
```

---

## Task 12: Final sweep

- [ ] **Step 1: Run every standalone RAG/chat test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_memory_*.py tests_local/test_rag_*.py tests_local/test_chat_*.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" 2>&1 | tail -1
done
```

Expected: every line ends with a `*** passed` message. If any test prints a traceback ending in `AssertionError`, stop and fix before moving on.

- [ ] **Step 2: No commit (verification only).**

---

## Acceptance criteria (recap from spec)

- [x] `rag/memory.py` rewritten — `load_memory(db, session) → MemoryContext`, `_summarize(...)`, `_estimate_tokens(...)`, `MemoryContext` dataclass.
- [x] `ChatSession` has `summary`, `summary_covers_until_id`, `summary_updated_at` columns + idempotent migrations.
- [x] `chat_service.send` calls `load_memory`, no inline history-fetch.
- [x] Short conversation: no summarisation, no LLM call from memory.
- [x] Long conversation: summary populated, recent window preserved.
- [x] LLM failure during summarisation: graceful (old summary + window, no exception).
- [x] `error=True` rows excluded from window AND from summary input.
- [x] `chain.invoke` accepts `conversation_summary` (defaults to `"(không có)"`).
- [x] Prompt template includes `{conversation_summary}` block.
- [x] All new + existing standalone tests pass.
