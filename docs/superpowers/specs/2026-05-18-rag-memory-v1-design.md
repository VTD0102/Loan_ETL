# RAG Memory V1 — Design

**Date**: 2026-05-18
**Status**: Approved (pending user review)
**Scope**: `backend/rag/memory.py`, `backend/rag/prompts.py`, `backend/services/chat_service.py`, `backend/models/chat.py`, `backend/core/config.py`

## Mục tiêu

Thay layer "memory" cụt hiện tại (sliding window 10 turn hard-coded trong `chat_service.send`) bằng một module memory đúng nghĩa: short-term window + summary buffer cho các turn cũ. Token-aware, lazy summarize, per-session scope.

V1 giải 2 vấn đề:
1. `backend/rag/memory.py` là dead code — không ai import.
2. Cứ > 10 turns thì các turn cũ bị drop hoàn toàn → mất ngữ cảnh hội thoại dài.

## Phạm vi không bao gồm (V2+)

- Fact extraction từ hội thoại ("khách quan tâm DTI", "khách prefer 36 tháng").
- Cross-session memory (recall ngữ cảnh từ session khác của cùng user).
- Episodic / semantic memory (vector search trên chat history).
- Background / async summarization.
- Cross-user memory.

---

## Architecture

### Module mới `backend/rag/memory.py`

Replace toàn bộ file hiện tại (dead code) với:

```python
"""
memory.py — Conversation memory for the RAG pipeline.

V1: sliding window of recent turns + lazy summary buffer for older turns.
Token-aware (rough char-based estimate). Per-session scope.
"""
from dataclasses import dataclass

@dataclass
class MemoryContext:
    summary: str | None              # Running summary of older turns (or None)
    recent_messages: list            # LangChain message objects within the token budget


def load_memory(db, session) -> MemoryContext:
    """Load memory for the given chat session.

    Algorithm:
    1. Fetch the session's ChatMessage rows (excluding error rows).
    2. Walk newest → oldest, accumulating estimated tokens until the window
       budget is reached.
    3. If older messages exist beyond the window AND the existing summary
       doesn't already cover them → call _summarize() to refresh the summary
       and persist it on chat_sessions.summary.
    4. Return MemoryContext(summary, recent_messages).

    The recent_messages list is returned in oldest → newest order, matching
    the existing chat_history convention in chain.invoke().
    """


def _estimate_tokens(text: str) -> int:
    """Rough estimate: len(text) // 4. Good enough for budgeting.

    Not exact for Gemini's tokenizer, but consistent and dependency-free.
    Errs on the small side (we under-count), which makes us slightly
    conservative on summary trigger.
    """


def _summarize(db, session, messages_to_summarize: list, previous_summary: str | None) -> str:
    """LLM call to produce a new summary covering `messages_to_summarize`.

    Builds an incremental prompt: "Given the existing summary [previous_summary]
    and these new turns [messages_to_summarize], produce an updated summary
    of the whole conversation so far in Vietnamese, max 500 tokens."

    Persists the result to session.summary + summary_updated_at +
    summary_covers_until_id.

    Uses the main LLM (get_chain()'s ChatOpenAI) directly — no chain composition
    needed. Catches openai.APIError / httpx.TimeoutException, wraps in LLMError
    (consistent with rag.exceptions hierarchy from earlier task).
    """
```

### Schema migration

`backend/models/chat.py` — add 3 columns to `ChatSession`:

```python
class ChatSession(Base):
    # ... existing columns ...
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_covers_until_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_messages.id"), nullable=True,
    )
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

`backend/init_db.py` — append 3 idempotent ALTERs to `_COLUMN_MIGRATIONS`:

```python
"ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT",
"ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_covers_until_id UUID",
"ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMP",
```

(Foreign key constraint between `chat_sessions.summary_covers_until_id` and `chat_messages.id` is intentionally **not** enforced at the DB level — ALTER would require a follow-up step and risks cascade-delete surprises. The relationship is informational; application code treats it as "the latest message ID covered by the current summary.")

### Settings (`backend/core/config.py`)

Add after the existing `rag_qdrant_timeout_seconds` setting:

```python
# RAG memory (V1: window + summary buffer)
rag_memory_window_token_budget: int = 2000      # max tokens kept verbatim in recent window
rag_memory_summary_max_tokens: int = 500        # cap on summary length
rag_memory_min_messages_to_summarize: int = 6   # don't summarize if older portion < this
```

### Prompt template (`backend/rag/prompts.py`)

Add a `{conversation_summary}` placeholder to `chat_prompt` template, rendered above `{chat_history}`:

```
Tóm tắt hội thoại trước đó (nếu có):
{conversation_summary}

Các lượt gần đây:
{chat_history}
```

If `conversation_summary` is empty/None → render `(không có)` placeholder.

### `chain.invoke` signature change

Add one optional parameter:

```python
def invoke(
    question: str,
    user_context: str,
    chat_history: list,
    personalization: PersonalizationContext | None = None,
    conversation_summary: str | None = None,    # ← new
) -> dict:
```

Pass `conversation_summary` straight into the prompt payload alongside other variables. Default `None` → render as empty string in the prompt.

### `chat_service.send` integration

Replace the inline history-fetch block (currently builds `history_rows` and `chat_history` directly from `ChatMessage`) with:

```python
from rag.memory import load_memory

# ... inside send() ...
memory = load_memory(db, session)
chat_history = memory.recent_messages

response_payload = _rag_invoke(
    payload_message, context, chat_history,
    personalization=personalization,
    conversation_summary=memory.summary,
)
```

`load_memory` does the summarize-if-needed work internally; `chat_service` doesn't need to know about thresholds or summarization mechanics.

---

## Algorithm details

### Token budgeting

For each message row: `tokens = _estimate_tokens(row.content)`. Sum from newest backwards until adding the next message would exceed `rag_memory_window_token_budget`. The messages before that cutoff = "older portion", the messages after = "recent window".

Edge cases:
- If the recent window includes ALL messages (short conversation) → no summarization, return `MemoryContext(summary=None or session.summary if it exists, recent_messages=all)`.
- If a single message > budget (e.g., user pastes a wall of text) → keep it in the window anyway (don't drop the most recent turn).

### Lazy summarization trigger

Summarize only when ALL of:
1. There are messages beyond the recent window (count ≥ `rag_memory_min_messages_to_summarize`).
2. The existing `session.summary_covers_until_id` is **not** the ID of the most-recent older-portion message — meaning new old-portion messages have appeared since the last summary.
3. `error=True` rows are excluded from summarization (they're failed responses, not real conversation).

If all 3 met → call `_summarize`. Else skip.

### Summarization prompt

```
Bạn là trợ lý tóm tắt hội thoại tín dụng.
Dưới đây là tóm tắt cũ (nếu có):
{previous_summary or "(chưa có)"}

Và các lượt mới cần cập nhật vào tóm tắt:
{formatted_messages_to_summarize}

Hãy viết một tóm tắt MỚI bao trùm toàn bộ hội thoại (cả phần cũ + phần mới),
tiếng Việt, tối đa ~500 tokens, tập trung vào:
- Câu hỏi/quan tâm chính của khách hàng
- Dữ kiện đã trao đổi (số tiền, kỳ hạn, DTI, trạng thái đơn)
- Quyết định / hướng dẫn đã đưa ra
Không bịa thêm thông tin ngoài hội thoại.
```

Output → `session.summary` + `summary_updated_at = now()` + `summary_covers_until_id = id của message cuối trong older portion`.

### Failure mode

If `_summarize` raises (LLM timeout / API error):
- Log warning, do **not** update `session.summary` (keep old summary).
- Return `MemoryContext(summary=session.summary, recent_messages=window)` — graceful degradation. Conversation continues without fresh summary; main RAG flow still works.

This matches the existing pattern in `chain.invoke` (retrieval failure → continue with empty docs).

---

## Migration order

1. Schema migration (add 3 columns).
2. Settings.
3. New `memory.py` (TDD with mocked DB + LLM).
4. Prompt template update.
5. `chain.invoke` signature (additive optional param).
6. `chat_service.send` integration (replace inline history fetch).
7. Update existing prompts.py test if any.

Each step ends with a green test + commit.

---

## Tests (in `backend/tests_local/`)

1. **`test_memory_token_estimation.py`** — `_estimate_tokens("hello world")` returns reasonable number.

2. **`test_memory_short_conversation_no_summary.py`** — session with 3 short messages → `MemoryContext.summary is None`, all 3 in `recent_messages`, no `_summarize` called.

3. **`test_memory_long_conversation_summarizes.py`** — session with 20 long messages → `_summarize` called once, `session.summary` updated, only window of recent ones in `recent_messages`. Mock `_summarize` to return a fixed string.

4. **`test_memory_skips_summarize_if_already_covered.py`** — session.summary exists and `summary_covers_until_id == latest old-portion message id` → no LLM call.

5. **`test_memory_excludes_error_rows.py`** — older portion contains an `error=True` row → that row is NOT passed into `_summarize`.

6. **`test_memory_summarize_failure_graceful.py`** — `_summarize` raises `LLMError` → `load_memory` returns the OLD summary + window, doesn't raise.

7. **`test_chat_service_uses_memory.py`** — integration: mock `load_memory` to return a known `MemoryContext`, verify `chat_service.send` passes `conversation_summary` to `_rag_invoke`.

Existing tests to update:
- `test_chat_service_atomic_save.py` — currently the `FakeDB` returns `[]` for ChatMessage query. After integration, `load_memory` will be called. Need to either mock `load_memory` in the test, or extend the FakeDB to return reasonable data for memory's queries.
- `test_rag_chain_retriever_fallback.py` and `test_rag_routing_guardrail_personalized.py` — `chain.invoke` gains optional `conversation_summary` param. Existing tests use defaults so should still pass without changes; verify.

---

## Acceptance criteria

- [ ] `backend/rag/memory.py` rewritten — no dead code.
- [ ] `ChatSession` has `summary`, `summary_covers_until_id`, `summary_updated_at` columns.
- [ ] `chat_service.send` calls `load_memory` instead of inline history-fetch.
- [ ] When conversation total < window budget: no summarization, no LLM call from memory layer.
- [ ] When conversation exceeds budget: `session.summary` populated, `summary_covers_until_id` set, recent window preserved.
- [ ] LLM failure during summarization → graceful degradation (old summary + window returned, no exception).
- [ ] `error=True` rows are excluded from both the window AND the summary.
- [ ] All new tests pass + all existing RAG/chat tests still pass.

---

## Trade-offs (logged for future iterations)

- **Char-based token estimate**: not exact for Gemini. If we hit context-window overruns, swap to a real tokenizer (tiktoken for OpenAI, vertex for Gemini). For V1, the conservative under-counting is fine.
- **Synchronous summarization**: adds an LLM call (~1-3s) on the turn that crosses threshold. Acceptable for now. V2 could move to background task.
- **Per-session scope**: cross-session memory would need fact extraction + a per-user store — out of scope here, designed for V2.
- **Summary not versioned**: we overwrite `session.summary` each time. Past summaries are lost. If we want audit trail, move to a separate `chat_summaries` table later.
- **Foreign key not enforced** for `summary_covers_until_id`: chose informational over enforced to keep migration simple. Application code is the source of truth.

---

## Out of scope (V2+)

- Fact extraction (user facts → persistent profile memory).
- Cross-session episodic recall (vector store over chat history).
- Background / async summarization.
- Token budgeting with a real tokenizer.
- Summary versioning / audit trail.
- Summary using a cheaper / dedicated model (V2 if we want to tune cost).
