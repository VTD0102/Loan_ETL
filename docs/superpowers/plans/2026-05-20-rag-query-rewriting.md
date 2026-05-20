# RAG Query Rewriting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conversation-aware query rewriting so follow-up chat questions retrieve documents using a standalone query while answers still address the user's original message.

**Architecture:** Create a small best-effort `rag.query_rewriter` module that rewrites only the retrieval query using the existing OpenRouter ChatOpenAI configuration. Wire `rag.chain.invoke()` so input guardrails, intent routing, chat persistence, and final generation still use the original question, while Qdrant retrieval uses the rewritten query only when the routed intent needs retrieval.

**Tech Stack:** Python 3.12, LangChain `ChatOpenAI`, OpenRouter, script-style backend tests under `backend/tests_local/`, Qdrant retrieval already mocked in local tests.

---

## File Structure

- Create `backend/rag/query_rewriter.py`
  - Owns the rewrite prompt, LLM singleton, history formatting, output cleanup, and fallback behavior.
  - Public function: `rewrite_for_retrieval(question, chat_history, conversation_summary=None) -> str`.
  - Does not know about Qdrant, rerankers, chat sessions, or DB rows.
- Create `backend/tests_local/test_rag_query_rewriter.py`
  - Unit tests for no-memory bypass, rewrite success, blank fallback, exception fallback, overlong fallback, and label/multiline fallback.
- Create `backend/tests_local/test_rag_chain_query_rewrite.py`
  - Integration-style local tests for `rag.chain.invoke()` wiring.
- Modify `backend/rag/chain.py`
  - Import `rewrite_for_retrieval`.
  - Compute `retrieval_query` only for retrieval-needed intents.
  - Retrieve with `retrieval_query`.
  - Keep final prompt `question` as the original user message.
  - Return `retrieval_query` in the internal result payload.

---

## Task 1: Add Query Rewriter Module

**Files:**
- Create: `backend/tests_local/test_rag_query_rewriter.py`
- Create: `backend/rag/query_rewriter.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests_local/test_rag_query_rewriter.py`:

```python
"""Conversation-aware RAG query rewriter tests."""

import sys
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import rag.query_rewriter as query_rewriter


class FakeRewriteLLM:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(content=self.response)


def _patch_llm(fake_llm):
    original_get = query_rewriter._get_rewrite_llm
    query_rewriter._get_rewrite_llm = lambda: fake_llm

    def restore():
        query_rewriter._get_rewrite_llm = original_get

    return restore


def test_no_memory_returns_original_without_llm_call():
    original_get = query_rewriter._get_rewrite_llm
    query_rewriter._get_rewrite_llm = lambda: (_ for _ in ()).throw(
        AssertionError("rewrite LLM should not be loaded without memory")
    )
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "DTI là gì?",
            [],
            conversation_summary=None,
        )
    finally:
        query_rewriter._get_rewrite_llm = original_get

    assert result == "DTI là gì?"


def test_follow_up_with_memory_rewrites_to_standalone_query():
    fake_llm = FakeRewriteLLM(
        "Với hồ sơ vay bị từ chối khoản vay 50 triệu kỳ hạn 12 tháng, kỳ hạn nào có thể giúp tăng khả năng được duyệt?"
    )
    restore = _patch_llm(fake_llm)
    history = [
        HumanMessage(content="Tôi bị từ chối khoản vay 50 triệu kỳ hạn 12 tháng."),
        AIMessage(content="Bạn có thể thử kỳ hạn dài hơn để giảm áp lực trả nợ."),
    ]
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "vậy kỳ hạn nào tốt hơn?",
            history,
            conversation_summary="Khách đang hỏi về khoản vay bị AUTO_REJECTED.",
        )
    finally:
        restore()

    assert result.startswith("Với hồ sơ vay bị từ chối")
    assert "kỳ hạn nào" in result
    assert len(fake_llm.calls) == 1
    rendered_prompt = str(fake_llm.calls[0])
    assert "vậy kỳ hạn nào tốt hơn?" in rendered_prompt
    assert "AUTO_REJECTED" in rendered_prompt
    assert "Tôi bị từ chối khoản vay 50 triệu" in rendered_prompt


def test_blank_rewrite_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM("   ")
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "vì sao vậy?",
            [HumanMessage(content="DTI của tôi cao.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "vì sao vậy?"


def test_llm_error_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM(raises=RuntimeError("rewrite model unavailable"))
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "vì sao vậy?",
            [HumanMessage(content="Hồ sơ bị từ chối vì DTI cao.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "vì sao vậy?"


def test_overlong_rewrite_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM("a" * 501)
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "còn gì nữa?",
            [HumanMessage(content="Tôi muốn biết cách cải thiện hồ sơ vay.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "còn gì nữa?"


def test_multiline_or_labeled_rewrite_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM("Query:\nKỳ hạn nào tốt hơn cho hồ sơ bị từ chối?")
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "kỳ hạn nào?",
            [HumanMessage(content="Tôi bị từ chối khoản vay 50 triệu.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "kỳ hạn nào?"


if __name__ == "__main__":
    test_no_memory_returns_original_without_llm_call()
    test_follow_up_with_memory_rewrites_to_standalone_query()
    test_blank_rewrite_falls_back_to_original_question()
    test_llm_error_falls_back_to_original_question()
    test_overlong_rewrite_falls_back_to_original_question()
    test_multiline_or_labeled_rewrite_falls_back_to_original_question()
    print("rag query rewriter tests passed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_query_rewriter.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rag.query_rewriter'`.

- [ ] **Step 3: Implement the query rewriter**

Create `backend/rag/query_rewriter.py`:

```python
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
        response = _get_rewrite_llm().invoke([
            {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_rewrite_prompt(original, chat_history, conversation_summary)},
        ])
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_query_rewriter.py
```

Expected: `rag query rewriter tests passed`.

- [ ] **Step 5: Commit**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/query_rewriter.py backend/tests_local/test_rag_query_rewriter.py
git commit -m "feat: add RAG query rewriter"
```

---

## Task 2: Wire Rewritten Query Into RAG Chain

**Files:**
- Modify: `backend/rag/chain.py`
- Create: `backend/tests_local/test_rag_chain_query_rewrite.py`

- [ ] **Step 1: Write the failing chain integration tests**

Create `backend/tests_local/test_rag_chain_query_rewrite.py`:

```python
"""Verify RAG chain uses rewritten queries only for retrieval."""

import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import rag.chain as chain


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return [
            Document(
                page_content="Kỳ hạn dài hơn có thể giảm DTI và rủi ro trả nợ.",
                metadata={"source": "policy.md", "section_title": "Kỳ hạn vay"},
            )
        ]


class FakeChain:
    def __init__(self):
        self.payloads = []

    def invoke(self, payload):
        self.payloads.append(payload)
        return "Bạn có thể cân nhắc kỳ hạn dài hơn."


def _patch_chain(
    fake_chain,
    fake_retriever=None,
    rewrite_func=None,
    intent="personal_advice",
    needs_retrieval=True,
):
    originals = {
        "get_chain": chain.get_chain,
        "get_retriever": chain.get_retriever,
        "classify_intent": chain.classify_intent,
        "needs_retrieval": chain.needs_retrieval,
        "rewrite_for_retrieval": chain.rewrite_for_retrieval,
    }
    chain.get_chain = lambda: fake_chain
    if fake_retriever is not None:
        chain.get_retriever = lambda: fake_retriever
    chain.classify_intent = lambda question, chat_history: intent
    chain.needs_retrieval = lambda routed_intent: needs_retrieval
    if rewrite_func is not None:
        chain.rewrite_for_retrieval = rewrite_func

    def restore():
        chain.get_chain = originals["get_chain"]
        chain.get_retriever = originals["get_retriever"]
        chain.classify_intent = originals["classify_intent"]
        chain.needs_retrieval = originals["needs_retrieval"]
        chain.rewrite_for_retrieval = originals["rewrite_for_retrieval"]

    return restore


def test_chain_retrieves_with_rewritten_query_but_answers_original_question():
    fake_chain = FakeChain()
    fake_retriever = FakeRetriever()
    rewrite_calls = []
    history = [HumanMessage(content="Tôi bị từ chối khoản vay 50 triệu kỳ hạn 12 tháng.")]

    def fake_rewrite(question, chat_history, conversation_summary=None):
        rewrite_calls.append((question, list(chat_history), conversation_summary))
        return "Hồ sơ vay bị từ chối 50 triệu kỳ hạn 12 tháng nên chọn kỳ hạn nào?"

    restore = _patch_chain(fake_chain, fake_retriever, fake_rewrite)
    try:
        result = chain.invoke(
            "vậy kỳ hạn nào tốt hơn?",
            "customer context",
            history,
            conversation_summary="Khách có hồ sơ AUTO_REJECTED.",
        )
    finally:
        restore()

    assert fake_retriever.queries == [
        "Hồ sơ vay bị từ chối 50 triệu kỳ hạn 12 tháng nên chọn kỳ hạn nào?"
    ]
    assert fake_chain.payloads[0]["question"] == "vậy kỳ hạn nào tốt hơn?"
    assert "Kỳ hạn dài hơn" in fake_chain.payloads[0]["context"]
    assert rewrite_calls == [
        (
            "vậy kỳ hạn nào tốt hơn?",
            history,
            "Khách có hồ sơ AUTO_REJECTED.",
        )
    ]
    assert result["answer"] == "Bạn có thể cân nhắc kỳ hạn dài hơn."
    assert result["retrieval_query"] == "Hồ sơ vay bị từ chối 50 triệu kỳ hạn 12 tháng nên chọn kỳ hạn nào?"
    assert len(result["source_documents"]) == 1


def test_chain_skips_rewriter_for_non_retrieval_intent():
    fake_chain = FakeChain()
    rewrite_calls = []

    def fake_rewrite(question, chat_history, conversation_summary=None):
        rewrite_calls.append(question)
        return "should not be used"

    restore = _patch_chain(
        fake_chain,
        fake_retriever=None,
        rewrite_func=fake_rewrite,
        intent="greeting",
        needs_retrieval=False,
    )
    try:
        result = chain.invoke(
            "Xin chào",
            "customer context",
            [HumanMessage(content="Tôi hỏi về khoản vay hôm qua.")],
            conversation_summary="Khách hỏi về khoản vay.",
        )
    finally:
        restore()

    assert rewrite_calls == []
    assert fake_chain.payloads[0]["question"] == "Xin chào"
    assert fake_chain.payloads[0]["context"] == "Không tìm thấy tài liệu liên quan trong kho kiến thức."
    assert result["intent"] == "greeting"
    assert result["retrieval_query"] == "Xin chào"
    assert result["source_documents"] == []


def test_chain_falls_back_to_original_query_when_rewriter_raises():
    fake_chain = FakeChain()
    fake_retriever = FakeRetriever()

    def failing_rewrite(question, chat_history, conversation_summary=None):
        raise RuntimeError("rewrite failed")

    restore = _patch_chain(fake_chain, fake_retriever, failing_rewrite)
    try:
        result = chain.invoke(
            "vì sao vậy?",
            "customer context",
            [HumanMessage(content="DTI của tôi quá cao.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert fake_retriever.queries == ["vì sao vậy?"]
    assert fake_chain.payloads[0]["question"] == "vì sao vậy?"
    assert result["retrieval_query"] == "vì sao vậy?"


if __name__ == "__main__":
    test_chain_retrieves_with_rewritten_query_but_answers_original_question()
    test_chain_skips_rewriter_for_non_retrieval_intent()
    test_chain_falls_back_to_original_query_when_rewriter_raises()
    print("rag chain query rewrite tests passed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_query_rewrite.py
```

Expected: FAIL with `AttributeError: module 'rag.chain' has no attribute 'rewrite_for_retrieval'`.

- [ ] **Step 3: Update `rag.chain` imports**

In `backend/rag/chain.py`, add this import next to the other `rag.*` imports:

```python
from rag.query_rewriter import rewrite_for_retrieval
```

- [ ] **Step 4: Replace `invoke()` with query-rewrite-aware implementation**

In `backend/rag/chain.py`, replace the existing `invoke()` function with:

```python
def invoke(
    question: str,
    user_context: str,
    chat_history: list,
    personalization: "PersonalizationContext | None" = None,
    conversation_summary: str | None = None,
) -> dict:
    """Full RAG pipeline: guardrail -> route -> rewrite -> retrieve -> LLM -> guardrail."""
    retrieval_query = question

    # ── Step 1: Input guardrail ───────────────────────────────────────────
    input_check = check_input(question)
    if not input_check.passed:
        logger.info("Input guardrail blocked message: %s", input_check.reason)
        return {
            "answer": input_check.reason,
            "source_documents": [],
            "intent": "blocked",
            "blocked": True,
            "retrieval_query": retrieval_query,
        }

    # ── Step 2: Intent routing ────────────────────────────────────────────
    intent = classify_intent(question, chat_history)
    logger.info("Classified intent: %s", intent)

    # ── Step 3: Retrieval (intent-aware, conversation-query-aware) ─────────
    documents: list[Any] = []
    if needs_retrieval(intent):
        try:
            retrieval_query = rewrite_for_retrieval(
                question,
                chat_history,
                conversation_summary=conversation_summary,
            )
        except Exception:
            logger.exception("Query rewrite failed unexpectedly, using original question")
            retrieval_query = question

        try:
            documents = _retrieve_documents(retrieval_query)
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
        "retrieval_query": retrieval_query,
    }
```

- [ ] **Step 5: Run chain query rewrite test to verify it passes**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_query_rewrite.py
```

Expected: `rag chain query rewrite tests passed`.

- [ ] **Step 6: Run existing chain/routing tests**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_import.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_format_documents.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
```

Expected:

```text
RAG chain import test passed
rag chain document formatting tests passed
RAG retriever fallback test passed
RAG routing, guardrail, and personalization-focused checks passed.
```

- [ ] **Step 7: Commit**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chain.py backend/tests_local/test_rag_chain_query_rewrite.py
git commit -m "feat: use rewritten query for RAG retrieval"
```

---

## Task 3: Focused Regression Sweep

**Files:**
- No source edits expected.

- [ ] **Step 1: Run new tests together**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_query_rewriter.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_query_rewrite.py
```

Expected:

```text
rag query rewriter tests passed
rag chain query rewrite tests passed
```

- [ ] **Step 2: Run affected chat/memory tests**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_uses_memory.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_excludes_current_user_message.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_atomic_save.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_short_conversation_no_summary.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_long_conversation_summarizes.py
```

Expected:

```text
chat_service uses memory test passed
chat_service excludes-current-user-message test passed
chat_service atomic save test passed
memory short-conversation test passed
memory long-conversation summarise test passed
```

- [ ] **Step 3: Run non-live RAG/chat/memory sweep**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
SKIP=(
  tests_local/test_rag_benchmark.py
  tests_local/test_rag_evaluation_notebook.py
)
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    skip=false
    for s in "${SKIP[@]}"; do
        [[ "$f" == "$s" ]] && skip=true && break
    done
    [[ "$skip" == true ]] && { echo "=== $f === SKIPPED (live)"; continue; }
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All non-live tests passed"
```

Expected: `All non-live tests passed`.

- [ ] **Step 4: Commit only if the sweep required compatibility fixes**

If no files changed after the sweep, do not commit.

If a small compatibility fix was required, run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chain.py backend/rag/query_rewriter.py backend/tests_local/test_rag_chain_query_rewrite.py backend/tests_local/test_rag_query_rewriter.py
git commit -m "fix: stabilize RAG query rewriting"
```

---

## Task 4: Final Verification and Status

**Files:**
- No source edits expected.

- [ ] **Step 1: Check worktree status**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git status --short --branch
```

Expected: clean worktree on branch `taitu`, ahead by local query-rewriting commits.

- [ ] **Step 2: List recent commits**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git log --oneline -6
```

Expected: includes these titles:

```text
feat: add RAG query rewriter
feat: use rewritten query for RAG retrieval
```

- [ ] **Step 3: Report outcome**

Report:

- Commits made, with SHA and title.
- Test commands run and pass/fail status.
- Whether public chat API response shape changed.
- Any deviations from this plan.
- `git status --short --branch`.
