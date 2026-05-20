# RAG Code Review — Đánh giá lỗi & tối ưu

**Ngày:** 2026-05-19  
**Phạm vi:** Toàn bộ module `backend/rag/` (18 files) + tích hợp trong `services/chat_service.py`

---

## Tổng quan

Hệ thống RAG hiện tại có kiến trúc tốt với pipeline 6 bước rõ ràng (guardrail → route → retrieve → personalize → LLM → guardrail), hỗ trợ hybrid retrieval (BM25 + dense) + reranker + parent document expansion. Code đã trải qua nhiều vòng eval cải tiến (hybrid, rerank V1/V1.1).

Dưới đây là tổng hợp các **lỗi** cần sửa và các **điểm chưa tối ưu** kèm giải pháp.

---------------------KẾT QUẢ SAU KHI SỬA-------------------
Đã sửa đổi và tối ưu hóa hệ thống RAG thành công dựa trên bản kế hoạch review 2026-05-19-rag-code-review.md.

Các thay đổi cụ thể đã thực hiện:
Sửa lỗi exports (backend/rag/__init__.py):

Loại bỏ các export không tồn tại (get_or_create_session, load_chat_history).
Thêm export chuẩn cho load_memory.
Tối ưu hóa Memory & Singleton cache (backend/rag/memory.py):

Loại bỏ bộ lọc trùng lặp của exclude_message_id.
Lưu trữ cache _summary_llm instance thay vì khởi tạo lại ChatOpenAI trong mỗi cuộc hội thoại cần tóm tắt.
Chuyển datetime.utcnow() lỗi thời sang datetime.now(timezone.utc).
Đảm bảo Thread-safety cho Singletons:

Tích hợp threading.Lock trong backend/rag/chain.py (get_chain), backend/rag/retriever.py (get_retriever), và backend/rag/router.py (_get_classifier_llm) giúp bảo vệ cache khỏi race condition khi chạy trên môi trường FastAPI đa luồng.
Sửa lỗi logic & bảo mật thông tin trong Prompt Context (backend/rag/context_builder.py):

Sửa hàm _band để trả về "Không có dữ liệu" nếu credit_score bị thiếu (None/0) thay vì trả về "Kém (< 580)" gây hiểu nhầm.
Loại bỏ model_version khỏi text context gửi cho LLM nhằm tránh bị LLM trích dẫn và kích hoạt bộ lọc bảo mật đầu ra (leak guardrail).
Nâng cao khả năng giám sát Guardrails (backend/rag/guardrails.py):

Bổ sung logs chi tiết (logger.warning) ghi lại chính xác pattern và nội dung nào bị phát hiện rò rỉ dữ liệu trước khi chặn response đầu ra của LLM.
Giảm thiểu cuộc gọi ML dư thừa (backend/services/chat_service.py):

Thêm bộ lọc trạng thái để bỏ qua các cuộc gọi dự đoán rủi ro ML mới đối với các hồ sơ vay cũ đã có kết quả cuối cùng (APPROVED, ADMIN_REJECTED, AUTO_REJECTED).
Kết quả chạy thử nghiệm cục bộ (tests_local/):
Tất cả các bài kiểm tra tự động liên quan đều đã chạy và vượt qua thành công:

test_memory_token_estimation.py — PASS
test_rag_exceptions.py — PASS
test_memory_short_conversation_no_summary.py — PASS
test_memory_skips_summarize_if_already_covered.py — PASS
test_memory_excludes_error_rows.py — PASS
test_rag_eval_metrics.py — PASS
test_rag_eval_diff.py — PASS
test_rag_eval_runner.py — PASS
test_guardrails.py — PASS (xác nhận log pattern rò rỉ hoạt động chính xác)
test_router.py — PASS
test_rag_routing_guardrail_personalized.py — PASS
----------------------------------------------------------

## A. LỖI CẦN SỬA (Bugs)

### A1. `__init__.py` export tên hàm không tồn tại

**File:** `backend/rag/__init__.py` (L7, L10)

**Mô tả:** `_EXPORTS` khai báo 2 tên không tồn tại trong module `rag.memory`:
- `"get_or_create_session"` → hàm trong `memory.py` thực tế là `_get_or_create_session` (private, bắt đầu bằng `_`) — nhưng thực ra hàm này nằm trong `chat_service.py`, không phải `memory.py`.
- `"load_chat_history"` → không có hàm nào tên này trong `memory.py`; hàm thực tế là `load_memory`.

**Ảnh hưởng:** Gọi `from rag import load_chat_history` hoặc `from rag import get_or_create_session` sẽ raise `AttributeError` tại runtime.

**Cách khắc phục:**

```diff
 _EXPORTS = {
     ...
-    "get_or_create_session": ("rag.memory", "get_or_create_session"),
-    "load_chat_history": ("rag.memory", "load_chat_history"),
+    "load_memory": ("rag.memory", "load_memory"),
     ...
 }
```

Xóa 2 entry cũ, thêm entry đúng. Nếu không có consumer nào import qua `rag.__init__`, có thể bỏ luôn.

---

### A2. `memory.py` lọc `exclude_message_id` 2 lần (dư thừa)

**File:** `backend/rag/memory.py` (L153–163)

**Mô tả:** Query đã có `.filter(ChatMessage.id != exclude_message_id)` ở L159, nhưng sau khi query xong lại lọc thêm 1 lần nữa bằng Python list comprehension ở L162–163:

```python
rows = query.order_by(ChatMessage.created_at.desc()).all()
if exclude_message_id is not None:
    rows = [row for row in rows if row.id != exclude_message_id]  # dư thừa
```

**Ảnh hưởng:** Không gây sai kết quả (chỉ filter thừa), nhưng tốn CPU xử lý list.

**Cách khắc phục:** Xóa đoạn L162–163. Bộ lọc SQL ở L159 đã đủ.

---

### A3. `retriever.py` + `chain.py` dùng module-level singleton không thread-safe

**File:** `backend/rag/retriever.py` (L72, `_retriever`), `backend/rag/chain.py` (L36, `_chain`), `backend/rag/router.py` (L127, `_classifier_llm`)

**Mô tả:** Cả 3 file đều dùng `global` variable + `if is None` pattern để cache singleton. Với FastAPI (chạy async trên uvicorn, nhiều thread workers), pattern này có race condition: 2 requests đồng thời có thể tạo 2 instance.

**Ảnh hưởng:** Không gây crash nhưng có thể tạo duplicate resources (duplicate QdrantClient, duplicate LLM client). Trong thực tế với các service stateless, hậu quả nhẹ nhưng là code smell.

**Cách khắc phục (nhẹ):** Dùng `functools.lru_cache(maxsize=1)`:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_retriever():
    ...
```

Hoặc nếu muốn chặt chẽ hơn, dùng `threading.Lock()`.

---

### A4. `context_builder.py` tính `_band()` sai khi giá trị = 0

**File:** `backend/rag/context_builder.py` (L362–366)

**Mô tả:** Hàm `_band(value, bands)` dùng `value < threshold` — khi `credit_score = 0` (hoặc `None` được cast thành `0`), kết quả trả về là `"Kém (< 580)"` khi không có điểm tín dụng nào cả, gây hiểu nhầm cho LLM.

**Cách khắc phục:** Thêm guard cho `None`/`0`:

```python
def _band(value: float | None, bands: list[tuple]) -> str:
    if value is None or value == 0:
        return "Không có dữ liệu"
    for threshold, label in bands:
        if value < threshold:
            return label
    return bands[-1][1]
```

---

## B. CHƯA TỐI ƯU — ĐỀ XUẤT CẢI THIỆN

### B1. Router gọi LLM cho mỗi tin nhắn → tốn latency + token

**File:** `backend/rag/router.py` (L174–204)

**Hiện trạng:** Nếu không match bất kỳ keyword pattern nào, `classify_intent()` gọi LLM (Gemini Flash) để phân loại intent → thêm 500ms–2s latency + chi phí token cho mỗi tin nhắn.

**Đánh giá:** Keyword patterns đã cover phần lớn trường hợp phổ biến, nhưng vẫn có ~30% câu hỏi tự nhiên rơi vào LLM path.

**Giải pháp (nếu cần tối ưu):**
1. **Mở rộng keyword patterns** — thêm 10–15 pattern phổ biến dựa trên log thực tế (ví dụ: `"vay bao nhiêu"`, `"nợ xấu"`, `"làm sao để"`)
2. **Cache kết quả LLM** — dùng simple LRU cache cho ~100 query gần nhất (hash `question.strip().lower()`)
3. **Dùng embedding classifier nhẹ** — thay LLM bằng một bộ phân loại nhúng (ví dụ: cosine similarity với mẫu intent) nếu số intent ít (6 intents)

**Ưu tiên:** Thấp — chỉ cần thiết khi traffic tăng và chi phí LLM đáng kể.

---

### B2. `_format_documents()` không giới hạn token trước khi đưa vào prompt

**File:** `backend/rag/chain.py` (L158–178)

**Hiện trạng:** Hàm nối tất cả parent documents thành 1 chuỗi `context` dài tùy ý. Với `TOP_K=4` parent docs, mỗi parent tối đa 3500 chars → context tối đa ~14,000 chars (~3,500 tokens). Trong trường hợp parent docs dài + user context + summary → có thể vượt context window.

**Đánh giá:** Chưa gây vấn đề thực tế (Gemini Flash có 1M context window) nhưng đang tốn token không cần thiết cho những document dài ít liên quan.

**Giải pháp:** Thêm `max_context_chars` cap:

```python
def _format_documents(documents: list[Any], max_chars: int = 8000) -> str:
    ...
    result = "\n\n".join(chunks)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n[...đã cắt bớt...]"
    return result
```

**Ưu tiên:** Thấp — Gemini 2.5 Flash có context window rất lớn, chưa bị ảnh hưởng.

---

### B3. `memory.py` summary LLM dùng cùng model chính → tốn chi phí

**File:** `backend/rag/memory.py` (L101–113)

**Hiện trạng:** `_summarize()` tạo một `ChatOpenAI(model=LLM_MODEL)` mới mỗi lần cần tóm tắt, dùng cùng model chính (Gemini Flash). Tóm tắt hội thoại là task đơn giản — có thể dùng model rẻ hơn/nhỏ hơn.

**Đánh giá:** Chấp nhận được — Gemini Flash đã rẻ (so với Opus). Nhưng nếu cần tối ưu chi phí thì đây là nơi dễ cắt giảm nhất.

**Giải pháp:** Thêm config `RAG_SUMMARY_MODEL` riêng (ví dụ `google/gemini-2.0-flash-lite`) hoặc giữ nguyên nếu chi phí không đáng kể.

**Ưu tiên:** Rất thấp.

---

### B4. Reranker tạo mới `ChatOpenAI` instance trong `_summarize()` mỗi lần

**File:** `backend/rag/memory.py` (L103–113)

**Hiện trạng:** Mỗi lần gọi `_summarize()`, code tạo mới `ChatOpenAI(...)` instance thay vì cache/reuse.

**Giải pháp:** Cache LLM instance tương tự `_chain` trong `chain.py`:

```python
_summary_llm = None

def _get_summary_llm():
    global _summary_llm
    if _summary_llm is None:
        _summary_llm = ChatOpenAI(...)
    return _summary_llm
```

**Ưu tiên:** Trung bình — giảm overhead khởi tạo khi summary được gọi nhiều.

---

### B5. `context_builder.py` hiển thị `model_version` cho user

**File:** `backend/rag/context_builder.py` (L307–308)

**Hiện trạng:** Context truyền vào LLM chứa `model_version` (ví dụ `"v4"`). Thông tin này là metadata nội bộ, có thể bị LLM trích dẫn trong câu trả lời → bị output guardrail chặn bởi pattern `model_version\s*[:=]\s*['\"]` (L91 trong guardrails.py).

**Đánh giá:** Guard đã hoạt động, nhưng tốt hơn là không cho LLM thấy từ đầu.

**Giải pháp:** Xóa `model_version` khỏi `_json_to_text()` output — chỉ giữ trong `build_context_json()` cho API debug.

**Ưu tiên:** Thấp.

---

### B6. `ingest.py` không có progress/logging khi upsert nhiều chunks

**File:** `backend/rag/ingest.py` (L86)

**Hiện trạng:** `store.add_documents(chunks)` upload tất cả chunks một lần, không có progress bar hay log batch.

**Giải pháp:** Chia thành batches + progress log:

```python
BATCH_SIZE = 50
for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i:i + BATCH_SIZE]
    store.add_documents(batch)
    print(f"  Ingested {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks")
```

**Ưu tiên:** Thấp — chỉ quan trọng khi knowledge base lớn.

---

### B7. `guardrails.py` output check không log pattern nào đã match

**File:** `backend/rag/guardrails.py` (L173–182)

**Hiện trạng:** Khi `_INTERNAL_LEAK_PATTERNS` match, response bị block nhưng log chỉ ghi `"internal_leak"` — không ghi pattern nào match hay nội dung gì bị phát hiện.

**Giải pháp:** Ghi log chi tiết hơn (cho admin debug) nhưng KHÔNG return cho user:

```python
for pattern in _INTERNAL_LEAK_PATTERNS:
    match = pattern.search(response)
    if match:
        logger.warning("Output guardrail: internal leak pattern matched [%s] near: %s",
                       pattern.pattern[:30], match.group()[:50])
        return GuardrailResult(...)
```

**Ưu tiên:** Trung bình — rất hữu ích cho debugging production.

---

### B8. `chat_service.py` gọi ML prediction cho user không có đơn vay → lãng phí

**File:** `backend/services/chat_service.py` (L177–207)

**Hiện trạng:** `_ensure_latest_application_has_prediction()` chạy ML prediction cho bất kỳ đơn nào thiếu `default_probability`, kể cả đơn cũ đã bị reject. Điều này xảy ra mỗi khi user gửi chat.

**Đánh giá:** Nhẹ — ML prediction đã được cache trên DB record sau lần đầu. Chỉ tốn khi gặp legacy row thực sự thiếu prediction.

**Giải pháp:** Thêm guard để chỉ chạy prediction cho đơn PENDING_REVIEW hoặc AWAITING_INFO:

```python
if app.status in ("PENDING_REVIEW", "AWAITING_INFO") and app.default_probability is None:
    # run prediction
```

**Ưu tiên:** Thấp.

---

## C. TỔNG KẾT

### Bảng tổng hợp

| # | Loại | Module | Mô tả ngắn | Mức ưu tiên |
|---|------|--------|-------------|-------------|
| A1 | 🔴 Bug | `__init__.py` | Export tên hàm không tồn tại | **Cao** |
| A2 | 🟡 Bug nhẹ | `memory.py` | Lọc `exclude_message_id` 2 lần | Thấp |
| A3 | 🟡 Code smell | `retriever.py`, `chain.py`, `router.py` | Singleton global không thread-safe | Trung bình |
| A4 | 🟡 Bug logic | `context_builder.py` | `_band(0, ...)` trả kết quả sai | Trung bình |
| B1 | 🔵 Tối ưu | `router.py` | LLM call cho mỗi unmatched intent | Thấp |
| B2 | 🔵 Tối ưu | `chain.py` | Không giới hạn context chars | Rất thấp |
| B3 | 🔵 Tối ưu | `memory.py` | Summary dùng model chính | Rất thấp |
| B4 | 🔵 Tối ưu | `memory.py` | Tạo mới LLM instance mỗi lần summarize | Trung bình |
| B5 | 🔵 Tối ưu | `context_builder.py` | Lộ `model_version` cho LLM | Thấp |
| B6 | 🔵 Tối ưu | `ingest.py` | Không có progress khi upsert | Thấp |
| B7 | 🔵 Tối ưu | `guardrails.py` | Không log chi tiết khi block output | Trung bình |
| B8 | 🔵 Tối ưu | `chat_service.py` | ML prediction cho đơn không cần thiết | Thấp |

### Đánh giá tổng thể

- **Kiến trúc:** ✅ Tốt — pipeline rõ ràng, modular, có exception hierarchy, có eval framework.
- **Guardrails:** ✅ Kỹ — cả input (injection + PII) và output (leak + promise + length).
- **Retrieval:** ✅ Tối ưu — hybrid (BM25 + dense) + reranker + parent expansion.
- **Memory:** ✅ Hợp lý — sliding window + lazy summary với token budget.
- **Personalization:** ✅ Sâu — 7 trạng thái đơn vay × 6 intents, tone riêng cho từng context.
- **Eval framework:** ✅ Hoàn chỉnh — 31 test cases, deterministic metrics, baseline diff, CLI runner.

**Kết luận:** RAG pipeline đã ở mức sản xuất tốt. Chỉ có **A1** (export sai tên) cần sửa ngay. Các item khác là cải thiện chất lượng code, không ảnh hưởng functionality.
