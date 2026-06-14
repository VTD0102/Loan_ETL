# Sườn Báo Cáo Học Thuật: Hệ Thống RAG trong Dự Án CreditIntel

> **Môn học:** Hệ Quản Trị Cơ Sở Dữ Liệu  
> **Dự án:** CreditIntel — Nền tảng đánh giá rủi ro tín dụng ứng dụng AI  
> **Module báo cáo:** Retrieval-Augmented Generation (RAG)

---

## Mục lục đề xuất

1. [Giới thiệu](#1-giới-thiệu)
2. [Cơ sở lý thuyết](#2-cơ-sở-lý-thuyết)
3. [Kiến trúc tổng quan](#3-kiến-trúc-tổng-quan)
4. [Giai đoạn Ingest — Nạp và phân mảnh tài liệu](#4-giai-đoạn-ingest)
5. [Giai đoạn Runtime — Pipeline xử lý câu hỏi](#5-giai-đoạn-runtime)
6. [Nguồn tri thức](#6-nguồn-tri-thức)
7. [Các kỹ thuật nâng cao](#7-các-kỹ-thuật-nâng-cao)
8. [Đánh giá chất lượng](#8-đánh-giá-chất-lượng)
9. [Điểm mạnh, hạn chế và hướng phát triển](#9-điểm-mạnh-hạn-chế-và-hướng-phát-triển)
10. [Kết luận](#10-kết-luận)

---

## 1. Giới thiệu

### 1.1 Bối cảnh và động lực
- Vấn đề: Chatbot truyền thống không có kiến thức chuyên ngành → hay bịa thông tin (hallucination)
- Giải pháp: RAG — kết hợp tìm kiếm tài liệu + sinh câu trả lời bằng LLM
- Mục tiêu trong CreditIntel: Xây dựng trợ lý AI tư vấn tín dụng, giải thích kết quả ML, hướng dẫn quy trình vay — **có trích dẫn nguồn, không bịa thông tin**

### 1.2 Phạm vi báo cáo
- Module `backend/rag/` — 17 file Python (không tính `__pycache__`, `.env`)
- Tích hợp với `chat_service.py` (điều phối) và `loan_adjustment_tool.py` (tool calling, nằm trong `services/`)
- Các công nghệ: LangChain, Qdrant, OpenRouter (Gemini 2.5 Flash), FastEmbed

### 1.3 Đóng góp chính
- Pipeline RAG đa giai đoạn 6 bước (Guardrail → Router → Retrieval → Personalization → Generation → Output Guardrail)
- Hybrid Search (Dense + Sparse BM25) + Cross-Encoder Reranking
- Parent-Child Chunking cho tài liệu Markdown
- Cá nhân hóa giọng điệu theo 7 trạng thái đơn vay
- Bộ đánh giá offline tự xây (eval framework) với 2 chỉ số chính: Faithfulness và Context Precision

---

## 2. Cơ sở lý thuyết

### 2.1 RAG là gì?
- Định nghĩa: Retrieval-Augmented Generation (Lewis et al., 2020)
- So sánh với chatbot thuần LLM (không RAG): hallucination, kiến thức không cập nhật
- Kiến trúc chuẩn: Indexing → Retrieval → Generation

### 2.2 Vector Embedding và Tìm kiếm ngữ nghĩa
- Dense Embedding: biểu diễn văn bản thành vector số thực (ví dụ: `text-embedding-3-small`, 1536 chiều)
- Sparse Embedding (BM25): tìm kiếm từ khóa chính xác
- Cosine Similarity: đo độ tương đồng giữa 2 vector

### 2.3 Hybrid Search
- Kết hợp Dense + Sparse để vừa hiểu ngữ nghĩa vừa khớp từ khóa chuyên ngành (DTI, FICO, CIC)
- Reciprocal Rank Fusion (RRF)

### 2.4 Cross-Encoder Reranking
- Bi-Encoder (retrieval) vs Cross-Encoder (reranking)
- Cross-Encoder chính xác hơn nhưng chậm hơn → dùng ở bước thứ 2 (sau khi lọc top-K)

### 2.5 Chunking Strategies
- Fixed-size chunking vs Semantic chunking vs Recursive Text Splitting
- Parent-Child chunking: tìm kiếm ở mức chi tiết (child), trả kết quả ở mức ngữ cảnh rộng (parent)
- So sánh lý do chọn Parent-Child cho tài liệu Markdown có cấu trúc

---

## 3. Kiến trúc tổng quan

### 3.1 Sơ đồ kiến trúc hệ thống
> **Gợi ý:** Vẽ sơ đồ flowchart (Mermaid hoặc draw.io) thể hiện luồng từ User → Rate Limit → Input Guardrail → Intent Router → Hybrid Search → Reranker → Parent Expansion → Personalizer → LLM → Output Guardrail → Response

### 3.2 Các thành phần chính

| Thành phần | File | Vai trò |
|-----------|------|---------|
| Orchestrator | `chain.py` | Điều phối pipeline 6 bước |
| Ingest | `ingest.py` | Nạp tài liệu vào Qdrant |
| Chunking | `chunking.py` | Phân đoạn Parent-Child |
| Retriever | `retriever.py` | Hybrid Search + Reranking |
| Reranker | `reranker.py` | Cross-Encoder scoring |
| Router | `router.py` | Phân loại ý định (6 loại) |
| Query Rewriter | `query_rewriter.py` | Viết lại câu hỏi ngữ cảnh |
| Guardrails | `guardrails.py` | An toàn đầu vào/đầu ra |
| Personalizer | `personalizer.py` | Cá nhân hóa giọng điệu |
| Memory | `memory.py` | Sliding window + summarization |
| Context Builder | `context_builder.py` | 4-block user context |
| Prompts | `prompts.py` | System prompt template |
| Config | `config.py` | Tập trung cấu hình (model, Qdrant, reranker) |
| Exceptions | `exceptions.py` | Phân cấp lỗi (RAGError, RetrievalError, LLMError) |
| Eval Runner | `eval_runner.py` | Chạy bộ đánh giá offline |
| Eval Metrics | `eval_metrics.py` | Tính Faithfulness, Context Precision, regression detection |
| Eval Dataset | `eval_dataset.py` | Validate + load dataset JSON cho eval |

### 3.3 Module ngoài `rag/` nhưng liên quan trực tiếp

| File | Vị trí | Vai trò |
|------|--------|---------|
| `chat_service.py` | `services/` | Điều phối toàn bộ: rate limit, atomic save, memory, loan adjustment, gọi RAG |
| `loan_adjustment_tool.py` | `services/` | Tool calling: tìm phương án vay thay thế bằng ML real-time |

### 3.4 Công nghệ sử dụng

| Công nghệ | Vai trò | Chi tiết |
|-----------|---------|----------|
| Qdrant | Vector Database | Lưu trữ & tìm kiếm vector, hỗ trợ Hybrid mode |
| LangChain | Framework | LCEL pipeline: `prompt \| llm \| StrOutputParser` |
| OpenRouter | API Gateway | Truy cập Gemini 2.5 Flash + OpenAI Embedding |
| FastEmbed | Local inference | BM25 sparse embedding + Cross-Encoder reranker |
| PostgreSQL | Relational DB | Lưu chat history, session, user context |

---

## 4. Giai đoạn Ingest — Nạp và phân mảnh tài liệu

### 4.1 Nguồn dữ liệu đầu vào
- `backend/rag/knowledge/faq.md` (303 dòng, ~19 KB) — 30 cặp Q&A, 9 chủ đề
- `backend/rag/knowledge/policy.md` (294 dòng, ~17 KB) — 12 chương chính sách
- *(Code khai báo thêm `docs/data_dictionary/` nhưng thư mục chưa tồn tại → bị skip khi chạy. Đây là dự trù mở rộng tương lai.)*

### 4.2 Thuật toán Parent-Child Chunking
> **Nội dung viết:**
> - **Bước 1 — Load:** `DirectoryLoader` đọc tất cả file `*.md` từ thư mục `backend/rag/knowledge/`
> - **Bước 2 — Enrich metadata:** Gắn `source_type` (faq/policy/knowledge_base), `document_title`
> - **Bước 3 — Parent splitting:** Chia theo heading Markdown `##` → mỗi section là 1 Parent (tối đa 3500 ký tự). Riêng file FAQ: chia theo pattern `**Q: ...**`
> - **Bước 4 — Child splitting:** Mỗi Parent chia tiếp thành Child chunks (tối đa 700 ký tự, overlap 80 ký tự) bằng thuật toán block-packing
> - **Bước 5 — Stable ID:** SHA-1 hash từ `source|section_title|index|section_part_index|content[:200]` → đảm bảo idempotent upsert (16 ký tự hex)
> - **So sánh** với Fixed-size, Recursive Text Splitting, Semantic Chunking — giải thích lý do chọn Parent-Child

### 4.3 Lưu trữ vào Qdrant + CLI Tool
- Mỗi child chunk được encode bằng 2 loại embedding:
  - **Dense:** `OpenAIEmbeddings` (text-embedding-3-small, 1536 chiều) — qua API
  - **Sparse:** `FastEmbedSparse` (Qdrant/bm25) — chạy local, miễn phí
- Metadata gắn kèm: `parent_id`, `parent_content`, `section_title`, `source`, `source_type`, `document_title`, `retrieval_unit`, `chunk_index`, `parent_index`
- **3 chế độ CLI:** `--dry-run` (không ghi), mặc định (incremental), `--recreate` (xóa tạo lại)

### 4.4 Sơ đồ minh họa
```
Tài liệu gốc (policy.md)
    │
    ├── Parent Section 1: "Giới Thiệu" (≤ 3500 chars)
    │   ├── Child Chunk 1.1 (≤ 700 chars) → [Dense Vector + Sparse Vector] → Qdrant
    │   ├── Child Chunk 1.2 (≤ 700 chars, overlap 80) → Qdrant
    │   └── Child Chunk 1.3 → Qdrant
    │
    ├── Parent Section 2: "Tiêu Chí Phân Loại Rủi Ro"
    │   ├── Child Chunk 2.1 → Qdrant
    │   └── Child Chunk 2.2 → Qdrant
    └── ...
```

---

## 5. Giai đoạn Runtime — Pipeline xử lý câu hỏi

### 5.0 Tiền xử lý tại `chat_service.py`
> **Viết ngắn gọn:**
> - Rate Limit: 20 msg/phút/user (query PostgreSQL)
> - Atomic Save: lưu tin nhắn user vào DB **trước khi** gọi RAG (đảm bảo không mất tin nhắn khi crash)
> - Load memory (sliding window + lazy summary)
> - Loan Adjustment State Machine (kiểm tra pending_action, keyword matching)
> - Build user context (4-block từ PostgreSQL)

### 5.1 Bước 1 — Input Guardrail (`guardrails.py`)

| Kiểm tra | Chi tiết | Hành động |
|----------|---------|-----------|
| Độ dài | Tối đa 2000 ký tự | Từ chối với thông báo |
| Prompt Injection | 19 pattern Regex (EN + VI) | Trả lời an toàn, không xử lý tiếp |
| PII Probing | 11 pattern Regex | Từ chối truy cập thông tin người khác |

> **Giải thích thêm:**
> - Tại sao dùng Regex thay vì LLM classifier: tốc độ (microseconds), deterministic, miễn phí
> - Thiết kế phản hồi từ chối không tiết lộ lý do (security through opacity)
> - Cơ chế dừng sớm (early exit): `passed=False` → dừng pipeline ngay, tiết kiệm API

### 5.2 Bước 2 — Intent Classification (`router.py`)
> **Viết:**
> - **Fast-path (Regex):** 4 nhóm pattern cho greeting (9), risk (5), policy (10), off_topic (6) → xử lý nhanh, không tốn API call
> - **LLM-path (Fallback):** Gọi Gemini 2.5 Flash (temperature=0, max_tokens=60) → trả JSON `{"intent": "...", "confidence": 0.95}`
> - **6 loại intent:** loan_inquiry, risk_explanation, policy_question, personal_advice, greeting, off_topic
> - **Quyết định retrieval:** Chỉ 4 intent đầu cần truy xuất tài liệu; greeting và off_topic bỏ qua
> - **So sánh:** Tại sao 2 tầng thay vì chỉ LLM — tiết kiệm ~40% chi phí router

### 5.3 Bước 3 — Retrieval (`retriever.py`)

#### 5.3.1 Query Rewriting (`query_rewriter.py`)
- Viết lại câu hỏi ngữ cảnh (ví dụ: "Của tôi thì sao?" → "Xác suất vỡ nợ và mức rủi ro của đơn vay khách hàng hiện tại")
- Kết hợp `conversation_summary` để giữ ngữ cảnh hội thoại
- Chỉ kích hoạt khi có ngữ cảnh (không rewrite câu hỏi đầu tiên)
- Hàm `_clean_rewrite()` lọc output kém chất lượng, fallback về câu hỏi gốc

#### 5.3.2 Hybrid Search (Qdrant)
- **Dense Search:** Cosine similarity trên vector 1536 chiều → hiểu ngữ nghĩa
- **Sparse Search:** BM25 → khớp từ khóa chính xác (DTI, FICO, CIC)
- **RRF Fusion:** Kết hợp ranking từ cả hai
- **Kết quả:** Top-20 child chunks (`RERANKER_CANDIDATE_K = 20`)
- **So sánh:** Tại sao lấy 20 (over-fetch) thay vì ít hơn

#### 5.3.3 Cross-Encoder Reranking
- **Model:** `jinaai/jina-reranker-v2-base-multilingual` (local, ~1.1 GB)
- **Cấu hình:** `RERANKER_ENABLED` cho phép bật/tắt qua biến môi trường
- Chấm điểm 20 cặp `(query, chunk)` → sắp xếp giảm dần → giữ top-12 (`RERANKER_TOP_K = 12`)
- **Fallback:** Nếu reranker lỗi → trả về top-12 raw candidates (không crash)
- **Observability:** `get_rerank_stats()` trả về `rerank_calls`, `rerank_fallbacks`, `fallback_rate`
- **So sánh:** Bi-Encoder vs Cross-Encoder (bảng), local vs API (bảo mật, chi phí, latency)

#### 5.3.4 Parent Document Expansion
- Map child chunks → parent sections qua `parent_id` trong metadata
- De-duplicate → giữ tối đa 4 parent sections (`TOP_K = 4`)
- **Ý nghĩa:** Tìm ở mức chi tiết (child), trả về ở mức trọn vẹn (parent)

#### 5.3.5 Sơ đồ 4 giai đoạn
```
Query Rewriting → câu hỏi độc lập
      ↓
Hybrid Search → top-20 child chunks
      ↓
Cross-Encoder Rerank → top-12 child chunks
      ↓
Parent Expansion + de-dup → top-4 parent sections → LLM
```

### 5.4 Bước 4 — Personalization (`personalizer.py`)
> **Viết:**
> - Ánh xạ 7 trạng thái đơn vay → tông giọng LLM

| Trạng thái | Tông giọng |
|-----------|-----------|
| `auto_rejected` | Đồng cảm, khích lệ, không đổ lỗi |
| `admin_rejected` | Đồng cảm, chuyên nghiệp |
| `pending_review` | Khích lệ, thông tin |
| `approved` | Chúc mừng, hướng dẫn |
| `awaiting_info` | Hướng dẫn cụ thể |
| `info_submitted` | Yên tâm, chuyên nghiệp |
| `None` (chưa có đơn) | Thân thiện, chào đón |

> - Intent Instructions: hướng dẫn riêng cho 6 loại intent
> - **Tổ hợp:** 7 trạng thái × 6 intent = 42 tổ hợp cá nhân hóa
> - **Giải thích:** Tại sao cá nhân hóa giọng điệu (tâm lý khách hàng khác nhau theo trạng thái)

### 5.5 Bước 5 — LLM Generation (`chain.py` + `prompts.py`)
> **Viết:**
> - **Model:** Gemini 2.5 Flash (qua OpenRouter), temperature=0.3
> - **Framework:** LangChain LCEL: `ChatPromptTemplate | ChatOpenAI | StrOutputParser`
> - **Cấu trúc prompt 3 phần:**

```
[SYSTEM] 9 quy tắc cốt lõi
    + Thông tin cá nhân (tên, giọng điệu)
    + Hướng dẫn theo ý định
    + Thông tin hồ sơ khách hàng (4-block context)
    + Tóm tắt hội thoại trước đó
    + Tài liệu liên quan (top-4 parent sections)
[CHAT_HISTORY] Recent messages (HumanMessage / AIMessage)
[HUMAN] Câu hỏi hiện tại (câu hỏi gốc, KHÔNG phải rewrite)
```

> - **So sánh temperature:** 0.0 (router) vs 0.3 (generation) vs 0.7+ (creative)

### 5.6 Bước 6 — Output Guardrail (`guardrails.py`)

| Kiểm tra | Hành động |
|----------|-----------|
| Rò rỉ nội bộ (tên bảng DB, API key, SQL) — 13 pattern | **Chặn cứng** → trả thông báo lỗi an toàn |
| Cam kết phê duyệt tuyệt đối — 6 pattern | **Soft fix** → đính kèm disclaimer |
| Độ dài > 3000 ký tự | Cắt tại câu hoàn chỉnh cuối cùng (tìm dấu chấm sau 60% text) |

> - **Giải thích:** Tại sao "soft fix" thay vì chặn cứng cho cam kết (giữ UX, chỉ thêm disclaimer)
> - **Defense in depth:** Output Guardrail là safety net phòng khi LLM "lỡ miệng" dù system prompt đã cấm

---

## 6. Nguồn tri thức

### 6.1 Knowledge Base tĩnh (Qdrant)

| File | Kích thước | Nội dung | Cấu trúc |
|------|-----------|----------|----------|
| `faq.md` | ~19 KB | 30 cặp Q&A, 9 chủ đề (A–I) | FAQ nghiệp vụ CreditIntel |
| `policy.md` | ~17 KB | 12 chương chính sách | Quy trình, tiêu chí, quy tắc |

> *Lưu ý:* Code khai báo thêm nguồn `docs/data_dictionary/` nhưng thư mục chưa được tạo — là dự trù mở rộng.

### 6.2 Dữ liệu cá nhân hóa real-time (PostgreSQL → Context Builder)

| Block | Dữ liệu | Nguồn |
|-------|---------|-------|
| Form Context | Số tiền, kỳ hạn, DTI, credit score, việc làm, CIC | Bảng `loan_applications` |
| ML Context | Xác suất vỡ nợ, risk level, hạn mức đề xuất | Kết quả ML prediction |
| Advisory Context | So sánh vay vs đề xuất, yếu tố rủi ro/tích cực, khuyến nghị | Tính toán từ Form + ML |
| Data Quality | Danh sách feature bị impute, mức tin cậy | Metadata của ML pipeline |

> - **Giải thích:** Tại sao query live từ PostgreSQL thay vì embed vào Qdrant (luôn cập nhật, ngăn rò rỉ cross-user)

### 6.3 Lịch sử hội thoại (PostgreSQL → Memory)
- Sliding window: 2000 tokens budget
- Lazy summarization: khi > 6 tin nhắn ngoài window
- Lưu trong `chat_sessions.summary`

---

## 7. Các kỹ thuật nâng cao

### 7.1 Conversation Memory — Sliding Window + Lazy Summarization
> **Viết:**
> - Token estimation: `len(content) // 4` (rough, không cần tokenizer)
> - Window: duyệt từ mới → cũ, giữ trong budget 2000 tokens
> - Summarization trigger: ≥ 6 tin nhắn ngoài window + chưa được tóm tắt
> - LLM summarizer: Gemini 2.5 Flash, temperature=0.2, max_tokens=500
> - Lưu summary + `summary_covers_until_id` vào PostgreSQL
> - Rollback nếu DB commit lỗi

### 7.2 Loan Adjustment State Machine (`services/loan_adjustment_tool.py`)
> **Viết:**
> - **Vị trí:** Module nằm trong `services/`, KHÔNG phải trong `rag/` — tích hợp qua `chat_service.py`
> - Kích hoạt: User bị AUTO_REJECTED + gửi tin nhắn chứa tổ hợp keyword
> - Thuật toán: Thử từng `(loan_amount, term)` → ML real-time → P(default) ≤ 0.4
> - Pending action: TTL 30 phút, xác nhận/hủy bằng keyword
> - Hạn chế: Regex keyword matching, không phải LLM function calling
> - **So sánh:** Regex keyword vs LLM function calling — đơn giản/nhanh vs linh hoạt/tốn API

### 7.3 Singleton Pattern và Thread Safety
> **Viết:**
> - Tất cả thành phần nặng (LLM, Retriever, Reranker) dùng Singleton + `threading.Lock`
> - Pre-warm reranker khi server startup (`@app.on_event("startup")`)
> - Mục đích: tránh tải model 1.1 GB lúc request đầu tiên
> - `RERANKER_ENABLED` flag cho phép tắt reranker hoàn toàn qua biến môi trường

### 7.4 Hệ thống xử lý lỗi phân cấp (`exceptions.py`)
> **Viết:**
> - Phân cấp: `RAGError` → `RetrievalError`, `LLMError`, `RAGTimeoutError`
> - `chat_service.py`: bắt `RAGError` → trả HTTP 503 kèm thông báo lỗi user-friendly
> - Atomic persistence: tin nhắn user luôn được lưu kể cả khi RAG crash
> - Graceful degradation ở mọi tầng: reranker lỗi → fallback, query rewrite lỗi → dùng câu gốc, retrieval timeout → trả lời không có tài liệu

---

## 8. Đánh giá chất lượng

### 8.1 Kiến trúc Eval Framework
> **Viết:**
> - Bộ eval gồm 3 file: `eval_dataset.py` (validate dataset), `eval_metrics.py` (tính điểm), `eval_runner.py` (chạy pipeline)
> - Dataset format: JSON array, mỗi case có `id`, `group`, `question`, `ground_truth`, `expected_behavior`, `expected_sources`, `expected_context_terms`, `must_include`, `must_not_include`
> - Yêu cầu 30–50 test cases cho 1 dataset hoàn chỉnh
> - User context mặc định cho eval: hồ sơ mẫu với loan_amount=$10,000, DTI=41.5%, credit_score=620, risk=Medium

### 8.2 Các chỉ số đo lường

| Chỉ số | Công thức | Ý nghĩa |
|--------|----------|---------|
| **Faithfulness** | `0.7 × coverage + 0.3 × grounded_ratio − 0.25 × forbidden_count` | Câu trả lời có bao phủ đủ thông tin cần thiết (`must_include`) và dựa trên tài liệu truy xuất không? Có chứa thông tin cấm (`must_not_include`) không? |
| **Context Precision** | `relevant_context_count / returned_context_count` | Bao nhiêu % tài liệu truy xuất thực sự liên quan (khớp `expected_sources` hoặc `expected_context_terms`)? |
| **Overall** | `0.6 × Faithfulness + 0.4 × Context Precision` | Điểm tổng hợp, ngưỡng đạt (`PASS_THRESHOLD`) = 0.75 |

### 8.3 Regression Detection
> **Viết:**
> - So sánh kết quả hiện tại vs baseline bằng `diff_results()`
> - **Case-level regression:** `overall_delta ≤ -0.15` HOẶC case đang pass → fail
> - **Run-level regression:** `avg_overall_delta ≤ -0.05`
> - Output: danh sách `regressed_case_ids`, `improved_case_ids`, flag `has_regression`
> - Mục đích: phát hiện regression khi thay đổi prompt, nâng cấp LLM, hoặc sửa knowledge base

### 8.4 Kết quả (nếu có)
> **Gợi ý:** Chạy `eval_runner.py` và ghi lại kết quả benchmark vào đây
> ```bash
> cd backend
> PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner
> ```

---

## 9. Điểm mạnh, hạn chế và hướng phát triển

### 9.1 Điểm mạnh
1. **Bảo mật đa lớp:** Input guardrail (19 injection + 11 PII patterns) + Output guardrail (13 leak + 6 promise patterns) — defense in depth
2. **Tìm kiếm chính xác:** Hybrid Search (Dense + BM25) + Cross-Encoder Reranking → chính xác hơn chỉ dùng vector search
3. **Parent-Child Chunking:** Tìm chi tiết ở mức child nhưng LLM nhận ngữ cảnh rộng ở mức parent — so sánh lợi thế với fixed-size
4. **Cá nhân hóa sâu:** 7 trạng thái × 6 intent = 42 tổ hợp giọng điệu khác nhau
5. **Graceful degradation:** Reranker lỗi → fallback về raw candidates; Query rewrite lỗi → dùng câu gốc; Retrieval timeout → trả lời không có tài liệu
6. **Eval framework tự xây:** Phát hiện regression tự động khi thay đổi prompt/LLM, không cần evaluation framework bên ngoài

### 9.2 Hạn chế
1. **Knowledge Base còn nhỏ:** Chỉ 2 file (~36 KB), thư mục `data_dictionary` khai báo trong code nhưng chưa được tạo — chưa có hướng dẫn sử dụng, case study
2. **Reranker chạy CPU:** Latency 1–10 giây tùy cache → ảnh hưởng UX
3. **Tool calling bằng Regex:** Không phải LLM function calling → phải thêm keyword thủ công, không linh hoạt
4. **Token estimation thô:** `len // 4` không chính xác với tiếng Việt (tiếng Việt tokenize khác tiếng Anh)
5. **Eval chưa có dataset chuẩn:** Cần xây dựng bộ 30–50 test cases để chạy eval thực tế

### 9.3 Hướng phát triển
1. Bổ sung knowledge base: thêm hướng dẫn sử dụng, case study thực tế
2. Chuyển sang LLM function calling (bỏ regex keyword matching cho loan adjustment)
3. Dùng GPU hoặc Rerank API bên ngoài cho reranker (giảm latency)
4. Kết nối ETL pipeline để auto-update Qdrant khi Admin sửa chính sách
5. Dùng tiktoken hoặc tokenizer thực tế cho memory management
6. Xây dựng bộ eval dataset 30–50 cases và chạy benchmark baseline

---

## 10. Kết luận

> **Gợi ý viết:**
> - Tóm tắt: Hệ thống RAG 6 bước đã giải quyết vấn đề hallucination và cá nhân hóa trong chatbot tín dụng
> - Đóng góp kỹ thuật: Hybrid Search + Reranking + Parent-Child Chunking + Multi-layer Guardrails + Eval Framework
> - Tích hợp: RAG không đứng riêng lẻ mà kết hợp chặt với dữ liệu PostgreSQL (user context, ML results, chat memory) và services (loan adjustment tool)
> - Bài học: Thiết kế RAG cần cân bằng giữa độ chính xác (reranking) và tốc độ (latency), giữa an toàn (guardrails) và trải nghiệm (personalization)

---

## Phụ lục

### A. Cấu trúc thư mục `backend/rag/`
```
backend/rag/
├── __init__.py          # Lazy exports (17 functions)
├── config.py            # Tập trung cấu hình model, Qdrant, reranker
├── chain.py             # Orchestrator — LCEL pipeline 6 bước
├── ingest.py            # CLI tool nạp tài liệu vào Qdrant
├── chunking.py          # Thuật toán Parent-Child chunking
├── context_builder.py   # Xây dựng 4-block user context từ PostgreSQL
├── router.py            # Intent classification (Regex + LLM 2 tầng)
├── query_rewriter.py    # Viết lại câu hỏi phụ thuộc ngữ cảnh
├── retriever.py         # Hybrid Search + RerankedRetriever
├── reranker.py          # Cross-Encoder wrapper (Singleton, lazy load)
├── guardrails.py        # Input + Output guardrails (Regex-based)
├── personalizer.py      # Cá nhân hóa giọng điệu (7 trạng thái × 6 intent)
├── memory.py            # Sliding window + Lazy summarization
├── prompts.py           # System prompt template (9 quy tắc)
├── exceptions.py        # Phân cấp lỗi: RAGError → RetrievalError, LLMError
├── eval_runner.py       # Chạy bộ đánh giá offline
├── eval_metrics.py      # Faithfulness, Context Precision, regression detection
├── eval_dataset.py      # Validate + load eval dataset JSON
└── knowledge/
    ├── faq.md           # 30 cặp Q&A, 9 chủ đề
    └── policy.md        # 12 chương chính sách tín dụng
```

### B. Module liên quan ngoài `rag/`
```
backend/services/
├── chat_service.py             # Điều phối: rate limit, atomic save, memory, gọi RAG
└── loan_adjustment_tool.py     # Tool calling: tìm phương án vay thay thế

backend/tests_local/
├── test_loan_adjustment_tool.py
├── test_chat_service_loan_adjustment.py
└── test_rag_auto_flows.py
```

### C. Bảng cấu hình môi trường RAG
| Biến | Giá trị mặc định | Mô tả |
|------|------------------|-------|
| `RAG_LLM_MODEL` | `google/gemini-2.5-flash` | Model LLM chính |
| `RAG_EMBEDDING_MODEL` | `openai/text-embedding-3-small` | Embedding model (1536d) |
| `RAG_BM25_MODEL` | `Qdrant/bm25` | Sparse embedding |
| `RAG_RERANKER_MODEL` | `jinaai/jina-reranker-v2-base-multilingual` | Cross-Encoder |
| `RAG_RERANKER_ENABLED` | `true` | Cho phép bật/tắt reranker |
| `RAG_RERANKER_CANDIDATE_K` | 20 | Số child chunks trước rerank |
| `RAG_RERANKER_TOP_K` | 12 | Số child chunks sau rerank |
| `RAG_TOP_K` | 4 | Số parent sections gửi LLM |
| `RAG_MEMORY_WINDOW_TOKEN_BUDGET` | 2000 | Token budget cho recent messages |
| `RAG_MEMORY_MIN_MESSAGES_TO_SUMMARIZE` | 6 | Ngưỡng trigger summarization |

### D. Tài liệu tham khảo (gợi ý)
1. Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS.
2. Gao, Y. et al. (2024). *Retrieval-Augmented Generation for Large Language Models: A Survey.* arXiv.
3. Nogueira, R. & Cho, K. (2019). *Passage Re-ranking with BERT.* arXiv:1901.04085.
4. Robertson, S. & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and Beyond.* Foundations and Trends in IR.
5. Günther, M. et al. (2024). *Jina Reranker v2: A Multilingual Multi-Task Cross-Encoder.* Jina AI Technical Report.
6. Perez, F. & Ribeiro, I. (2022). *Ignore This Title and HackAPrompt.* arXiv:2210.14644.
7. LangChain Documentation — https://python.langchain.com/
8. Qdrant Documentation — https://qdrant.tech/documentation/
9. Jina AI Reranker — https://jina.ai/reranker/
