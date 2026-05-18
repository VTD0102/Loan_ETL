# RAG Resilience Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 resilience gaps in the RAG layer (exception handling, timeouts, atomic save, personalizer DB duplication, ingest CLI) so we can safely build new features on top.

**Architecture:** TDD per task. Refactor in dependency order: signature changes first (personalizer → chain.invoke → chat_service), then additive changes (timeouts, exceptions module), then behavior changes (atomic save), then standalone CLI (ingest). Each task ends with a green test run and a git commit. No frontend changes.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (Supabase Postgres), LangChain (`langchain-openai`, `langchain-qdrant`), Qdrant client, Pydantic V2, OpenAI SDK. Tests are standalone scripts in `backend/tests_local/` (not pytest suites).

**Spec:** [docs/superpowers/specs/2026-05-18-rag-resilience-fixes-design.md](../specs/2026-05-18-rag-resilience-fixes-design.md)

---

## File Structure

**New files:**
- `backend/rag/exceptions.py` — `RAGError` hierarchy.
- `backend/tests_local/test_rag_exceptions.py` — verify hierarchy.
- `backend/tests_local/test_rag_personalization_no_db.py` — personalizer without db.
- `backend/tests_local/test_rag_timeout_config.py` — verify timeout kwargs propagate.
- `backend/tests_local/test_chat_service_atomic_save.py` — user message persists on RAG failure.
- `backend/tests_local/test_rag_ingest_cli.py` — ingest --dry-run / --recreate flags.

**Modified files:**
- `backend/core/config.py` — add `rag_*_timeout_seconds` settings.
- `backend/models/chat.py` — add `error` column to `ChatMessage`.
- `backend/init_db.py` — add `ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error ...`.
- `backend/rag/personalizer.py` — `build_personalization(user, app)` signature.
- `backend/rag/chain.py` — drop `db`/`user_id`, accept `personalization`; specific exception handling; timeouts on `ChatOpenAI`.
- `backend/rag/router.py` — timeouts on classifier LLM; specific exception handling.
- `backend/rag/retriever.py` — split `QdrantClient(timeout=...)` + `OpenAIEmbeddings(timeout=...)`.
- `backend/rag/ingest.py` — argparse with `--dry-run` / `--recreate` / `--collection`.
- `backend/services/chat_service.py` — top-level imports, atomic save, build personalization, raise 503 on `RAGError`.
- `backend/tests_local/test_rag_routing_guardrail_personalized.py` — update to new `chain.invoke` signature.
- `backend/tests_local/test_rag_chain_retriever_fallback.py` — update to new `chain.invoke` signature.

**Each file has one responsibility.** No file in this plan grows beyond what already exists. `chat_service.py` will lose ~20 lines (try/except fallback) and gain ~15 (atomic save).

---

## Task 1: Add `rag/exceptions.py`

**Files:**
- Create: `backend/rag/exceptions.py`
- Test: `backend/tests_local/test_rag_exceptions.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_exceptions.py`:

```python
"""Verify RAGError hierarchy."""
from rag.exceptions import RAGError, RetrievalError, LLMError, RAGTimeoutError


def test_hierarchy():
    assert issubclass(RetrievalError, RAGError)
    assert issubclass(LLMError, RAGError)
    assert issubclass(RAGTimeoutError, RAGError)
    assert issubclass(RAGError, Exception)


def test_instantiation_and_message():
    exc = RetrievalError("qdrant down")
    assert isinstance(exc, RAGError)
    assert str(exc) == "qdrant down"


if __name__ == "__main__":
    test_hierarchy()
    test_instantiation_and_message()
    print("rag.exceptions hierarchy tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_exceptions.py
```

Expected: `ModuleNotFoundError: No module named 'rag.exceptions'`.

- [ ] **Step 3: Implement `backend/rag/exceptions.py`**

```python
"""Exception hierarchy for the RAG pipeline.

Catching ``RAGError`` covers any RAG-layer failure (retrieval, LLM, timeout).
Catch a specific subclass when you want to handle a single failure mode.
"""


class RAGError(Exception):
    """Base exception for RAG pipeline failures."""


class RetrievalError(RAGError):
    """Qdrant or embedding service failure."""


class LLMError(RAGError):
    """OpenRouter / LLM call failure."""


class RAGTimeoutError(RAGError):
    """Upstream call exceeded its timeout budget."""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_exceptions.py
```

Expected: `rag.exceptions hierarchy tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/rag/exceptions.py backend/tests_local/test_rag_exceptions.py
git commit -m "feat: add RAG exception hierarchy (RAGError + subclasses)"
```

---

## Task 2: Refactor `personalizer.build_personalization` to (user, app) signature

**Files:**
- Modify: `backend/rag/personalizer.py`
- Modify: `backend/rag/chain.py:54-136` (invoke signature + call site)
- Modify: `backend/tests_local/test_rag_routing_guardrail_personalized.py` (line 57-59 patches old signature)
- Modify: `backend/tests_local/test_rag_chain_retriever_fallback.py` (line 26-30 calls invoke)
- Test: `backend/tests_local/test_rag_personalization_no_db.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_personalization_no_db.py`:

```python
"""Verify build_personalization(user, app) works without db session."""
from types import SimpleNamespace
from rag.personalizer import build_personalization, PersonalizationContext


def test_no_user_no_app_returns_default():
    ctx = build_personalization(None, None)
    assert ctx.user_display_name == "Quý khách"
    assert ctx.application_status is None
    assert "THÂN THIỆN" in ctx.tone_instructions


def test_pending_review_tone():
    user = SimpleNamespace(username="Minh")
    app = SimpleNamespace(status="PENDING_REVIEW")
    ctx = build_personalization(user, app)
    assert ctx.user_display_name == "Minh"
    assert ctx.application_status == "pending_review"
    assert "KHÍCH LỆ" in ctx.tone_instructions


def test_auto_rejected_tone():
    user = SimpleNamespace(username="Lan")
    app = SimpleNamespace(status="AUTO_REJECTED")
    ctx = build_personalization(user, app)
    assert ctx.application_status == "auto_rejected"
    assert "ĐỒNG CẢM" in ctx.tone_instructions


def test_user_without_username():
    user = SimpleNamespace(username=None)
    ctx = build_personalization(user, None)
    assert ctx.user_display_name == "Quý khách"


if __name__ == "__main__":
    test_no_user_no_app_returns_default()
    test_pending_review_tone()
    test_auto_rejected_tone()
    test_user_without_username()
    print("personalization (no-db) tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_personalization_no_db.py
```

Expected: `TypeError: build_personalization() missing 1 required positional argument` or similar — current signature is `(db, user_id)`.

- [ ] **Step 3: Refactor `backend/rag/personalizer.py`**

Replace the `build_personalization` function (currently at lines 148-180). The full new function body:

```python
def build_personalization(
    user: "User | None",
    app: "LoanApplication | None",
) -> PersonalizationContext:
    """Build personalized context from user profile + latest application.

    Caller is responsible for fetching ``user`` and ``app`` from the database
    (or passing ``None``). This keeps the RAG layer decoupled from the ORM
    session.
    """
    ctx = PersonalizationContext()

    if user is not None and getattr(user, "username", None):
        ctx.user_display_name = user.username

    if app is not None:
        ctx.application_status = (app.status or "").lower()
    else:
        ctx.application_status = None

    tone_config = _STATUS_TONES.get(ctx.application_status) or _STATUS_TONES.get(None)
    ctx.tone_instructions = tone_config["tone"]
    ctx.greeting_line = tone_config["greeting"]
    return ctx
```

Also remove the now-unused imports at the top of `backend/rag/personalizer.py`:

```python
# Delete these three lines (no longer needed):
from sqlalchemy.orm import Session

from models.application import LoanApplication
from models.user import User
```

The `User`/`LoanApplication` references in the new signature are forward references as strings (`"User | None"`), so removing the runtime imports is safe.

- [ ] **Step 4: Update `backend/rag/chain.py` invoke signature**

Replace `invoke()` (currently at lines 54-136). The full new body:

```python
def invoke(
    question: str,
    user_context: str,
    chat_history: list,
    personalization: "PersonalizationContext | None" = None,
) -> dict:
    """Full RAG pipeline: guardrail → route → retrieve → personalise → LLM → guardrail.

    Parameters
    ----------
    question : str
        The user's message.
    user_context : str
        Pre-built textual context from ``context_builder.build_user_context``.
    chat_history : list
        LangChain message objects for conversation memory.
    personalization : PersonalizationContext, optional
        Pre-built personalization context. If ``None``, defaults are used.

    Returns
    -------
    dict
        ``answer``, ``source_documents``, ``intent``, and optionally ``blocked``.
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
        except Exception:
            logger.exception("Retrieval failed, continuing without docs")
            documents = []

    # ── Step 4: Personalization (caller-provided) ─────────────────────────
    if personalization is None:
        personalization = PersonalizationContext()
    intent_instructions = get_intent_instructions(intent)

    # ── Step 5: LLM call ─────────────────────────────────────────────────
    answer = get_chain().invoke({
        "question": question,
        "user_context": user_context,
        "context": _format_documents(documents),
        "chat_history": chat_history,
        "user_display_name": personalization.user_display_name,
        "personalization_instructions": personalization.tone_instructions,
        "intent_instructions": intent_instructions,
    })

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

Also update the imports in `backend/rag/chain.py` (currently lines 21, 26-30) — remove the `Session` import and the `build_personalization` import (no longer called from chain), and remove the `get_intent_instructions` line that's now bundled with personalizer:

```python
# Top of chain.py — keep only what's still needed:
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from core.config import settings
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL
from rag.guardrails import check_input, check_output
from rag.personalizer import PersonalizationContext, get_intent_instructions
from rag.prompts import chat_prompt
from rag.retriever import get_retriever
from rag.router import classify_intent, needs_retrieval
```

Specifically: delete `from sqlalchemy.orm import Session` and the `build_personalization` from the `rag.personalizer` import line.

- [ ] **Step 5: Update existing test `test_rag_routing_guardrail_personalized.py`**

Replace `test_chain_injects_personalization_into_prompt_payload` (lines 41-67):

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
        )

        assert result["intent"] == "greeting"
        assert captured_payload["user_display_name"] == "Minh"
        assert "kiểm thử cá nhân hóa" in captured_payload["personalization_instructions"]
        assert captured_payload["context"] == "Không tìm thấy tài liệu liên quan trong kho kiến thức."
    finally:
        chain.get_chain = original_get_chain
```

(The `build_personalization` monkey-patch is gone — chain doesn't call it anymore.)

- [ ] **Step 6: Update existing test `test_rag_chain_retriever_fallback.py`**

The current call at line 26-30 already uses the new signature (no `db`/`user_id` passed), so no change needed. Verify by reading the file — if `chain.invoke("...", "...", [])` is intact, leave alone.

- [ ] **Step 7: Run all affected tests**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_personalization_no_db.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
```

Expected: all three print their "passed" messages.

- [ ] **Step 8: Note that `chat_service.py` is now broken**

`chat_service.send()` calls `rag_invoke(payload_message, context, chat_history, db=db, user_id=user.id)`. With the new signature, these kwargs no longer exist. The chat endpoint will throw `TypeError` until Task 3.

This is acceptable for an isolated commit; Task 3 fixes it immediately. Do not run the live server between Task 2 and Task 3.

- [ ] **Step 9: Commit**

```bash
git add backend/rag/personalizer.py backend/rag/chain.py \
        backend/tests_local/test_rag_personalization_no_db.py \
        backend/tests_local/test_rag_routing_guardrail_personalized.py
git commit -m "refactor: personalizer takes (user, app); chain.invoke takes PersonalizationContext"
```

---

## Task 3: Update `chat_service` to build personalization and fetch app

**Files:**
- Modify: `backend/services/chat_service.py:150-177` (`_ensure_latest_application_has_prediction`)
- Modify: `backend/services/chat_service.py:15-68` (`send`)

Note: This task does NOT yet refactor imports (still lazy) or atomic save — those come in later tasks. Goal is only to restore green chat flow with new signatures.

- [ ] **Step 1: Update `_ensure_latest_application_has_prediction` to return the app**

Open `backend/services/chat_service.py`. Replace the function (currently lines 150-177):

```python
def _ensure_latest_application_has_prediction(db: Session, user_id: Any) -> LoanApplication | None:
    """Ensure the user's latest application has ML prediction fields filled.

    Returns the latest application (or None if the user has none). Callers
    can reuse this object to avoid a duplicate query downstream.
    """
    app = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )
    if app is None:
        return None
    if app.default_probability is not None and app.model_version:
        return app

    payload = _application_to_payload(app)
    try:
        prediction = ml_service.predict(payload, db=db, user_id=user_id)
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ML model is not available or has an invalid contract: {exc}",
        ) from exc

    app.default_probability = prediction.get("default_probability")
    app.risk_level = prediction.get("risk_level")
    app.risk_score = prediction.get("risk_score")
    app.recommended_amount = prediction.get("recommended_amount")
    app.recommended_term = prediction.get("recommended_term")
    app.model_version = prediction.get("model_version")
    app.feature_snapshot = prediction.get("feature_snapshot")
    app.imputed_features = prediction.get("imputed_features")
    db.flush()
    return app
```

- [ ] **Step 2: Update `send()` to capture the app and pass personalization**

Replace `send()` (currently lines 15-68). The full new body (still using lazy import; atomic save comes later):

```python
def send(db: Session, user_email: str, payload_message: str, session_id: Any = None) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _enforce_rate_limit(db, user.id)
    app = _ensure_latest_application_has_prediction(db, user.id)
    session = _get_or_create_session(db, user.id, session_id)
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
        .all()
    )

    try:
        from langchain_core.messages import AIMessage, HumanMessage
        from rag.chain import invoke as rag_invoke
        from rag.context_builder import build_user_context
        from rag.personalizer import build_personalization

        chat_history = []
        for row in reversed(history_rows):
            if row.role == "user":
                chat_history.append(HumanMessage(content=row.content))
            elif row.role == "assistant":
                chat_history.append(AIMessage(content=row.content))

        context = build_user_context(db, user.id)
        personalization = build_personalization(user, app)
        response_payload = rag_invoke(
            payload_message, context, chat_history,
            personalization=personalization,
        )
        answer = response_payload.get("answer", "Xin lỗi, hiện tại tôi không thể kết nối tới lõi suy luận kiến thức.")
        sources = _extract_sources(response_payload.get("source_documents", []))
    except ImportError as ie:
        answer = f"RAG Module chưa sẵn sàng: {str(ie)}. Xin thử lại sau."
        sources = []
    except Exception as e:
        answer = f"Lỗi truy vấn nội bộ RAG/LLM: {str(e)}"
        sources = []

    if not session.title:
        session.title = payload_message.strip()[:80]
    session.updated_at = datetime.utcnow()
    db.add(ChatMessage(session_id=session.id, role="user", content=payload_message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer, sources=sources))
    db.commit()

    return {
        "response": answer,
        "session_id": session.id,
        "sources": sources,
    }
```

- [ ] **Step 3: Run all RAG/chat tests**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_personalization_no_db.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_import.py
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add backend/services/chat_service.py
git commit -m "refactor: chat_service builds personalization and passes app to RAG chain"
```

---

## Task 4: Add timeout settings + apply to LLM/embedding/Qdrant

**Files:**
- Modify: `backend/core/config.py:8-37` (add 5 settings)
- Modify: `backend/rag/chain.py:40-51` (`get_chain`)
- Modify: `backend/rag/router.py:127-137` (`_get_classifier_llm`)
- Modify: `backend/rag/retriever.py:13-28` (`get_retriever`)
- Test: `backend/tests_local/test_rag_timeout_config.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_timeout_config.py`:

```python
"""Verify timeout/max_retries are propagated to LLM/embedding/Qdrant clients."""
from langchain_core.runnables import Runnable

import rag.chain as chain_mod
import rag.retriever as retriever_mod
import rag.router as router_mod
from core.config import settings


_captured = {}


class FakeChatOpenAI(Runnable):
    """Runnable stub so it composes with `chat_prompt | llm | parser`."""
    def __init__(self, **kwargs):
        _captured.setdefault("chat", []).append(kwargs)

    def invoke(self, input, config=None, **kwargs):
        return "stub"


class FakeEmbeddings:
    def __init__(self, **kwargs):
        _captured["embeddings"] = kwargs


class FakeQdrantClient:
    def __init__(self, **kwargs):
        _captured["qdrant"] = kwargs


class FakeVectorStore:
    def __init__(self, **kwargs):
        pass

    def as_retriever(self, **kwargs):
        return self


def test_chat_chain_timeout_kwargs():
    chain_mod._chain = None
    original = chain_mod.ChatOpenAI
    chain_mod.ChatOpenAI = FakeChatOpenAI
    try:
        chain_mod.get_chain()
    finally:
        chain_mod.ChatOpenAI = original
        chain_mod._chain = None

    chat_kwargs = _captured["chat"][-1]
    assert chat_kwargs["timeout"] == settings.rag_llm_timeout_seconds
    assert chat_kwargs["max_retries"] == settings.rag_llm_max_retries


def test_router_classifier_timeout_kwargs():
    router_mod._classifier_llm = None
    original = router_mod.ChatOpenAI
    router_mod.ChatOpenAI = FakeChatOpenAI
    try:
        router_mod._get_classifier_llm()
    finally:
        router_mod.ChatOpenAI = original
        router_mod._classifier_llm = None

    chat_kwargs = _captured["chat"][-1]
    assert chat_kwargs["timeout"] == settings.rag_llm_timeout_seconds
    assert chat_kwargs["max_retries"] == settings.rag_llm_max_retries


def test_retriever_timeout_kwargs():
    retriever_mod._retriever = None
    original_emb = retriever_mod.OpenAIEmbeddings
    original_client = retriever_mod.QdrantClient
    original_vs = retriever_mod.QdrantVectorStore
    retriever_mod.OpenAIEmbeddings = FakeEmbeddings
    retriever_mod.QdrantClient = FakeQdrantClient
    retriever_mod.QdrantVectorStore = FakeVectorStore
    try:
        retriever_mod.get_retriever()
    finally:
        retriever_mod.OpenAIEmbeddings = original_emb
        retriever_mod.QdrantClient = original_client
        retriever_mod.QdrantVectorStore = original_vs
        retriever_mod._retriever = None

    assert _captured["embeddings"]["timeout"] == settings.rag_embedding_timeout_seconds
    assert _captured["embeddings"]["max_retries"] == settings.rag_embedding_max_retries
    assert _captured["qdrant"]["timeout"] == settings.rag_qdrant_timeout_seconds


if __name__ == "__main__":
    test_chat_chain_timeout_kwargs()
    test_router_classifier_timeout_kwargs()
    test_retriever_timeout_kwargs()
    print("rag timeout config tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Expected: `AttributeError: 'Settings' object has no attribute 'rag_llm_timeout_seconds'` (settings not added yet) OR `KeyError: 'timeout'` (kwargs not in captured dict yet).

- [ ] **Step 3: Add timeout settings to `backend/core/config.py`**

Edit `backend/core/config.py`. After the `rag_top_k: int = 4` line (line 31), add:

```python
    # RAG timeouts / retries (seconds)
    rag_llm_timeout_seconds: float = 30.0
    rag_llm_max_retries: int = 2
    rag_embedding_timeout_seconds: float = 10.0
    rag_embedding_max_retries: int = 2
    rag_qdrant_timeout_seconds: float = 5.0
```

- [ ] **Step 4: Apply timeout to `get_chain` in `backend/rag/chain.py`**

Replace the `ChatOpenAI(...)` instantiation in `get_chain()` (currently lines 44-49):

```python
        llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0.3,
            timeout=settings.rag_llm_timeout_seconds,
            max_retries=settings.rag_llm_max_retries,
        )
```

- [ ] **Step 5: Apply timeout to `_get_classifier_llm` in `backend/rag/router.py`**

Replace `ChatOpenAI(...)` in `_get_classifier_llm` (currently lines 130-136):

```python
        _classifier_llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0,
            max_tokens=60,
            timeout=settings.rag_llm_timeout_seconds,
            max_retries=settings.rag_llm_max_retries,
        )
```

- [ ] **Step 6: Restructure `get_retriever` in `backend/rag/retriever.py`**

Replace the full file body:

```python
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL, TOP_K,
)
from core.config import settings

_retriever = None


def get_retriever():
    global _retriever
    if _retriever is None:
        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            timeout=settings.rag_embedding_timeout_seconds,
            max_retries=settings.rag_embedding_max_retries,
        )
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=settings.rag_qdrant_timeout_seconds,
        )
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
        )
        _retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    return _retriever
```

- [ ] **Step 7: Run the timeout test**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Expected: `rag timeout config tests passed`.

- [ ] **Step 8: Run existing RAG tests to confirm no regression**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_qdrant_config.py
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/core/config.py backend/rag/chain.py backend/rag/router.py \
        backend/rag/retriever.py backend/tests_local/test_rag_timeout_config.py
git commit -m "feat: explicit timeouts + retries for LLM, embeddings, Qdrant"
```

---

## Task 5: Specific exception handling in `chain.py` and `router.py`

**Files:**
- Modify: `backend/rag/chain.py` (imports, `_retrieve_documents`, LLM call in `invoke`)
- Modify: `backend/rag/router.py:194` (broad `except Exception`)

- [ ] **Step 1: Add error-wrapping in `_retrieve_documents`**

Open `backend/rag/chain.py`. Add to imports near the top (after existing imports):

```python
import httpx
import openai
from qdrant_client.http.exceptions import UnexpectedResponse

from rag.exceptions import LLMError, RAGTimeoutError, RetrievalError
```

Replace `_retrieve_documents` (currently lines 141-145):

```python
def _retrieve_documents(question: str) -> list[Any]:
    retriever = get_retriever()
    try:
        if hasattr(retriever, "invoke"):
            return retriever.invoke(question)
        return retriever.get_relevant_documents(question)
    except (openai.APITimeoutError, httpx.TimeoutException) as exc:
        raise RAGTimeoutError(f"Retrieval timed out: {exc}") from exc
    except (openai.APIConnectionError, openai.APIError, UnexpectedResponse) as exc:
        raise RetrievalError(f"Retrieval failed: {exc}") from exc
```

- [ ] **Step 2: Update retrieval try-block in `invoke()`**

In `invoke()` (the block currently at lines 98-103), replace:

```python
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
```

The old broad `except Exception` is removed — retrieval failures are now classified, and the loud `Exception` will propagate (which is what we want, because a programmer error is not the same as a service outage).

- [ ] **Step 3: Wrap the LLM call in `invoke()`**

Replace lines 116-124 (the `answer = get_chain().invoke({...})` block) with:

```python
    try:
        answer = get_chain().invoke({
            "question": question,
            "user_context": user_context,
            "context": _format_documents(documents),
            "chat_history": chat_history,
            "user_display_name": personalization.user_display_name,
            "personalization_instructions": personalization.tone_instructions,
            "intent_instructions": intent_instructions,
        })
    except (openai.APITimeoutError, httpx.TimeoutException) as exc:
        raise RAGTimeoutError(f"LLM call timed out: {exc}") from exc
    except (openai.APIConnectionError, openai.APIError) as exc:
        raise LLMError(f"LLM call failed: {exc}") from exc
```

- [ ] **Step 4: Tighten exception handling in `router.classify_intent`**

Open `backend/rag/router.py`. Add to imports at the top (after `import json`):

```python
import httpx
import openai
```

Replace the `except Exception:` block at line 194:

```python
    except (openai.APITimeoutError, openai.APIError, httpx.TimeoutException) as exc:
        logger.warning("Intent classifier upstream error: %s", exc)
        return DEFAULT_INTENT
    except json.JSONDecodeError as exc:
        logger.info("Intent classifier returned non-JSON, defaulting (%s)", exc)
        return DEFAULT_INTENT
```

Unexpected exceptions (programming errors) now propagate instead of being silently mapped to `loan_inquiry`.

- [ ] **Step 5: Run existing tests**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_exceptions.py
```

The `test_rag_chain_retriever_fallback.py` test (which raises `ConnectionError` from a fake retriever) should still pass — the original broad `except Exception` in `invoke()` is replaced by `except RetrievalError`/`except RAGTimeoutError`. `ConnectionError` is neither, so the fallback test would now fail.

Update `test_rag_chain_retriever_fallback.py`. Replace the `FailingRetriever` class:

```python
from rag.exceptions import RetrievalError


class FailingRetriever:
    def invoke(self, question):
        raise RetrievalError("qdrant is down")
```

Re-run the test — it should now pass.

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
```

Expected: `RAG retriever fallback test passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/rag/chain.py backend/rag/router.py \
        backend/tests_local/test_rag_chain_retriever_fallback.py
git commit -m "refactor: specific exception types in chain + router (RetrievalError, LLMError)"
```

---

## Task 6: Add `error` column to `ChatMessage`

**Files:**
- Modify: `backend/models/chat.py:32-43`
- Modify: `backend/init_db.py:5-8` (`_COLUMN_MIGRATIONS`)

- [ ] **Step 1: Add column to ORM model**

Open `backend/models/chat.py`. Add to the import line at the top:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
```

(Adds `Boolean` to the existing imports.)

In the `ChatMessage` class, after the `sources` mapping (line 39), add:

```python
    error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
```

- [ ] **Step 2: Register the migration**

Open `backend/init_db.py`. In `_COLUMN_MIGRATIONS` (line 5-8), append:

```python
_COLUMN_MIGRATIONS = [
    "ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS loan_purpose VARCHAR",
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error BOOLEAN NOT NULL DEFAULT FALSE",
]
```

- [ ] **Step 3: Run migration**

```bash
cd backend && ../.venv/bin/python init_db.py
```

Expected output includes:
```
  ✓ error
```

(If the database is offline locally, skip the run — the SQL is idempotent and will execute when init_db is run against Supabase.)

- [ ] **Step 4: Commit**

```bash
git add backend/models/chat.py backend/init_db.py
git commit -m "feat: add ChatMessage.error column (idempotent migration)"
```

---

## Task 7: Atomic save in `chat_service.send`

**Files:**
- Modify: `backend/services/chat_service.py:15-68` (`send`)
- Test: `backend/tests_local/test_chat_service_atomic_save.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_chat_service_atomic_save.py`:

```python
"""Verify user message persists when RAG fails, and assistant row is marked error."""
import uuid
from types import SimpleNamespace
from contextlib import contextmanager

from fastapi import HTTPException

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession
from rag.exceptions import LLMError


class FakeQuery:
    def __init__(self, items):
        self._items = items
        self._filters = []

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def scalar(self):
        return 0  # rate-limit count = 0

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, user):
        self._user = user
        self._app = None
        self.added = []
        self.committed = 0

    def query(self, model):
        if model.__name__ == "User":
            return FakeQuery([self._user])
        if model.__name__ == "LoanApplication":
            return FakeQuery([])
        if model.__name__ == "ChatMessage":
            return FakeQuery([])
        if model.__name__ == "ChatSession":
            return FakeQuery([])
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChatSession) and obj.id is None:
            obj.id = uuid.uuid4()

    def flush(self):
        for obj in self.added:
            if isinstance(obj, ChatSession) and obj.id is None:
                obj.id = uuid.uuid4()

    def commit(self):
        self.committed += 1


def test_user_message_persists_when_rag_fails():
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", username="Minh")
    db = FakeDB(user)

    def fake_invoke(*args, **kwargs):
        raise LLMError("openrouter timeout")

    def fake_build_user_context(db, user_id):
        return "fake context block"

    original_invoke = chat_service._rag_invoke
    original_ctx = chat_service.build_user_context
    chat_service._rag_invoke = fake_invoke
    chat_service.build_user_context = fake_build_user_context
    try:
        raised = None
        try:
            chat_service.send(db, "a@b.com", "Tôi muốn vay 100 triệu")
        except HTTPException as exc:
            raised = exc
        assert raised is not None, "expected HTTPException"
        assert raised.status_code == 503
        assert "thử lại" in raised.detail.lower() or "sự cố" in raised.detail.lower()
    finally:
        chat_service._rag_invoke = original_invoke
        chat_service.build_user_context = original_ctx

    user_msgs = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "user"]
    assistant_msgs = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]

    assert len(user_msgs) == 1, "user message must persist"
    assert user_msgs[0].content == "Tôi muốn vay 100 triệu"
    assert len(assistant_msgs) == 1, "assistant placeholder must be saved"
    assert assistant_msgs[0].error is True
    assert db.committed >= 2, "expected two commits (user first, then assistant)"


if __name__ == "__main__":
    test_user_message_persists_when_rag_fails()
    print("chat_service atomic save test passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_atomic_save.py
```

Expected: failure because `chat_service._rag_invoke` doesn't exist yet (still uses lazy import).

- [ ] **Step 3: Refactor imports and `send()` for atomic save**

Open `backend/services/chat_service.py`. Replace the whole file with:

```python
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.application import LoanApplication
from models.chat import ChatMessage, ChatSession
from models.user import User
from rag.chain import invoke as _rag_invoke
from rag.context_builder import build_user_context
from rag.exceptions import RAGError
from rag.personalizer import build_personalization
from schemas.application import ApplicationCreate
from services import ml_service

logger = logging.getLogger(__name__)

_RAG_ERROR_MESSAGE = (
    "Xin lỗi, hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau ít phút."
)


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

    # 2) Re-fetch history excluding the message we just stored.
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(11)
        .all()
    )
    history_rows = [r for r in history_rows if r.id != user_message.id][:10]

    chat_history = []
    for row in reversed(history_rows):
        if row.role == "user":
            chat_history.append(HumanMessage(content=row.content))
        elif row.role == "assistant":
            chat_history.append(AIMessage(content=row.content))

    error_flag = False
    sources: list[dict[str, Any]] = []
    try:
        context = build_user_context(db, user.id)
        personalization = build_personalization(user, app)
        response_payload = _rag_invoke(
            payload_message, context, chat_history,
            personalization=personalization,
        )
        answer = response_payload.get("answer") or _RAG_ERROR_MESSAGE
        sources = _extract_sources(response_payload.get("source_documents", []))
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


def history(db: Session, user_email: str, session_id: Any = None) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .first()
        )

    if not session:
        return {"session_id": None, "messages": []}

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session_id": session.id,
        "messages": [
            {
                "role": row.role,
                "content": row.content,
                "sources": row.sources or [],
                "created_at": row.created_at,
            }
            for row in messages
        ],
    }


def _enforce_rate_limit(db: Session, user_id: Any) -> None:
    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    query_count = (
        db.query(func.count(ChatMessage.id))
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .filter(
            ChatSession.user_id == user_id,
            ChatMessage.role == "user",
            ChatMessage.created_at >= one_min_ago,
        )
        .scalar()
    )

    if query_count >= 20:
        raise HTTPException(status_code=429, detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau 1 phút.")


def _get_or_create_session(db: Session, user_id: Any, session_id: Any = None) -> ChatSession:
    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session

    session = ChatSession(user_id=user_id)
    db.add(session)
    db.flush()
    return session


def _ensure_latest_application_has_prediction(db: Session, user_id: Any) -> LoanApplication | None:
    app = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )
    if app is None:
        return None
    if app.default_probability is not None and app.model_version:
        return app

    payload = _application_to_payload(app)
    try:
        prediction = ml_service.predict(payload, db=db, user_id=user_id)
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ML model is not available or has an invalid contract: {exc}",
        ) from exc

    app.default_probability = prediction.get("default_probability")
    app.risk_level = prediction.get("risk_level")
    app.risk_score = prediction.get("risk_score")
    app.recommended_amount = prediction.get("recommended_amount")
    app.recommended_term = prediction.get("recommended_term")
    app.model_version = prediction.get("model_version")
    app.feature_snapshot = prediction.get("feature_snapshot")
    app.imputed_features = prediction.get("imputed_features")
    db.flush()
    return app


def _application_to_payload(app: LoanApplication) -> ApplicationCreate:
    return ApplicationCreate.model_construct(
        monthly_income=app.monthly_income,
        loan_amount=app.loan_amount,
        term=app.term,
        employment_status=app.employment_status,
        occupation_type=app.occupation_type or "Unknown",
        years_employed=app.years_employed or 0,
        dti=app.dti,
        is_homeowner=app.is_homeowner,
        listing_category=app.listing_category,
        credit_score=app.credit_score,
        num_bureau_records=app.num_bureau_records or 0,
        num_active_credit=app.num_active_credit or 0,
        total_overdue_amount=app.total_overdue_amount or 0,
        max_credit_overdue_days=app.max_credit_overdue_days or 0,
        has_bad_debt=app.has_bad_debt or False,
        income_verifiable_flag=app.income_verifiable_flag or False,
        age_years=app.age_years or 30,
        gender_male_flag=app.gender_male_flag or False,
        education_ordinal=app.education_ordinal or 3,
        cnt_children=app.cnt_children or 0,
        cnt_fam_members=app.cnt_fam_members or 1,
        is_married_flag=app.is_married_flag or False,
    )


def _extract_sources(documents: list[Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in documents:
        metadata = getattr(doc, "metadata", {}) or {}
        source = metadata.get("source") or metadata.get("file_path") or metadata.get("title")
        if not source:
            source = "knowledge_base"
        key = str(source)
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "source": key,
            "title": metadata.get("title") or key,
        })
    return sources
```

Key differences from the previous version:
- Top-level imports (no lazy `try/except ImportError`).
- `_rag_invoke` is a module-level alias so the test can monkey-patch it.
- User message saved + committed before chain call.
- Specific `except RAGError` (no broad `except Exception`).
- Returns 503 on RAG failure with assistant error row already persisted.

- [ ] **Step 4: Run the atomic-save test**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_atomic_save.py
```

Expected: `chat_service atomic save test passed`.

- [ ] **Step 5: Re-run the broader test suite to check for regressions**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_legacy_application_payload.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_routing_guardrail_personalized.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Expected: all pass. (`test_chat_legacy_application_payload.py` may need a small tweak if it asserts a specific HTTP shape — if it does, update assertions to match new flow.)

- [ ] **Step 6: Commit**

```bash
git add backend/services/chat_service.py backend/tests_local/test_chat_service_atomic_save.py
git commit -m "feat: atomic save in chat_service; raise 503 on RAGError"
```

---

## Task 8: Ingest CLI with `--dry-run` / `--recreate`

**Files:**
- Modify: `backend/rag/ingest.py`
- Test: `backend/tests_local/test_rag_ingest_cli.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_ingest_cli.py`:

```python
"""Verify ingest CLI flags: --dry-run skips upsert, --recreate calls delete."""
import sys
from types import SimpleNamespace

import rag.ingest as ingest


_calls = {"delete": 0, "upsert": 0, "embeddings": 0}


def _fake_load_documents():
    return [SimpleNamespace(metadata={"source": "fake.md"}, page_content="hello")]


def _fake_split_documents(docs):
    return docs


def _fake_get_embeddings():
    _calls["embeddings"] += 1
    return object()


def _fake_upsert(chunks, embeddings, collection_name, recreate):
    _calls["upsert"] += 1
    _calls["recreate"] = recreate
    _calls["collection"] = collection_name


def _run_main(argv):
    original_argv = sys.argv
    sys.argv = argv
    try:
        ingest.main()
    finally:
        sys.argv = original_argv


def test_dry_run_skips_upsert():
    _calls.update({"delete": 0, "upsert": 0, "embeddings": 0})
    original_load = ingest.load_documents
    original_split = ingest.split_documents
    original_emb = ingest.get_embeddings
    original_upsert = ingest.upsert_to_qdrant
    ingest.load_documents = _fake_load_documents
    ingest.split_documents = _fake_split_documents
    ingest.get_embeddings = _fake_get_embeddings
    ingest.upsert_to_qdrant = _fake_upsert
    try:
        _run_main(["ingest", "--dry-run"])
    finally:
        ingest.load_documents = original_load
        ingest.split_documents = original_split
        ingest.get_embeddings = original_emb
        ingest.upsert_to_qdrant = original_upsert

    assert _calls["upsert"] == 0, "dry-run must not call upsert"
    assert _calls["embeddings"] == 0, "dry-run must not initialise embeddings"


def test_default_upsert_no_recreate():
    _calls.update({"delete": 0, "upsert": 0, "embeddings": 0})
    original_load = ingest.load_documents
    original_split = ingest.split_documents
    original_emb = ingest.get_embeddings
    original_upsert = ingest.upsert_to_qdrant
    ingest.load_documents = _fake_load_documents
    ingest.split_documents = _fake_split_documents
    ingest.get_embeddings = _fake_get_embeddings
    ingest.upsert_to_qdrant = _fake_upsert
    try:
        _run_main(["ingest"])
    finally:
        ingest.load_documents = original_load
        ingest.split_documents = original_split
        ingest.get_embeddings = original_emb
        ingest.upsert_to_qdrant = original_upsert

    assert _calls["upsert"] == 1
    assert _calls["recreate"] is False


def test_recreate_flag_sets_recreate_true():
    _calls.update({"delete": 0, "upsert": 0, "embeddings": 0})
    original_load = ingest.load_documents
    original_split = ingest.split_documents
    original_emb = ingest.get_embeddings
    original_upsert = ingest.upsert_to_qdrant
    ingest.load_documents = _fake_load_documents
    ingest.split_documents = _fake_split_documents
    ingest.get_embeddings = _fake_get_embeddings
    ingest.upsert_to_qdrant = _fake_upsert
    try:
        _run_main(["ingest", "--recreate"])
    finally:
        ingest.load_documents = original_load
        ingest.split_documents = original_split
        ingest.get_embeddings = original_emb
        ingest.upsert_to_qdrant = original_upsert

    assert _calls["upsert"] == 1
    assert _calls["recreate"] is True


if __name__ == "__main__":
    test_dry_run_skips_upsert()
    test_default_upsert_no_recreate()
    test_recreate_flag_sets_recreate_true()
    print("rag ingest CLI tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_cli.py
```

Expected: failure (`ingest.main` does not exist or `upsert_to_qdrant` signature mismatch).

- [ ] **Step 3: Rewrite `backend/rag/ingest.py`**

Replace the file body:

```python
"""Build / update the Qdrant knowledge base.

Run:
    python -m rag.ingest             # incremental upsert (default)
    python -m rag.ingest --dry-run   # list docs + chunks, no writes
    python -m rag.ingest --recreate  # destructive: delete collection first
"""
import argparse
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
)
from core.config import settings

KNOWLEDGE_DIRS = [
    Path(__file__).parent / "knowledge",
    Path(__file__).parents[2] / "docs" / "data_dictionary",
]


def load_documents():
    docs = []
    for directory in KNOWLEDGE_DIRS:
        if not directory.exists():
            continue
        loader = DirectoryLoader(
            str(directory),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        loaded = loader.load()
        for doc in loaded:
            doc.metadata["source"] = Path(doc.metadata["source"]).name
        docs.extend(loaded)
    return docs


def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    return splitter.split_documents(docs)


def get_embeddings():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=OPENROUTER_BASE_URL,
    )


def upsert_to_qdrant(chunks, embeddings, collection_name=QDRANT_COLLECTION, recreate=False):
    """Upsert chunks into Qdrant.

    With ``recreate=True``, deletes the collection first (destructive).
    With ``recreate=False`` (default), appends to the existing collection.
    """
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    if recreate and client.collection_exists(collection_name=collection_name):
        client.delete_collection(collection_name=collection_name)

    if recreate or not client.collection_exists(collection_name=collection_name):
        QdrantVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=collection_name,
        )
        return

    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    store.add_documents(chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge base into Qdrant")
    parser.add_argument("--dry-run", action="store_true",
                        help="List documents & chunk count; do not call Qdrant or embeddings.")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete the collection before upsert (destructive).")
    parser.add_argument("--collection", default=QDRANT_COLLECTION,
                        help="Override the Qdrant collection name.")
    args = parser.parse_args()

    docs = load_documents()
    chunks = split_documents(docs)
    print(f"Loaded {len(docs)} documents → {len(chunks)} chunks")

    if args.dry_run:
        for i, chunk in enumerate(chunks[:2]):
            source = chunk.metadata.get("source", "?")
            print(f"--- Chunk {i + 1} ({source}) ---")
            print(chunk.page_content[:200])
        print(f"\nDry run: would upsert {len(chunks)} chunks to '{args.collection}'")
        return

    embeddings = get_embeddings()
    if args.recreate:
        print(f"⚠️  Recreating collection '{args.collection}' (destructive)")
    else:
        print(f"Upserting (incremental) to '{args.collection}'")
    upsert_to_qdrant(chunks, embeddings, collection_name=args.collection, recreate=args.recreate)
    print(f"Done. Ingested {len(chunks)} chunks.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the CLI test**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_cli.py
```

Expected: `rag ingest CLI tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/rag/ingest.py backend/tests_local/test_rag_ingest_cli.py
git commit -m "feat: ingest CLI with --dry-run, --recreate, --collection flags"
```

---

## Task 9: Update documentation

**Files:**
- Modify: `CLAUDE.md` (Qdrant section)

- [ ] **Step 1: Update the Qdrant ingest instructions in `CLAUDE.md`**

Find the Qdrant section in `/home/taitu/GitHub/Loan_ETL/CLAUDE.md` (around the "Qdrant (local, for RAG)" heading). Replace the ingest command block:

```bash
# Ingest knowledge base into Qdrant
cd backend

# Dry run — list docs + chunks, no writes
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --dry-run

# Incremental upsert (default — keeps existing collection)
PYTHONPATH=. ../.venv/bin/python -m rag.ingest

# Recreate collection (destructive — deletes existing data)
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --recreate
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update Qdrant ingest commands for new CLI flags"
```

---

## Task 10: Final verification — run every test in `tests_local/`

- [ ] **Step 1: List all RAG/chat tests**

```bash
ls backend/tests_local/test_rag_*.py backend/tests_local/test_chat_*.py
```

- [ ] **Step 2: Run them sequentially**

```bash
cd backend
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py; do
    echo "=== Running $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAILED: $f"; exit 1; }
done
echo "All RAG/chat tests passed"
```

Expected: `All RAG/chat tests passed`.

- [ ] **Step 3: Sanity check the live endpoint (optional, requires running services)**

If Qdrant + Supabase are up:

```bash
cd backend && ../.venv/bin/uvicorn main:app --reload
```

In another terminal:

```bash
# Hit /docs and confirm /chat is still listed and ChatResponse schema unchanged
curl -s http://localhost:8000/openapi.json | python -c "import sys, json; spec=json.load(sys.stdin); print(spec['paths']['/chat']['post']['responses'])"
```

Expected: 201 response shape unchanged. (HTTP 503 is added but is implicit in FastAPI's default error handling.)

- [ ] **Step 4: No additional commit needed** — verification only.

---

## Acceptance criteria (recap from spec)

- [x] `chat_service.py` has no `try/except ImportError` and no `except Exception as e`.
- [x] `chain.py` and `router.py` catch specific exception types (`openai.*`, `httpx.TimeoutException`, `qdrant_client.http.exceptions.UnexpectedResponse`).
- [x] `ChatOpenAI`, `OpenAIEmbeddings`, `QdrantClient` initialised with explicit `timeout` (and `max_retries` for the OpenAI clients) from `settings`.
- [x] User message persists when RAG fails; assistant row saved with `error=True`; endpoint returns HTTP 503.
- [x] `personalizer.build_personalization` no longer queries the DB (takes `user`, `app`).
- [x] `python -m rag.ingest --dry-run` performs no Qdrant or embedding calls.
- [x] All standalone tests in `backend/tests_local/test_rag_*.py` and `test_chat_*.py` pass.
