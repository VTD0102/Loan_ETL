# RAG Query Rewriting Design

## Goal

Improve retrieval quality for conversational follow-up questions by rewriting the
user's current message into a standalone retrieval query before searching Qdrant.
The rewrite is used only for retrieval. The final answer must still be generated
from the user's original message, the chat history, the conversation summary, the
user profile context, and retrieved documents.

Example:

- Recent context: the user discussed an AUTO_REJECTED 50,000 loan at 12 months.
- User message: "vậy kỳ hạn nào tốt hơn?"
- Retrieval query: "Với hồ sơ vay bị từ chối khoản vay 50,000 kỳ hạn 12 tháng, kỳ hạn nào có thể giúp giảm rủi ro và tăng khả năng được duyệt?"
- Final prompt question remains: "vậy kỳ hạn nào tốt hơn?"

## Non-Goals

- Do not expose the rewritten query to the frontend API.
- Do not replace the user's original message in chat history.
- Do not use rewriting for greetings, off-topic messages, blocked messages, or
  intents that do not need retrieval.
- Do not add a second external model provider. Reuse the existing OpenRouter
  ChatOpenAI configuration.
- Do not change Qdrant collection schema, ingest format, or reranker behavior.

## Current State

`backend/services/chat_service.py` persists the user message, loads memory, builds
user context, then calls `rag.chain.invoke()` with:

- `question`: the raw user message
- `chat_history`: recent memory window
- `conversation_summary`: older summarized memory
- personalization and DB-derived user context

`backend/rag/chain.py` already passes chat history into intent classification and
the final LLM prompt, but retrieval currently calls `_retrieve_documents(question)`
with the raw user message. That means short follow-ups such as "cái nào tốt hơn?"
or "vì sao vậy?" can retrieve weak documents because the query lacks the topic from
the previous turns.

## Proposed Architecture

Add `backend/rag/query_rewriter.py`.

Public API:

```python
def rewrite_for_retrieval(
    question: str,
    chat_history: list,
    conversation_summary: str | None = None,
) -> str:
    ...
```

Behavior:

1. If both `chat_history` and `conversation_summary` are empty, return the
   original question without an LLM call.
2. Otherwise call the existing OpenRouter-backed `ChatOpenAI` model with a small,
   deterministic rewrite prompt.
3. The prompt asks the model to output exactly one standalone Vietnamese retrieval
   query, with no explanation.
4. The prompt forbids adding facts not present in the current question, recent
   history, or summary.
5. If the rewrite is blank, too long, timed out, or the LLM/API fails, return the
   original question.

`rag.chain.invoke()` changes:

1. Run input guardrail on the original `question`.
2. Classify intent using the original `question` and `chat_history`.
3. If `needs_retrieval(intent)` is true, call `rewrite_for_retrieval(...)`.
4. Call `_retrieve_documents(retrieval_query)`.
5. Generate the final answer with the original `question`, not the rewritten
   query.
6. Include `retrieval_query` in the internal return payload for tests and eval
   diagnostics. `chat_service` continues to expose only the normal response and
   sources.

This keeps answer semantics stable while making document lookup conversation-aware.

## Rewrite Prompt Contract

The rewrite prompt should be short and conservative:

- Language: Vietnamese.
- Output: one query sentence only.
- Preserve the user's intent.
- Resolve pronouns and vague references using conversation summary and recent
  messages.
- Keep loan/product terms and important numbers when present.
- Do not invent application status, amounts, credit score, DTI, or approval
  outcome.
- If the current question is already standalone, return it unchanged or minimally
  cleaned up.

## Failure Handling

Query rewriting is best-effort. It must never break chat.

Fallback to the original question when:

- The rewrite LLM raises `openai.APIError`, `openai.APIConnectionError`,
  `openai.APITimeoutError`, or `httpx.TimeoutException`.
- The rewritten text is empty after stripping.
- The rewritten text is much longer than expected. Use a conservative local limit
  such as 500 characters.
- The rewrite returns obvious formatting noise such as multiple lines with labels.

The existing retrieval fallback remains in place. If retrieval fails after rewrite,
`chain.invoke()` continues without documents as it does today.

## Observability

Do not expose the rewritten query in the public chat API response.

For tests and local eval, `rag.chain.invoke()` should return:

```python
{
    "answer": answer,
    "source_documents": documents,
    "intent": intent,
    "retrieval_query": retrieval_query,
}
```

For blocked or non-retrieval intents, `retrieval_query` must equal the original
question and the rewriter must not be called. This makes diagnostics predictable
without changing public chat behavior.

## Testing Strategy

Use local script-style tests under `backend/tests_local/`.

New tests:

- `test_rag_query_rewriter.py`
  - no memory returns original question without loading/calling the LLM
  - follow-up with memory rewrites into a standalone query
  - blank rewrite falls back to original
  - LLM/API error falls back to original
  - overlong rewrite falls back to original

Chain integration tests:

- retrieval receives the rewritten query
- final LLM prompt receives the original question
- greeting/off-topic/non-retrieval intent does not call the rewriter
- rewrite failure still retrieves with the original question

Regression tests:

- existing RAG chain tests
- chat memory test to ensure `chat_service.send()` still passes summary and
  recent messages into the chain
- non-live `test_rag_*.py`, `test_chat_*.py`, and `test_memory_*.py` sweep with
  live benchmark tests skipped

## Acceptance Criteria

- Conversational follow-up questions use a standalone retrieval query.
- The original user message is preserved for generation and persistence.
- Rewrite failures do not raise user-visible errors.
- No external services are required for unit tests; tests monkeypatch the rewriter
  LLM or module function.
- Public chat API shape does not change.
- Non-live test sweep passes.
