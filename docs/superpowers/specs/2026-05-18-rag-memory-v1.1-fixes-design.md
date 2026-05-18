# RAG Memory V1.1 — Fix design

**Date**: 2026-05-18
**Status**: Approved (post-audit of V1 implementation)
**Scope**: `backend/rag/memory.py`, `backend/services/chat_service.py`, `backend/tests_local/test_memory_excludes_error_rows.py`

## Why

V1 of the memory layer (commits `08bf24d`..`f7aa602`) passes all 11 standalone tests, but an audit found three issues the tests do not catch:

1. **Critical — user message duplication in `chat_history`.** `chat_service.send` commits the user message at line 46, then calls `load_memory(db, session)` at line 49. `load_memory` queries every non-error `ChatMessage` for the session, **including the message just committed**. The current question is then passed twice to the LLM: once as `question` and once inside `chat_history`. From the second turn onwards, every chat call duplicates the user's latest message.
2. **Important — `test_memory_excludes_error_rows.py` does not actually test exclusion from summarisation.** All test messages are ~15 chars (~3 tokens), well under the 2000-token budget. `_needs_summarize` returns `False`, so `fake_summarize` is never invoked, and the `if "to_summarize" in captured:` block silently passes. The spec acceptance "error rows excluded from summary input" is unverified.
3. **Important — DB commit failure inside `_summarize` propagates as an unhandled 500.** `_summarize` mutates `session.summary` / `session.summary_covers_until_id` / `session.summary_updated_at` in-memory, then calls `db.commit()`. If commit raises (e.g. transient connection loss), the exception is `SQLAlchemyError` — not `LLMError`/`RAGTimeoutError` — so `load_memory`'s graceful-degradation block does not catch it. The exception propagates up `send()`, where the only catch is `RAGError`, yielding a 500 with the in-memory session state already dirty.

V1.1 fixes all three with minimal surface changes; no behaviour outside these paths is touched.

## Non-goals

- No prompt or LLM behaviour changes.
- No new settings.
- No schema changes (V1 schema is unchanged).
- No re-architecting of the memory module.

---

## Fix 1 — Exclude the just-committed user message from `load_memory`

### Approach

Add an optional `exclude_message_id: uuid.UUID | None = None` parameter to `load_memory(db, session, exclude_message_id=None)`. Filter out rows whose `id` matches when fetching messages.

`chat_service.send` captures `user_message.id` after the first `db.commit()` and passes it: `memory = load_memory(db, session, exclude_message_id=user_message.id)`.

### Why this and not "load memory before committing user message"

Reordering would break the V0 atomic-save invariant established in the resilience refactor (user question must persist even if RAG fails). The cost of one extra optional parameter is much smaller than re-litigating that contract.

### Acceptance

- The current user turn never appears in `memory.recent_messages`.
- A standalone test verifies: after `send()` commits user message X and calls RAG, `_rag_invoke` receives a `chat_history` that does **not** contain X's content.

---

## Fix 2 — Make `test_memory_excludes_error_rows.py` actually exercise the summary path

### Approach

Inflate the test fixture so the older portion crosses the summary threshold:

- 12 messages, each 800 chars (rough: 200 tokens × 12 = 2400 tokens > 2000 budget).
- One of the older-portion messages has `error=True`.
- Mock `_summarize` to capture `messages_to_summarize`.
- Assert: `_summarize` was called exactly once **and** the captured list does NOT contain the error row.
- Also assert: `recent_messages` does not contain the error row (existing assertion stays).

Remove the silent `if "to_summarize" in captured:` guard — replace with a hard `assert "to_summarize" in captured` so a regression cannot pass undetected.

### Acceptance

- The updated test calls `fake_summarize` exactly once.
- `captured["to_summarize"]` has no row with `error=True`.

---

## Fix 3 — Graceful degradation on DB commit failure inside `_summarize`

### Approach

Wrap the `db.commit()` inside `_summarize` in `try/except SQLAlchemyError`. On failure:
1. Revert the three in-memory mutations to their previous values.
2. `db.rollback()`.
3. Raise `LLMError(f"Summary commit failed: {exc}") from exc`.

`load_memory` already catches `(LLMError, RAGTimeoutError)` and logs a warning — no change needed there. The graceful path returns the OLD summary + window, which is correct.

### Why `LLMError` (not a new exception type)

The existing `(LLMError, RAGTimeoutError)` catch in `load_memory` is the right contract. Adding a new `MemoryPersistError` would require updating the catch and adding a new test for the new type. `LLMError` is semantically slightly off but pragmatic — V1.1 stays small. If summary-commit failure becomes a frequent or distinct concern later, V2 can introduce a more precise type.

### Acceptance

- A standalone test: `_summarize` raises `SQLAlchemyError` from `db.commit()` → `load_memory` returns OLD summary + recent window, no exception leaks.
- In-memory `session.summary` / `summary_covers_until_id` / `summary_updated_at` are unchanged after the failed commit.

---

## Order of work

1. Fix 3 first — pure addition inside `memory.py`, no callsite changes.
2. Fix 2 — pure test edit, no production code change.
3. Fix 1 — adds optional param to `load_memory`, requires touching `chat_service.send` and one new test.

Each fix is its own commit. Each ends with the full memory + chat test suite green.

## Acceptance criteria (whole spec)

- All 3 fixes implemented per their sections.
- New test `test_chat_service_excludes_current_user_message.py` passes — verifies the user message ID is filtered out of the memory window.
- New test `test_memory_summarize_commit_failure_graceful.py` passes — verifies SQLAlchemyError in commit yields old summary + no exception.
- Updated `test_memory_excludes_error_rows.py` actually invokes `fake_summarize` and asserts on captured input.
- All existing memory / chat / RAG tests continue to pass.

## Out of scope (V2+)

- Async summarisation.
- Replacing the in-memory mutation pattern with a transactional context manager.
- Distinct exception types for memory-layer failures.
- Token budget tuning per LLM model.
