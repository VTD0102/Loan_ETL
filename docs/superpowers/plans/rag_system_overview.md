# 🤖 Tổng Quan Hệ Thống AI RAG — CreditIntel

> **Phạm vi:** `backend/rag/` · `backend/services/chat_service.py` · `backend/api/routers/chat.py`  
> **Ngày viết:** 2026-05-14  
> **Tác giả:** Tài liệu tự động từ phân tích source code

---

## 1. Tổng Quan Kiến Trúc

Hệ thống RAG (Retrieval-Augmented Generation) của CreditIntel là trợ lý AI tư vấn tài chính cho khách hàng vay vốn. Nó kết hợp ba thành phần chính:

```
Câu hỏi người dùng
       │
       ▼
┌──────────────────┐     ┌─────────────────────────┐
│  Context Builder  │──▶ │  Retriever (Pinecone)    │
│ (DB: hồ sơ vay)  │     │  Vector Search top-K docs│
└──────────────────┘     └────────────┬────────────┘
                                      │
                          ┌───────────▼────────────┐
                          │    LLM (OpenRouter)     │
                          │  ConversationalChain    │
                          │  + Chat History         │
                          └───────────┬────────────┘
                                      │
                          ┌───────────▼────────────┐
                          │   Câu trả lời + Sources │
                          │   Lưu DB (chat_messages)│
                          └────────────────────────┘
```

**Mô hình LLM:** `google/gemini-flash-1.5` (qua OpenRouter)  
**Embedding Model:** `openai/text-embedding-3-small` (1536 chiều)  
**Vector Store:** Pinecone Serverless (AWS us-east-1)  
**Framework:** LangChain `ConversationalRetrievalChain`

---

## 2. Kiến Trúc Module Chi Tiết

```
backend/rag/
├── __init__.py          # Export công khai của package RAG
├── config.py            # Cấu hình: model, API keys, top-K
├── ingest.py            # Pipeline nạp dữ liệu → Pinecone (one-shot script)
├── retriever.py         # Kết nối Pinecone, tạo retriever top-K
├── context_builder.py   # Build context từ DB: hồ sơ vay của user
├── prompts.py           # Định nghĩa System Prompt tiếng Việt
├── chain.py             # Khởi tạo ConversationalRetrievalChain (singleton)
├── memory.py            # Đọc/ghi chat history từ PostgreSQL
└── knowledge/
    ├── faq.md           # Tài liệu FAQ: 17 câu hỏi thường gặp
    └── policy.md        # Chính sách xét duyệt cho vay CreditIntel
```

---

## 3. Giai Đoạn 1 — INGEST: Xây Dựng Knowledge Base

### 3.1 Mục đích
Đây là bước **one-shot** (chạy một lần) để đưa tài liệu kiến thức vào Pinecone. Không chạy lại mỗi khi có câu hỏi.

### 3.2 Nguồn dữ liệu đầu vào

| Thư mục | Nội dung | Định dạng |
|---|---|---|
| `backend/rag/knowledge/` | FAQ + Chính sách cho vay | `.md` |
| `docs/data_dictionary/` | Data dictionary (nếu tồn tại) | `.md` |

**Tài liệu cụ thể:**
- `faq.md` — 17 câu hỏi & trả lời về quy trình vay, DTI, credit score, trạng thái đơn
- `policy.md` — Chính sách xét duyệt: ngưỡng rủi ro, đề xuất hạn mức, quy trình AUTO_REJECTED

### 3.3 Pipeline Ingest

```
📄 File .md (faq.md, policy.md, ...)
         │
         ▼  [DirectoryLoader + TextLoader]
Load Documents (LangChain)
         │
         ▼  [RecursiveCharacterTextSplitter]
Chia nhỏ thành chunks
   chunk_size  = 800 ký tự
   chunk_overlap = 100 ký tự
         │
         ▼  [OpenAIEmbeddings via OpenRouter]
Encode → Vector 1536 chiều
   Model: openai/text-embedding-3-small
         │
         ▼  [PineconeVectorStore.from_documents()]
Upsert vào Pinecone
   Index: "creditintel-kb"
   Metric: cosine similarity
   Cloud: AWS us-east-1 (Serverless)
```

### 3.4 Chi tiết kỹ thuật Chunking

**Thuật toán:** `RecursiveCharacterTextSplitter`  
Chia văn bản theo thứ tự ưu tiên: `\n\n` → `\n` → ` ` → ký tự đơn lẻ, đảm bảo chunk không bị cắt giữa câu hoặc đoạn văn nếu có thể.

| Tham số | Giá trị | Lý do |
|---|---|---|
| `chunk_size` | 800 | Đủ ngắn để embed chính xác, đủ dài để giữ ngữ cảnh |
| `chunk_overlap` | 100 | Tránh mất thông tin tại biên chunk |

### 3.5 Chạy lại Ingest

```bash
cd backend
python -m rag.ingest
```

Output: `Ingested N chunks into Pinecone index 'creditintel-kb'`

> ⚠️ Script sẽ **xóa toàn bộ index cũ** (`delete_all=True`) trước khi nạp lại.

---

## 4. Giai Đoạn 2 — RUNTIME: Xử Lý Câu Hỏi

### 4.1 Luồng hoàn chỉnh khi user gửi tin nhắn

```
POST /api/v1/chat
 body: { "message": "...", "session_id": "uuid | null" }
         │
         ▼ [Middleware: JWT Auth — require_customer]
Xác thực token JWT → lấy email user
         │
         ▼ [chat_service.send()]
┌─────────────────────────────────────────────────────┐
│ 1. Lookup User từ PostgreSQL                         │
│ 2. Kiểm tra Rate Limit (20 msg/phút)                │
│ 3. Đảm bảo đơn vay mới nhất có ML prediction        │
│ 4. Get/Create chat session                          │
│ 5. Load chat history (10 turns gần nhất)            │
│ 6. Build user context từ DB                         │
│ 7. Gọi RAG chain                                    │
│ 8. Lưu Q&A vào chat_messages                        │
│ 9. Trả về answer + session_id + sources             │
└─────────────────────────────────────────────────────┘
```

### 4.2 Bước 3 — Đảm bảo có ML Prediction

Trước khi chat, hệ thống kiểm tra xem đơn vay mới nhất đã có `default_probability` chưa. Nếu chưa → **tự động gọi ML model** để tính toán và lưu vào DB. Điều này đảm bảo `context_builder` luôn có dữ liệu phong phú.

### 4.3 Bước 6 — Build User Context

**File:** `rag/context_builder.py`

Query đơn vay mới nhất của user từ bảng `loan_applications`, build thành chuỗi text có cấu trúc:

```
- Trạng thái đơn vay gần nhất: PENDING_REVIEW
- Số tiền xin vay: 10,000,000 VND
- Kỳ hạn: 36 tháng
- Thu nhập hàng tháng: 15,000,000 VND
- DTI (tỷ lệ nợ/thu nhập): 35.00%
- Credit score tự khai: 680
- Tình trạng sở hữu nhà: Có nhà
- Xác suất vỡ nợ (ML): 18.50%
- Mức rủi ro: LOW
- Đề xuất của hệ thống: 15,000,000 VND / 36 tháng
- Phiên bản model: v1.2
```

Context này được **inject thẳng vào System Prompt** của LLM — không qua vector search — đảm bảo AI luôn biết thông tin cá nhân của khách hàng đang hỏi.

### 4.4 Bước 7 — RAG Chain Execution

```
Input:
  question     = "Tại sao tôi bị từ chối?"
  user_context = <chuỗi từ context_builder>
  chat_history = [HumanMessage, AIMessage, ...]  ← 10 turns gần nhất

              │
              ▼ [ConversationalRetrievalChain]
┌─────────────────────────────────────────────┐
│  STEP 1: Question Rephrasing                 │
│  LLM refine câu hỏi dựa trên chat_history   │
│  → "standalone question" không phụ thuộc    │
│    vào ngữ cảnh hội thoại trước             │
└───────────────────┬─────────────────────────┘
                    │
                    ▼ [Retriever — Pinecone cosine search]
┌─────────────────────────────────────────────┐
│  STEP 2: Semantic Retrieval                  │
│  Embed câu hỏi → vector 1536 chiều          │
│  Tìm TOP_K=4 chunks gần nhất trong Pinecone │
│  Metric: cosine similarity                   │
│  Trả về: list[Document] + metadata.source   │
└───────────────────┬─────────────────────────┘
                    │
                    ▼ [ChatPromptTemplate]
┌─────────────────────────────────────────────┐
│  STEP 3: Prompt Assembly                     │
│  [System] = SYSTEM_TEMPLATE:                 │
│    - Rules (6 quy tắc hành vi AI)           │
│    - {user_context} → hồ sơ cá nhân        │
│    - {context}      → chunks từ Pinecone    │
│  [History] = MessagesPlaceholder            │
│  [Human]   = câu hỏi gốc                   │
└───────────────────┬─────────────────────────┘
                    │
                    ▼ [LLM: google/gemini-flash-1.5]
┌─────────────────────────────────────────────┐
│  STEP 4: Generation                          │
│  temperature = 0.3 (ít sáng tạo, ổn định)  │
│  API: OpenRouter → Gemini Flash 1.5         │
│  Output: answer (str) + source_documents    │
└─────────────────────────────────────────────┘
```

---

## 5. Prompt Engineering

### 5.1 System Prompt (tiếng Việt)

**File:** `rag/prompts.py`

Prompt được thiết kế với 6 ràng buộc hành vi cứng:

| # | Ràng buộc | Mục đích |
|---|---|---|
| 1 | Luôn trả lời tiếng Việt, thân thiện-chuyên nghiệp | UX nhất quán |
| 2 | Chỉ trả lời về: vay, rủi ro, chỉ số tài chính, chính sách | Tránh hallucination ngoài domain |
| 3 | KHÔNG hứa phê duyệt đơn | Quản lý kỳ vọng, tránh rủi ro pháp lý |
| 4 | KHÔNG tiết lộ thông tin khách hàng khác / cấu trúc nội bộ | Bảo mật dữ liệu |
| 5 | Trích dẫn nguồn bằng tên file khi dùng tài liệu | Minh bạch, traceability |
| 6 | Nói rõ khi không đủ thông tin | Tránh sai lệch |

### 5.2 Cấu trúc Prompt đầy đủ

```
[SYSTEM]
  ← 6 quy tắc hành vi
  ═══ THÔNG TIN HỒ SƠ KHÁCH HÀNG ═══
  {user_context}          ← inject từ DB (personal data)
  ═══ TÀI LIỆU LIÊN QUAN ═══
  {context}               ← inject từ Pinecone (retrieved docs)

[CHAT HISTORY]
  HumanMessage: ...
  AIMessage: ...
  (tối đa 10 turns)

[HUMAN]
  {question}              ← câu hỏi hiện tại
```

---

## 6. Memory & Persistence

### 6.1 Lưu trữ hội thoại

**File:** `backend/models/chat.py` → bảng PostgreSQL

```sql
chat_sessions (
    id          UUID PRIMARY KEY,
    user_id     UUID FK → users.id,
    title       VARCHAR nullable,
    created_at  TIMESTAMP,
    updated_at  TIMESTAMP
)

chat_messages (
    id          UUID PRIMARY KEY,
    session_id  UUID FK → chat_sessions.id,
    role        VARCHAR  -- 'user' | 'assistant'
    content     TEXT,
    sources     JSON nullable,  -- danh sách file nguồn
    created_at  TIMESTAMP
)
```

### 6.2 Chiến lược Memory (Window Buffer)

- Load **10 turns gần nhất** (= 20 messages: 10 user + 10 assistant) từ DB
- Convert sang LangChain objects: `HumanMessage` / `AIMessage`
- Truyền vào chain qua `MessagesPlaceholder`

> **Lý do:** Window buffer thay vì full history tránh vượt context window của LLM và giảm chi phí API.

### 6.3 Rate Limiting

```python
# 20 messages/phút/user
one_min_ago = datetime.utcnow() - timedelta(minutes=1)
query_count = count(ChatMessage WHERE role='user' AND created_at >= one_min_ago)
if query_count >= 20:
    raise HTTP 429
```

---

## 7. Retriever — Tìm kiếm Ngữ nghĩa

### 7.1 Cấu hình

**File:** `rag/retriever.py`

```python
vectorstore = PineconeVectorStore.from_existing_index(
    index_name = "creditintel-kb",
    embedding   = OpenAIEmbeddings(model="openai/text-embedding-3-small")
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
```

| Tham số | Giá trị | Giải thích |
|---|---|---|
| `k` (TOP_K) | 4 | Trả về 4 chunks liên quan nhất |
| Metric | cosine | Đo độ tương đồng hướng vector |
| Dimension | 1536 | Theo `text-embedding-3-small` |

### 7.2 Cách hoạt động cosine similarity

```
cos(θ) = (A · B) / (|A| × |B|)

A = embedding(câu hỏi user)    [1536-dim vector]
B = embedding(mỗi chunk trong Pinecone)

Score ∈ [-1, 1], càng gần 1 càng tương đồng
→ Lấy top-4 có score cao nhất
```

### 7.3 Singleton Pattern

`_retriever` và `_chain` đều dùng **singleton** (lazy init, global variable) để:
- Tránh tạo lại connection tốn kém mỗi request
- Chỉ khởi tạo lần đầu khi có request thực sự

---

## 8. Đầu Vào & Đầu Ra

### 8.1 API Endpoint

```
POST /api/v1/chat
Authorization: Bearer <JWT token>
Content-Type: application/json
```

**Request:**
```json
{
    "message": "Tại sao đơn vay của tôi bị từ chối?",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"  // optional
}
```

**Response:**
```json
{
    "response": "Dựa trên hồ sơ của bạn, đơn bị từ chối do xác suất vỡ nợ đạt 45%, vượt ngưỡng 40% của hệ thống. Yếu tố chính là DTI 50% — khá cao so với mức an toàn 35%. (nguồn: policy.md)",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "sources": [
        { "source": "policy.md", "title": "policy.md" },
        { "source": "faq.md",    "title": "faq.md" }
    ]
}
```

### 8.2 Bảng tóm tắt đầu vào/đầu ra

| Thành phần | Đầu vào | Đầu ra |
|---|---|---|
| **API** | JWT token + message + session_id | answer + session_id + sources |
| **Context Builder** | user_id → DB query | Chuỗi text hồ sơ vay |
| **Retriever** | Câu hỏi (string) | List 4 Document chunks |
| **LLM Chain** | question + user_context + chunks + history | Answer string |
| **Ingest** | File .md | Pinecone index đã lưu vectors |

---

## 9. Phụ Thuộc Công Nghệ

| Thư viện | Phiên bản | Vai trò |
|---|---|---|
| `langchain` | ≥0.2 | ConversationalRetrievalChain, TextSplitter, Prompts |
| `langchain-openai` | ≥0.1 | ChatOpenAI, OpenAIEmbeddings |
| `langchain-pinecone` | ≥0.1 | PineconeVectorStore |
| `langchain-community` | ≥0.2 | DirectoryLoader, TextLoader |
| `pinecone` | ≥3.0 | Pinecone client SDK |
| `openrouter` | — | Proxy API cho LLM + Embeddings |
| `sqlalchemy` | ≥2.0 | ORM — lưu chat history vào PostgreSQL |
| `fastapi` | ≥0.100 | REST API endpoint |
| `pydantic` | ≥2.0 | Schema validation (ChatRequest/ChatResponse) |

---

## 10. Cấu Hình Môi Trường

**File:** `backend/.env`

```env
# OpenRouter (LLM + Embeddings)
OPENROUTER_API_KEY=sk-or-...
RAG_LLM_MODEL=google/gemini-flash-1.5
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
RAG_TOP_K=4

# Pinecone
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=creditintel-kb
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
```

---

## 11. Sơ Đồ Luồng Đầy Đủ (End-to-End)

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGEST PHASE (one-shot)                  │
│                                                                  │
│  faq.md ─┐                                                      │
│           ├─▶ DirectoryLoader ─▶ Chunker ─▶ Embeddings ─▶ Pinecone │
│  policy.md┘  (TextLoader)       800/100     text-embed-3-small  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       RUNTIME PHASE (per request)               │
│                                                                  │
│  User ──POST /api/v1/chat──▶ [JWT Auth]                         │
│                                    │                            │
│                    ┌───────────────▼──────────────────┐         │
│                    │        chat_service.send()        │         │
│                    │                                  │         │
│                    │  1. Rate limit check (20/min)    │         │
│                    │  2. ML predict (nếu chưa có)     │         │
│                    │  3. Get/Create ChatSession        │         │
│                    │  4. Load history (10 turns)       │         │
│                    │  5. build_user_context() ← DB    │         │
│                    │  6. rag.invoke()                  │         │
│                    │     ├─ Rephrase question          │         │
│                    │     ├─ Retriever → Pinecone       │         │
│                    │     │   cosine top-K=4 chunks     │         │
│                    │     ├─ Assemble Prompt            │         │
│                    │     │   [system + context +       │         │
│                    │     │    user_context + history]  │         │
│                    │     └─ LLM → answer               │         │
│                    │  7. Save Q&A + sources → DB       │         │
│                    └───────────────┬──────────────────┘         │
│                                    │                            │
│  User ◀── { response, session_id, sources } ───────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Điểm Mạnh & Hạn Chế

### ✅ Điểm mạnh
- **Context-aware**: Inject thực tế hồ sơ vay của user vào prompt → AI trả lời cá nhân hóa
- **Source transparency**: Trả về tên file nguồn cùng câu trả lời
- **Memory window**: Duy trì ngữ cảnh 10 turns không tốn token quá nhiều
- **Rate limiting**: Bảo vệ khỏi lạm dụng API
- **Singleton pattern**: Tránh khởi tạo lại connection mỗi request
- **Graceful fallback**: Nếu RAG/LLM lỗi → trả về thông báo lỗi thân thiện, không crash

### ⚠️ Hạn chế
- Chỉ tìm kiếm trên 2 file (faq.md + policy.md) — knowledge base còn nhỏ
- Embedding model qua OpenRouter (proxy) có thể chậm hơn gọi trực tiếp
- Memory không persistent qua restart (dữ liệu trong DB nhưng singleton bị reset)
- `delete_all=True` trong ingest xóa toàn bộ → cần rebuild nếu thêm tài liệu mới

---

*Tài liệu này phản ánh trạng thái source code tại thời điểm 2026-05-14.*
