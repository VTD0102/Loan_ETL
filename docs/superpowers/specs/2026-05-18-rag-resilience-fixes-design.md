# RAG Resilience Fixes — Design

**Date**: 2026-05-18
**Status**: Approved
**Scope**: `backend/rag/`, `backend/services/chat_service.py`, `backend/core/config.py`, `backend/models/chat.py`

## Mục tiêu

Củng cố tầng RAG hiện tại trước khi build feature mới lên trên. Fix 5 vấn đề resilience đã được xác định trong phân tích ngày 2026-05-18:

1. Lazy import + broad `except Exception` nuốt lỗi.
2. Không có timeout/retry cho Qdrant, OpenRouter LLM, OpenAI embedding.
3. User message bị mất nếu `chain.invoke()` throw (commit không chạy).
4. Personalizer query lại User + LoanApplication trùng với data đã có ở `chat_service.send()`.
5. `rag/ingest.py` là one-shot script, xoá collection mỗi lần chạy, không có dry-run/CLI.

## Phạm vi không bao gồm

- Không đổi prompt templates, routing logic, guardrails (đã ổn).
- Không thay model (vẫn Gemini 2.5 Flash qua OpenRouter).
- Không thay vector store (vẫn Qdrant local).
- Không thêm circuit breaker / fallback LLM (out of scope).

---

## Section 1 — Refactor imports & exception handling

### Hiện trạng

- `backend/services/chat_service.py:32-34`: lazy import LangChain + `rag.chain` trong try/except block.
- `backend/services/chat_service.py:50-55`: `except ImportError` + `except Exception as e` — nuốt mọi lỗi, trả `200 OK` kèm error string trong body.
- `backend/rag/chain.py:101-103, 110-111`: broad `except Exception` cho retrieval và personalization.

### Thay đổi

**Tạo module mới `backend/rag/exceptions.py`**:

```python
class RAGError(Exception):
    """Base exception for RAG pipeline failures."""

class RetrievalError(RAGError):
    """Qdrant or embedding service failure."""

class LLMError(RAGError):
    """OpenRouter / LLM call failure."""

class RAGTimeoutError(RAGError):
    """Upstream call exceeded timeout budget."""
```

**`backend/services/chat_service.py`**:
- Move imports lên top-level (xoá try/except ImportError):
  ```python
  from langchain_core.messages import AIMessage, HumanMessage
  from rag.chain import invoke as rag_invoke
  from rag.context_builder import build_user_context
  from rag.exceptions import RAGError
  ```
- Trong `send()`: catch `RAGError` → raise `HTTPException(status_code=503, detail="<msg tiếng Việt>")`. Vẫn save assistant message với placeholder text + `error=True` trước khi raise.
- Bỏ generic `except Exception` — để propagate thành 500 nếu là lỗi không lường trước.

**`backend/rag/chain.py`**:
- Catch cụ thể trong `_retrieve_documents`:
  - `httpx.TimeoutException`, `qdrant_client.http.exceptions.UnexpectedResponse`, `openai.APITimeoutError`, `openai.APIConnectionError` → wrap thành `RetrievalError`.
  - Re-raise nếu là exception khác.
- Trong `invoke()`: catch `RetrievalError` → log + continue with empty docs (giữ behavior hiện tại). Catch `LLMError`/`RAGTimeoutError` từ `get_chain().invoke()` → propagate.
- Catch cụ thể trong LLM call (`get_chain().invoke({...})`): wrap `openai.APITimeoutError`, `openai.APIError`, `httpx.TimeoutException` thành `LLMError`/`RAGTimeoutError`.

**`backend/rag/router.py`**:
- Trong `classify_intent`: thay `except Exception` (line 194) thành catch cụ thể (`openai.APIError`, `httpx.TimeoutException`, `json.JSONDecodeError`). Vẫn fallback về `DEFAULT_INTENT` — đây là acceptable degradation.

### Trade-off

- Frontend hiện đang đọc body text khi có lỗi RAG. Sẽ cần update để handle HTTP 503 và hiển thị error banner. Sẽ liệt kê trong implementation plan.
- Mock mode (`npm run mock`) không bị ảnh hưởng.

---

## Section 2 — Timeout + retry cho external calls

### Hiện trạng

- `backend/rag/chain.py:44-49`: `ChatOpenAI(...)` không set `timeout` hay `max_retries` explicit (dùng default của SDK, có thể vô hạn hoặc không nhất quán giữa version).
- `backend/rag/router.py:130-136`: classifier LLM same issue.
- `backend/rag/retriever.py:16-26`: `OpenAIEmbeddings` và `QdrantVectorStore.from_existing_collection` không set timeout.

### Thay đổi

**`backend/core/config.py`**: thêm settings (có default, không bắt buộc đặt trong `.env`):

```python
rag_llm_timeout_seconds: float = 30.0
rag_llm_max_retries: int = 2
rag_embedding_timeout_seconds: float = 10.0
rag_embedding_max_retries: int = 2
rag_qdrant_timeout_seconds: float = 5.0
```

**`backend/rag/chain.py:44`** — `get_chain()`:
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

**`backend/rag/router.py:130`** — same fix cho classifier LLM (timeout có thể thấp hơn, dùng cùng setting để đơn giản).

**`backend/rag/retriever.py`** — split khởi tạo:
```python
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore

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

### Trade-off

- Tổng latency tối đa cho 1 request: ~30s LLM + ~10s embedding + ~5s Qdrant + classifier ~30s = ~75s worst case. Acceptable cho chat (user expectation: <60s với loading indicator).
- Default values đặt ở `core/config.py` để dễ tune. Không hardcode.

---

## Section 3 — Atomic save: user message tồn tại kể cả khi RAG fail

### Hiện trạng

`backend/services/chat_service.py:60-62`:
```python
db.add(ChatMessage(... role="user" ...))
db.add(ChatMessage(... role="assistant" ...))
db.commit()
```

Nếu `chain.invoke()` throw exception trước line này → cả 2 message bị mất (commit không chạy).

### Thay đổi

**Database migration**:
- `backend/models/chat.py`: thêm column `error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)` vào `ChatMessage`.
- `backend/init_db.py` đã có pattern `_COLUMN_MIGRATIONS` (idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Thêm:
  ```python
  "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error BOOLEAN NOT NULL DEFAULT FALSE",
  ```

**Refactor `send()`** trong `backend/services/chat_service.py`:

```python
def send(db, user_email, payload_message, session_id=None):
    user = ...
    _enforce_rate_limit(db, user.id)
    app = _ensure_latest_application_has_prediction(db, user.id)  # giờ return app
    session = _get_or_create_session(db, user.id, session_id)

    # 1. Save user message + flush early
    user_msg = ChatMessage(session_id=session.id, role="user", content=payload_message)
    db.add(user_msg)
    if not session.title:
        session.title = payload_message.strip()[:80]
    db.commit()  # ← user message bền vững từ giờ

    # 2. Build context + invoke chain
    history_rows = db.query(ChatMessage).filter(...).order_by(...desc()).limit(11).all()
    # filter out user_msg vừa save để không gửi lại làm history
    history_rows = [r for r in history_rows if r.id != user_msg.id][:10]
    chat_history = [...]

    try:
        context = build_user_context(db, user.id)
        personalization = build_personalization(user, app)  # ← từ Section 4
        response_payload = rag_invoke(payload_message, context, chat_history, personalization)
        answer = response_payload.get("answer", "")
        sources = _extract_sources(response_payload.get("source_documents", []))
        error_flag = False
    except RAGError as exc:
        logger.exception("RAG pipeline failed")
        answer = "Xin lỗi, hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau ít phút."
        sources = []
        error_flag = True

    # 3. Save assistant message + update session
    db.add(ChatMessage(
        session_id=session.id, role="assistant",
        content=answer, sources=sources, error=error_flag,
    ))
    session.updated_at = datetime.utcnow()
    db.commit()

    if error_flag:
        raise HTTPException(status_code=503, detail=answer)

    return {"response": answer, "session_id": session.id, "sources": sources}
```

### Trade-off

- 2 commits/request (vs 1) → ~10-20ms latency thêm. Đổi lấy: zero user-message loss.
- Cần Alembic-style migration cho column `error`. Sẽ dùng simple `ALTER TABLE` script trong `backend/init_db.py` (idempotent check `if not column_exists`).
- Khi 503, frontend đã có data assistant message với error flag (qua endpoint `history`) → admin/dev có thể trace.

---

## Section 4 — Personalizer: bỏ duplicate DB query

### Hiện trạng

- `backend/rag/personalizer.py:148-180` (`build_personalization(db, user_id)`): query `User` + `LoanApplication` mỗi request.
- `chat_service.send()` đã có `user` object. `_ensure_latest_application_has_prediction` đã query latest app nhưng không return.

### Thay đổi

**`backend/rag/personalizer.py`** — đổi signature:
```python
def build_personalization(
    user: User | None,
    app: LoanApplication | None,
) -> PersonalizationContext:
    ctx = PersonalizationContext()
    if user and user.username:
        ctx.user_display_name = user.username
    ctx.application_status = (app.status or "").lower() if app else None
    tone_config = _STATUS_TONES.get(ctx.application_status) or _STATUS_TONES.get(None)
    ctx.tone_instructions = tone_config["tone"]
    ctx.greeting_line = tone_config["greeting"]
    return ctx
```

Không còn import `Session`, không còn query.

**`backend/rag/chain.py`** — `invoke()` signature đổi:
```python
def invoke(
    question: str,
    user_context: str,
    chat_history: list,
    personalization: PersonalizationContext | None = None,
) -> dict:
    ...
    if personalization is None:
        personalization = PersonalizationContext()
    intent_instructions = get_intent_instructions(intent)
    answer = get_chain().invoke({
        ...
        "user_display_name": personalization.user_display_name,
        "personalization_instructions": personalization.tone_instructions,
        ...
    })
```

Không còn `db` và `user_id` params.

**`backend/services/chat_service.py`**:
- `_ensure_latest_application_has_prediction` return app object (hoặc None nếu user chưa có application).
- Call `build_personalization(user, app)` rồi pass vào `rag_invoke`.

### Trade-off

- Tách `rag.chain` khỏi DB hoàn toàn — cleaner architecture, dễ unit test.
- Test cũ `test_rag_chain_retriever_fallback.py` không bị ảnh hưởng (test không pass `db`/`user_id`).
- `test_rag_routing_guardrail_personalized.py` cần update signature.

---

## Section 5 — Ingest CLI với dry-run & incremental mode

### Hiện trạng

`backend/rag/ingest.py:58-59`: `client.delete_collection()` rồi recreate — mỗi lần chạy mất hết data trong collection (rủi ro nếu chạy nhầm trên production Qdrant).

### Thay đổi

**`backend/rag/ingest.py`** — thêm argparse:

```python
import argparse

def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge base into Qdrant")
    parser.add_argument("--dry-run", action="store_true",
                        help="List documents & chunk count, do not upsert")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete collection before upsert (destructive)")
    parser.add_argument("--collection", default=QDRANT_COLLECTION,
                        help="Override collection name")
    args = parser.parse_args()

    docs = load_documents()
    chunks = split_documents(docs)
    print(f"Loaded {len(docs)} documents → {len(chunks)} chunks")

    if args.dry_run:
        for i, chunk in enumerate(chunks[:2]):
            print(f"--- Chunk {i+1} ({chunk.metadata.get('source')}) ---")
            print(chunk.page_content[:200])
        print(f"\nDry run: would upsert {len(chunks)} chunks to '{args.collection}'")
        return

    embeddings = get_embeddings()
    if args.recreate:
        print(f"⚠️  Recreating collection '{args.collection}' (destructive)")
        upsert_to_qdrant(chunks, embeddings, collection_name=args.collection, recreate=True)
    else:
        print(f"Upserting (incremental) to '{args.collection}'")
        upsert_to_qdrant(chunks, embeddings, collection_name=args.collection, recreate=False)
    print(f"Done. Ingested {len(chunks)} chunks.")

if __name__ == "__main__":
    main()
```

`upsert_to_qdrant` đổi signature: nhận `collection_name` và `recreate` flag. Khi `recreate=False`, dùng `vectorstore.add_documents(chunks)` thay vì `from_documents` (incremental upsert).

### Trade-off

- Default behavior change: `python -m rag.ingest` không xoá collection nữa. Phải dùng `--recreate` để xoá. Update `CLAUDE.md` và README để document.
- Incremental upsert có thể tạo duplicate chunks nếu chạy 2 lần với data y hệt. Tài liệu mới sẽ thêm IDs khác. Trade-off: tránh được xoá nhầm là ưu tiên cao hơn việc dedup.

---

## Section 6 — Tests

Pattern: standalone scripts trong `backend/tests_local/`, theo style hiện có.

### Tests mới

1. **`test_chat_service_atomic_save.py`**
   - Monkey-patch `rag_invoke` để throw `RAGError`.
   - Call `chat_service.send()` qua test client (hoặc trực tiếp với fake db session).
   - Assert: 503 raised, `db.query(ChatMessage).filter(role="user")` returns the user message, assistant message exists với `error=True`.

2. **`test_rag_timeout_config.py`**
   - Monkey-patch `ChatOpenAI`, `OpenAIEmbeddings`, `QdrantClient` constructors để capture kwargs.
   - Call `get_chain()`, `get_retriever()`, `_get_classifier_llm()`.
   - Assert: kwargs chứa `timeout` và `max_retries` từ settings.

3. **`test_rag_ingest_cli.py`**
   - Mock `load_documents` để return fake docs.
   - Monkey-patch `upsert_to_qdrant` và `QdrantClient.delete_collection` để record calls.
   - Run `ingest.main()` với `sys.argv = ["ingest", "--dry-run"]`.
   - Assert: `upsert_to_qdrant` không được gọi, `delete_collection` không được gọi.

4. **`test_rag_personalization_no_db.py`**
   - Tạo fake `User` và `LoanApplication` namespace objects.
   - Call `build_personalization(user, app)`.
   - Assert: returns correct `PersonalizationContext` for status, không cần db.

### Tests hiện có cần update

- `test_rag_chain_retriever_fallback.py`: `chain.invoke()` signature đổi (bỏ `db`/`user_id`). Cần update test nhỏ.
- `test_rag_routing_guardrail_personalized.py`: cần update để pass `personalization` thay vì `db`/`user_id`.

---

## Migration order (sẽ vào implementation plan)

1. Section 4 (personalizer refactor) — tự contained.
2. Section 2 (timeout config) — additive, low risk.
3. Section 1 (imports + exceptions) — đụng chat_service + chain, làm sau khi 2,4 ổn.
4. Section 3 (atomic save + ChatMessage.error column) — DB migration, cần test kỹ.
5. Section 5 (ingest CLI) — độc lập.
6. Section 6 (tests) — interleave với mỗi section trên.

## Acceptance criteria

- Tất cả test trong `backend/tests_local/test_rag_*.py` + `test_chat_*.py` pass.
- `python -m rag.ingest --dry-run` chạy được, không gọi Qdrant write.
- Khi Qdrant down: `/chat` trả lời được (empty docs) — verify bằng test integration.
- Khi OpenRouter timeout 30s: `/chat` trả HTTP 503 với message tiếng Việt, user message persist trong DB với assistant message `error=True`.
- `chat_service.py` không còn `try/except` cho imports, không còn `except Exception as e`.

## Out of scope (next iteration)

- Circuit breaker / fallback LLM khi OpenRouter down hoàn toàn.
- Streaming response (SSE).
- Personalization caching (đã loại nhờ pass-through).
- Frontend update để render error banner cho HTTP 503 — sẽ note trong implementation plan để track riêng.
