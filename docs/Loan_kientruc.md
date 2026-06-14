# V. RAG VÀ TRỢ LÝ AI TÍN DỤNG — KIẾN TRÚC DỮ LIỆU

> Chương này phân tích trợ lý hội thoại RAG của CreditIntel dưới góc nhìn **hệ quản trị cơ sở dữ liệu**: cách hệ thống tổ chức dữ liệu trên hai kho lưu trữ (quan hệ và vector), cách một quy trình ETL nạp tri thức vào kho vector, và — quan trọng nhất — cách một **tầng chuyển hóa dữ liệu (Context Builder)** dựng ngữ cảnh trả lời trực tiếp từ hồ sơ người dùng và kết quả mô hình học máy. Phần thiết kế lược đồ quan hệ tổng thể (ERD đầy đủ) đã được trình bày ở chương thiết kế cơ sở dữ liệu; ở đây chỉ nhắc lại những bảng và trường có vai trò trực tiếp trong luồng RAG.

---

## 1. Giới thiệu và kiến trúc lưu trữ kép

### 1.1. Bối cảnh: vì sao một chatbot tín dụng cần "neo" vào dữ liệu

Các mô hình ngôn ngữ lớn (LLM) như Gemini hay GPT có khả năng sinh văn bản trôi chảy, nhưng mang một hạn chế cố hữu: toàn bộ "kiến thức" của chúng được mã hóa trong trọng số tại thời điểm huấn luyện, không có cơ chế tra cứu dữ liệu thật trong thời gian thực. Hệ quả là hiện tượng **ảo giác (hallucination)** — mô hình tự bịa ra thông tin nghe hợp lý nhưng sai. Trong một sản phẩm tài chính, ảo giác không chỉ gây khó chịu mà còn dẫn tới hậu quả pháp lý: nói sai chính sách phê duyệt, báo sai chỉ số DTI hay xác suất vỡ nợ so với kết quả thật của mô hình, hoặc tệ hơn là làm lộ dữ liệu cá nhân của khách hàng khác.

Kiến trúc **RAG (Retrieval-Augmented Generation)** giải quyết vấn đề này bằng cách tách tri thức ra khỏi trọng số mô hình và đặt nó vào **kho dữ liệu bên ngoài có thể truy vấn**. Mỗi khi khách hàng đặt câu hỏi, hệ thống truy xuất đúng những mẩu dữ liệu liên quan rồi nạp vào prompt làm bằng chứng để LLM căn cứ mà trả lời. Nói cách khác, chất lượng câu trả lời không còn phụ thuộc vào "trí nhớ" của mô hình, mà phụ thuộc vào **chất lượng tổ chức và truy vấn dữ liệu** — đây chính là nơi bài toán trở thành một bài toán cơ sở dữ liệu.

Trợ lý CreditIntel được thiết kế theo nguyên tắc **"có trích dẫn nguồn, không bịa thông tin"**: mọi phát ngôn đều phải bắt nguồn từ một trong ba nguồn dữ liệu có kiểm soát — tài liệu chính sách tĩnh, hồ sơ vay thật của khách hàng, hoặc kết quả học máy đã được tính toán và lưu trữ sẵn. Toàn bộ mã nguồn nằm trong gói `backend/rag/` (pipeline suy luận) và `backend/services/chat_service.py` (điều phối).

### 1.2. Kiến trúc lưu trữ kép (polyglot persistence)

Đặc trưng dữ liệu nổi bật nhất của hệ thống là việc sử dụng **đồng thời hai loại cơ sở dữ liệu**, mỗi loại tối ưu cho một dạng dữ liệu và một dạng truy vấn khác nhau. Đây là một ví dụ điển hình của mô hình **polyglot persistence** — "đa hệ lưu trữ" — trong đó ta không cố ép mọi dữ liệu vào một loại CSDL duy nhất, mà chọn đúng công cụ cho đúng việc.

| Tiêu chí | PostgreSQL (quan hệ) | Qdrant (vector) |
|---|---|---|
| Vai trò | Lưu dữ liệu giao dịch: người dùng, đơn vay, kết quả ML, lịch sử chat | Lưu tri thức chính sách đã vector hóa để tìm theo ngữ nghĩa |
| Dữ liệu | Có cấu trúc, quan hệ chặt (khóa chính/ngoại) | Vector nhiều chiều + payload (siêu dữ liệu) |
| Kiểu truy vấn | SQL: lọc, join, gom nhóm, ràng buộc toàn vẹn | Tìm k láng giềng gần nhất theo độ tương đồng vector |
| Tính nhất quán | ACID, giao dịch | Eventually-consistent, tối ưu cho tốc độ tìm kiếm |
| Triển khai | Supabase (PostgreSQL được quản lý) | Docker container cục bộ (`localhost:6333`) |

Ranh giới phân chia dữ liệu giữa hai kho không phải tùy tiện mà dựa trên một nguyên tắc nhất quán: **dữ liệu cá nhân, động, có ràng buộc toàn vẹn thì ở PostgreSQL; tri thức dùng chung, tĩnh, cần tìm theo ngữ nghĩa thì ở Qdrant.** Một hệ quả quan trọng về mặt bảo mật là **dữ liệu cá nhân của khách hàng tuyệt đối không được nhúng vào Qdrant** — nó luôn được truy vấn trực tiếp từ PostgreSQL theo `user_id` tại thời điểm xử lý từng request (xem chi tiết ở Chương 5). Nhờ vậy, ranh giới cách ly giữa các khách hàng được bảo đảm ngay ở tầng kiến trúc lưu trữ, chứ không phải chỉ ở tầng logic ứng dụng.

Bốn bảng quan hệ tham gia trực tiếp vào luồng RAG (lược đồ đầy đủ xem chương thiết kế CSDL):

| Bảng | Vai trò trong RAG |
|---|---|
| `users` | Thông tin định danh khách hàng; dùng cho bước cá nhân hóa giọng điệu |
| `loan_applications` | Đơn vay **và** kết quả học máy — đóng vai trò "hợp đồng dữ liệu" giữa pipeline ML và RAG; là nguồn của Context Builder 4 khối |
| `chat_sessions` | Siêu dữ liệu phiên chat: tiêu đề, bản tóm tắt hội thoại, con trỏ bao phủ tóm tắt, hành động đang chờ xác nhận |
| `chat_messages` | Lịch sử tin nhắn (vai trò, nội dung, nguồn trích dẫn, cờ lỗi); nguồn cho cửa sổ trượt và tóm tắt bộ nhớ |

### 1.3. Hai mặt phẳng xử lý

Về mặt mã nguồn, trợ lý được tách thành hai mặt phẳng có trách nhiệm rạch ròi, giúp lõi suy luận kiểm thử được độc lập với mọi phụ thuộc cơ sở dữ liệu:

- **Mặt phẳng điều phối** (`services/chat_service.py`): chạm tới cơ sở dữ liệu — quản lý phiên, giới hạn tốc độ, lưu transcript, tải bộ nhớ, dựng ngữ cảnh người dùng, điều phối công cụ. Đây là nơi tập trung các thao tác dữ liệu giao dịch.
- **Mặt phẳng suy luận RAG** (`rag/chain.py`): một pipeline thuần túy 6 bước **không chạm cơ sở dữ liệu giao dịch** — chỉ nhận ngữ cảnh đã dựng sẵn, truy xuất tri thức từ Qdrant, gọi LLM và hậu kiểm. Mọi dữ liệu cá nhân được tầng điều phối truy vấn rồi truyền vào dưới dạng văn bản, giữ cho lõi RAG tách bạch khỏi tầng ORM.

### 1.4. Sơ đồ luồng dữ liệu tổng thể

```
┌──────────────────────────────────────────────────────────────────────────┐
│   Frontend (React)  ──POST /chat (JWT)──►  api/routers/chat.py            │
├──────────────────────────────────────────────────────────────────────────┤
│   services/chat_service.send()   ── MẶT PHẲNG ĐIỀU PHỐI ──                │
│     1. Giới hạn tốc độ      ── SQL COUNT (cửa sổ 1 phút) ──►  PostgreSQL   │
│     2. Lưu tin user (atomic, trước khi gọi RAG)          ──►  PostgreSQL   │
│     3. Tải bộ nhớ (cửa sổ trượt + tóm tắt lười)          ◄──  PostgreSQL   │
│     4. Đảm bảo đơn mới nhất đã có dự đoán ML             ◄──► PostgreSQL   │
│     5. build_user_context()  ── 4 khối từ loan_applications ◄── PostgreSQL │
│     6. build_personalization()                                            │
│                              │ chain.invoke(question, context, history)   │
│                              ▼                                             │
│   rag/chain.py   ── MẶT PHẲNG SUY LUẬN (6 bước) ──                        │
│     ① Guardrail vào → ② Router → ③ Rewrite + Retrieve                     │
│     ④ Personalize  → ⑤ LLM    → ⑥ Guardrail ra                           │
│                  │ retrieve()                    │ LLM                     │
│                  ▼                               ▼                         │
│        Qdrant (creditintel-kb)            OpenRouter / Gemini 2.5 Flash    │
│        dense(1536) + sparse(BM25)                                          │
│                              │ answer + sources                           │
│     7. Lưu transcript (chat_messages)                    ──►  PostgreSQL   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.5. Các tham số vận hành chính

Toàn bộ hành vi pipeline được điều khiển tập trung qua `core/config.py` (nạp từ `backend/.env`), giúp điều chỉnh hệ thống mà không sửa code:

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `rag_llm_model` | `google/gemini-2.5-flash` | LLM sinh câu trả lời (và routing, rewrite, summary) |
| `rag_embedding_model` | `openai/text-embedding-3-small` | Embedding dense 1536 chiều |
| `rag_bm25_model` | `Qdrant/bm25` | Sparse embedding cho hybrid search |
| `rag_reranker_model` | `jinaai/jina-reranker-v2-base-multilingual` | Cross-encoder rerank (~1,1 GB, chạy cục bộ) |
| `rag_reranker_candidate_k` | `20` | Số child chunk kéo từ Qdrant trước rerank |
| `rag_reranker_top_k` | `12` | Số child chunk giữ lại sau rerank |
| `rag_top_k` | `4` | Số **parent** cuối cùng đưa vào LLM |
| `rag_memory_window_token_budget` | `2000` | Ngân sách token cho cửa sổ hội thoại gần đây |
| `rag_memory_summary_max_tokens` | `500` | Độ dài tối đa bản tóm tắt |
| `rag_memory_min_messages_to_summarize` | `6` | Ngưỡng kích hoạt tóm tắt |
| `qdrant_collection` | `creditintel-kb` | Tên collection Qdrant |

---

## 2. Tầng dữ liệu vector — Qdrant

### 2.1. Vì sao cần một cơ sở dữ liệu vector

Cơ sở dữ liệu quan hệ truy vấn theo **giá trị chính xác**: `WHERE status = 'AUTO_REJECTED'`. Nhưng tri thức chính sách lại cần được tìm theo **ý nghĩa**: câu hỏi "Tại sao đơn của tôi bị loại ngay?" phải tìm được đoạn nói về "tiêu chí từ chối tự động" dù hai bên không chia sẻ một từ khóa nào. SQL `LIKE` không làm được điều này.

Giải pháp là biểu diễn mỗi đoạn văn bản thành một **vector embedding** — một điểm trong không gian nhiều chiều, sao cho hai đoạn có nghĩa gần nhau thì hai vector gần nhau. Khi đó "tìm theo ngữ nghĩa" trở thành bài toán hình học quen thuộc: tìm các điểm gần nhất với điểm-câu-hỏi. Một **cơ sở dữ liệu vector** như Qdrant được thiết kế chuyên cho đúng phép toán này: lưu trữ hàng loạt vector và trả về k láng giềng gần nhất một cách hiệu quả.

### 2.2. Cấu trúc collection và mô hình "named vectors"

CreditIntel sử dụng một collection duy nhất tên `creditintel-kb`. Điểm đặc biệt về mặt mô hình dữ liệu là mỗi điểm (point) trong collection mang **hai vector có tên (named vectors)** thay vì một:

```python
client.create_collection(
    collection_name="creditintel-kb",
    vectors_config={
        "dense": models.VectorParams(size=1536, distance=models.Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams(),
    },
)
```

| Vector | Loại | Sinh bởi | Vai trò |
|---|---|---|---|
| `dense` | Dày đặc, 1536 chiều, độ đo **Cosine** | `text-embedding-3-small` (OpenAI qua OpenRouter) | Tìm theo **ngữ nghĩa** — hiểu paraphrase, đồng nghĩa |
| `sparse` | Thưa (đa số phần tử = 0) | BM25 qua FastEmbed (`Qdrant/bm25`, cục bộ) | Tìm theo **từ khóa chính xác** — bắt thuật ngữ DTI, FICO, CIC |

Ngoài hai vector, mỗi điểm còn mang một khối **payload** — siêu dữ liệu phi-vector phục vụ truy vết và tái dựng ngữ cảnh (xem mục 3.4). Đây là điểm tương đồng thú vị với mô hình quan hệ: vector đóng vai trò "chỉ mục tìm kiếm", còn payload đóng vai trò "các cột dữ liệu" đi kèm mỗi bản ghi.

### 2.3. Độ đo khoảng cách Cosine

Độ đo được chọn cho vector dense là **Cosine** — đo độ tương đồng bằng cosin của góc giữa hai vector, cho giá trị trong khoảng [−1, 1]. Ưu điểm của Cosine so với khoảng cách Euclid là **không bị ảnh hưởng bởi độ lớn vector, chỉ quan tâm tới hướng**. Điều này phù hợp với văn bản: một đoạn dài và một đoạn ngắn cùng chủ đề nên được coi là gần nhau về ngữ nghĩa, dù độ lớn vector của chúng khác nhau.

### 2.4. Hybrid search và hợp nhất kết quả bằng RRF

Vector dense giỏi nắm bắt ý nghĩa nhưng đôi khi bỏ sót từ khóa hiếm; BM25 bắt chính xác từ khóa nhưng "mù" ngữ nghĩa. **Hybrid search** tận dụng cả hai: với một câu hỏi, Qdrant chạy đồng thời hai truy vấn (dense + sparse) rồi **hợp nhất hai bảng xếp hạng**. Vì điểm số của hai phương pháp ở hai thang đo khác nhau, hệ thống không cộng điểm thô mà dùng **Reciprocal Rank Fusion (RRF)** — hợp nhất dựa trên **thứ hạng** chứ không phải điểm số, nên ổn định và không bị một thang đo lấn át. Một tài liệu xuất hiện ở vị trí cao trong **cả hai** danh sách sẽ được ưu tiên.

Về mặt cấu hình, hybrid được bật qua `RetrievalMode.HYBRID` của thư viện `langchain_qdrant`. Nếu thư viện BM25 không nạp được vì lý do nào đó, hệ thống **tự hạ cấp an toàn** về `RetrievalMode.DENSE` (chỉ tìm theo vector dense) thay vì dừng hẳn — một biểu hiện của triết lý "suy giảm duyên dáng" xuyên suốt hệ thống.

### 2.5. Ngữ nghĩa upsert và bài toán idempotency

Một khía cạnh dữ liệu cần nói thẳng là **tính idempotent của thao tác nạp**. Khi nạp các chunk, hệ thống gọi:

```python
store.add_documents(chunks)   # KHÔNG truyền point ID
```

Vì không truyền ID, thư viện để Qdrant **tự sinh UUID ngẫu nhiên** cho mỗi điểm. Hệ quả về mặt cơ sở dữ liệu: chạy lại lệnh nạp trên cùng một tập tài liệu sẽ **tạo bản sao** thay vì cập nhật tại chỗ — thao tác **chưa idempotent**.

Cần phân biệt rõ với `parent_id` (mục 3.3): đó là một mã băm SHA-1 ổn định theo nội dung, nhưng nó chỉ dùng để **gom nhóm child về parent ở runtime**, *không* được dùng làm khóa chính của điểm Qdrant. Do đó, để cập nhật tri thức an toàn sau khi sửa tài liệu, quy ước vận hành hiện tại là dùng cờ `--recreate` (xóa và dựng lại collection). Đây là một điểm còn để ngỏ: gán point ID ổn định (ví dụ băm theo nội dung child) sẽ biến thao tác nạp thành upsert idempotent thật sự — một hướng cải tiến về quản trị dữ liệu.

---

## 3. Giai đoạn Ingest — quy trình ETL nạp tri thức vào Qdrant

Giai đoạn ingest (`rag/ingest.py` + `rag/chunking.py`) biến các tệp Markdown chính sách thành các điểm dữ liệu trong Qdrant. Nhìn dưới góc độ cơ sở dữ liệu, đây là một **quy trình ETL (Extract – Transform – Load)** kinh điển, hoàn toàn **tách biệt** với luồng phục vụ câu hỏi thời gian thực: ingest chỉ chạy khi khởi tạo hệ thống hoặc khi cập nhật chính sách, không ảnh hưởng tới hiệu năng phục vụ người dùng. Toàn bộ khâu Transform là **xác định (deterministic)** — không gọi LLM, không gọi embedding khi cắt chunk — nên kết quả tái lập được và kiểm thử được.

### 3.1. Extract — nạp tài liệu nguồn

Hệ thống đọc tài liệu từ hai thư mục cố định bằng `DirectoryLoader` của LangChain, quét đệ quy theo glob `**/*.md`:

```python
KNOWLEDGE_DIRS = [
    Path(__file__).parent / "knowledge",          # policy.md, faq.md
    Path(__file__).parents[2] / "docs" / "data_dictionary",  # từ điển đặc trưng
]
```

Kho tri thức hiện gồm ba tài liệu: `policy.md` (chính sách xét duyệt: phạm vi khoản vay 500–150.000 USD, kỳ hạn 12/24/36/48/60 tháng, ba mức rủi ro, quy trình hai giai đoạn AI→Admin), `faq.md` (các cặp hỏi-đáp nhóm theo chủ đề), và từ điển đặc trưng trong `docs/data_dictionary/`. Mỗi tệp được nạp thành một đối tượng `Document` gồm nội dung và siêu dữ liệu nguồn. Trên tập hiện tại, ETL sinh ra **76 child chunk** từ 3 tài liệu.

### 3.2. Transform — Parent-Child Chunking nhận biết cấu trúc

Đây là khâu biến đổi cốt lõi, giải quyết một mâu thuẫn kinh điển của RAG: chunk **nhỏ** thì embedding đậm đặc, truy xuất chính xác, nhưng thiếu ngữ cảnh khi đưa cho LLM; chunk **lớn** thì giàu ngữ cảnh nhưng embedding bị loãng, truy xuất kém nhạy. **Parent-Child Chunking** hóa giải bằng cách tách hai chức năng: **tìm kiếm trên child nhỏ** (chính xác) nhưng **trả về parent lớn** cho LLM (đủ ngữ cảnh).

Các hằng số cắt (`chunking.py`):

```python
PARENT_MAX_CHARS   = 3500   # kích thước tối đa một parent section
CHILD_MAX_CHARS    = 700    # kích thước tối đa một child chunk
CHILD_OVERLAP_CHARS = 80    # chồng lấn giữa hai child liền kề
```

Việc cắt parent **nhận biết cấu trúc Markdown** chứ không cắt mù theo độ dài, và thay đổi theo loại tài liệu:

- **Với FAQ** (`source_type == "faq"`): mỗi cặp hỏi-đáp đánh dấu bằng `**Q: ...**` trở thành một parent riêng, vì một cặp Q&A vốn đã là một đơn vị ngữ nghĩa trọn vẹn — tránh việc gom cả nhóm câu hỏi vào một section lớn rồi làm loãng truy xuất.
- **Với chính sách / từ điển**: ưu tiên cắt theo tiêu đề cấp hai (`## H2`), giữ phần mở đầu trước H2 đầu tiên làm một parent; nếu không có H2 thì lùi về H1; nếu không có tiêu đề nào thì cả tài liệu là một parent. Parent nào vượt `PARENT_MAX_CHARS` được cắt tiếp theo lối đóng gói từng block, không chồng lấn.

Mỗi parent sau đó được cắt thành các child ≤ 700 ký tự với chồng lấn 80 ký tự, theo thuật toán **đóng gói block** (`_pack_blocks`): tách văn bản theo dòng trống thành các block, gộp các block liền nhau cho tới khi chạm trần rồi sang chunk mới, mang theo phần đuôi chồng lấn để không cắt đứt mạch ngữ nghĩa ở ranh giới.

### 3.3. Sinh mã định danh ổn định cho parent

Mỗi parent nhận một mã băm ổn định để về sau gom nhóm các child trỏ về cùng một parent:

```python
def _stable_parent_id(source, section_title, parent_index, section_part_index, parent_content):
    raw = f"{source}|{section_title}|{parent_index}|{section_part_index}|{parent_content[:200]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
```

`parent_id` là 16 ký tự đầu của SHA-1 trên tổ hợp nguồn + tiêu đề + vị trí + 200 ký tự đầu nội dung. Cùng một tài liệu đầu vào luôn sinh ra cùng `parent_id`. Như đã lưu ý ở mục 2.5, `parent_id` này phục vụ **gom nhóm khi mở rộng Parent ở runtime**, không phải khóa chính của điểm Qdrant.

### 3.4. Load — schema payload của mỗi điểm và upsert vào Qdrant

Điểm tinh tế nhất về mặt mô hình dữ liệu là **mỗi child mang theo toàn bộ nội dung parent trong payload** (`parent_content`). Nhờ vậy, ở runtime ta khôi phục được parent ngay từ payload của child mà **không cần một truy vấn ngược thứ hai** — một dạng phi chuẩn hóa (denormalization) có chủ đích, đánh đổi dung lượng lưu trữ lấy độ trễ truy vấn thấp. Schema payload đầy đủ của mỗi child:

| Trường payload | Ví dụ | Vai trò |
|---|---|---|
| `source` | `"policy.md"` | Trích dẫn nguồn cho LLM |
| `source_type` | `faq` / `policy` / `data_dictionary` | Quyết định chiến lược cắt; lọc theo loại |
| `document_title` | `"Chính Sách Xét Duyệt…"` | Tiêu đề tài liệu (trích từ H1) |
| `section_title` | `"Tiêu Chí Phân Loại Rủi Ro"` | Trích dẫn mục cụ thể |
| `parent_id` | `"a3f8b2c1e9d04567"` | Khóa gom nhóm child→parent ở runtime |
| `parent_content` | (toàn văn parent) | Trả về cho LLM thay cho child |
| `chunk_index` | `1` | Vị trí child trong parent |
| `retrieval_unit` | `"child"` | Phân biệt đơn vị child/parent |

Cuối cùng, khâu Load mã hóa nội dung mỗi child thành hai vector (dense qua OpenRouter, sparse BM25 cục bộ) rồi upsert vào collection qua `QdrantVectorStore` ở chế độ `HYBRID`. Lưu ý vận hành đã nêu: nhánh mặc định chưa idempotent — cập nhật an toàn dùng `--recreate`.

### 3.5. Công cụ CLI

`ingest.py` cung cấp ba chế độ qua dòng lệnh, cho phép kiểm soát trước khi tốn chi phí embedding:

| Chế độ | Lệnh | Hành vi |
|---|---|---|
| Dry-run | `python -m rag.ingest --dry-run` | Liệt kê tài liệu và số chunk, **không** gọi Qdrant/embedding |
| Mặc định | `python -m rag.ingest` | Thêm toàn bộ chunk vào collection (chưa idempotent) |
| Recreate | `python -m rag.ingest --recreate` | Xóa rồi dựng lại collection (phá hủy) |

---

## 4. Pipeline Runtime — xử lý một câu hỏi

Mỗi lượt chat đi qua hai tầng: **tiền xử lý dữ liệu** ở `chat_service.py` (chạm PostgreSQL) và **pipeline suy luận 6 bước** ở `chain.py`. Mục này tập trung làm rõ các thao tác cơ sở dữ liệu ở tầng tiền xử lý, rồi điểm qua sáu bước suy luận.

### 4.1. Tiền xử lý — các thao tác dữ liệu giao dịch

Trước khi gọi pipeline RAG, `chat_service.send()` thực hiện một chuỗi thao tác trên PostgreSQL mà mỗi thao tác đều minh họa một kỹ thuật cơ sở dữ liệu cụ thể.

**(a) Giới hạn tốc độ bằng truy vấn gom nhóm theo cửa sổ thời gian.** Hệ thống đếm số tin nhắn của người dùng trong một phút gần nhất; nếu ≥ 20 thì trả HTTP 429. Đây là một truy vấn `COUNT` có join và lọc theo khoảng thời gian trượt:

```python
one_min_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
query_count = (
    db.query(func.count(ChatMessage.id))
      .join(ChatSession, ChatMessage.session_id == ChatSession.id)
      .filter(ChatSession.user_id == user_id,
              ChatMessage.role == "user",
              ChatMessage.created_at >= one_min_ago)
      .scalar()
)
```

**(b) Lưu nguyên tử — "ghi trước, xử lý sau".** Tin nhắn của khách hàng được `commit` vào `chat_messages` **trước khi** gọi RAG. Đây là một quyết định về **toàn vẹn dữ liệu**: dù pipeline RAG sau đó có lỗi hoàn toàn, tin nhắn người dùng vẫn không bao giờ bị mất, và hệ thống vẫn có thể ghi lại một bản ghi trợ lý mang cờ lỗi để bảo toàn nhật ký kiểm toán đầy đủ.

**(c) Đảm bảo đơn mới nhất đã có dự đoán ML.** Trước khi dựng ngữ cảnh, hệ thống kiểm tra đơn vay mới nhất của người dùng: nếu chưa có `default_probability`/`model_version`, nó gọi `ml_service.predict` và **ghi kết quả ngược vào `loan_applications`**. Bước này đảm bảo "hợp đồng dữ liệu" ML↔RAG luôn được lấp đầy trước khi Context Builder đọc tới (chi tiết ở Chương 5).

**(d) Cách ly theo `user_id`.** Mọi truy vấn ngữ cảnh đều ràng buộc theo `user_id` lấy từ JWT của chính người hỏi. Kết hợp với nguyên tắc "không nhúng dữ liệu cá nhân vào Qdrant", điều này tạo nên một ranh giới cách ly dữ liệu chéo (cross-tenant isolation) chặt ở cấp ứng dụng.

**(e) Tải bộ nhớ và dựng ngữ cảnh.** Cuối cùng, tầng điều phối gọi `load_memory()` (Chương 5.3), `build_user_context()` (Chương 5.1–5.2) và `build_personalization()`, rồi chuyển tất cả sang `chain.invoke()`.

### 4.2. Sáu bước của pipeline suy luận

Pipeline `chain.invoke()` xử lý tuần tự sáu bước, với triết lý **suy giảm duyên dáng** cho các thành phần phụ trợ: viết lại câu hỏi, truy xuất, rerank và tóm tắt đều có cơ chế fallback để chất lượng giảm dần thay vì làm đứt cả pipeline; riêng lỗi ở **LLM chính** được coi là sự cố dịch vụ (HTTP 503).

**① Guardrail đầu vào** (`guardrails.py`). Lớp lọc thuần regex (gần như tức thời, miễn phí) chặn ba loại rủi ro trước khi tốn bất kỳ lời gọi LLM nào: vượt độ dài (`MAX_INPUT_LENGTH = 2000`); **tiêm lệnh (prompt injection)** qua 20 mẫu song ngữ Anh-Việt ("ignore previous instructions", "bỏ qua các hướng dẫn ở trên"…); và **dò rỉ dữ liệu cá nhân (PII probing)** qua 11 mẫu ("thông tin của khách hàng khác", "select * from"…). Khi khớp, pipeline dừng ngay với câu từ chối lịch sự, router và LLM không được gọi.

**② Router phân loại ý định** (`router.py`). Câu hỏi được xếp vào đúng một trong sáu ý định: `loan_inquiry`, `risk_explanation`, `policy_question`, `personal_advice`, `greeting`, `off_topic`. Router chạy hai tầng: tầng một là **đường tắt regex** (greeting 9 mẫu, rủi ro cá nhân 5 mẫu, chính sách 10 mẫu, lạc đề 6 mẫu cho tin ngắn) — xác định, tức thì; chỉ khi không mẫu nào khớp mới rơi xuống tầng hai gọi `gemini-2.5-flash` ở `temperature=0`, `max_tokens=60` trả về JSON intent. Mọi bất trắc (JSON hỏng, timeout, intent lạ) quy về mặc định an toàn `loan_inquiry`. Hàm `needs_retrieval` quyết định bước kế: bốn ý định nghiệp vụ cần truy xuất, còn `greeting`/`off_topic` đi tắt để tiết kiệm độ trễ.

**③ Viết lại câu hỏi + truy xuất** — trái tim kỹ thuật. Một câu hỏi nối tiếp như "thế còn 60 tháng thì sao?" vô nghĩa nếu tách khỏi ngữ cảnh. `query_rewriter` dùng LLM (`temperature=0`) biến nó thành câu độc lập dựa trên tóm tắt + vài lượt gần nhất; chỉ viết lại khi có ngữ cảnh, phải qua bộ làm sạch (≤ 500 ký tự, một dòng), và mọi lỗi đều lặng lẽ quay về câu gốc. Quan trọng: câu viết lại **chỉ dùng để truy xuất**, còn khâu sinh câu trả lời vẫn dùng nguyên văn tin nhắn gốc.

Phần truy xuất là nơi ba kỹ thuật lồng vào nhau thành ba lớp phễu đồng tâm, thu hẹp dần tập ứng viên **20 → 12 → 4**:

```
ParentDocumentRetriever (max_parent_docs = TOP_K = 4)
   └─ RerankedRetriever (cross-encoder, top_k = 12)
        └─ base_retriever (Qdrant hybrid, k = 20)
```

- **Lớp trong — Hybrid (bi-encoder):** Qdrant kéo về 20 child ứng viên bằng cách hợp nhất dense + BM25 (RRF). Tầng này dùng **bi-encoder**: model embedding mã hóa câu hỏi và tài liệu **độc lập** rồi so vector — nhanh vì vector tài liệu đã tính sẵn khi ingest, nhưng kém chính xác vì không có tương tác trực tiếp giữa câu hỏi và tài liệu.
- **Lớp giữa — Rerank (cross-encoder):** đưa 20 ứng viên qua cross-encoder Jina, nhét **cặp (câu hỏi, tài liệu) vào cùng một lần forward** để chấm điểm liên quan chính xác hơn nhiều, giữ lại 12 child. Nếu reranker lỗi, hệ thống bắt ngoại lệ và trả về 12 ứng viên đầu của tập thô, đồng thời tăng bộ đếm `_rerank_fallback_count` để quan trắc.
- **Lớp ngoài — Mở rộng Parent:** gọi `expand_child_documents_to_parents` khử trùng theo `parent_id`, lấy `parent_content` từ payload đã nhúng sẵn, trả về tối đa 4 parent. Đây là hiện thực hóa nguyên tắc "tìm trên child, trả về parent".

Hệ thống còn có một lớp **tự chữa lành**: `SelfHealingHybridRetriever` đóng vai placeholder khi Qdrant offline và định kỳ thử kết nối lại (cooldown 60 giây), giúp pipeline tự hồi phục khi Qdrant được khởi động trở lại mà không cần restart server.

**④ Cá nhân hóa** (`personalizer.py`). Tầng điều phối dựng sẵn ngữ cảnh cá nhân hóa rồi truyền vào: tên hiển thị khách hàng + bộ hướng dẫn giọng điệu theo **trạng thái đơn vay** (7 trạng thái), cộng hướng dẫn theo **ý định** đã phân loại (6 intent) — tạo 7×6 tổ hợp phản hồi. Ví dụ với ý định giải thích rủi ro, hướng dẫn yêu cầu LLM diễn đạt "xác suất vỡ nợ ước tính khoảng 35%" thay vì phơi con số kỹ thuật "P(default)=0.35".

**⑤ Gọi LLM sinh câu trả lời** (`chain.py` + `prompts.py`). Toàn bộ ngữ cảnh được nạp vào chuỗi LCEL `chat_prompt | llm | StrOutputParser()`. Tài liệu được `_format_documents` gắn tiêu đề trích nguồn dạng `[i] nguồn :: tên tài liệu → mục` để LLM trích dẫn đúng xuất xứ. LLM chạy ở `temperature=0.3` (cân bằng nhất quán và tự nhiên), kèm `timeout` và `max_retries` từ config; lỗi quá hạn/mất kết nối được gói thành `RAGTimeoutError`/`LLMError`. System prompt nêu **9 quy tắc** (luôn tiếng Việt; chỉ phạm vi tín dụng; không hứa duyệt; không lộ dữ liệu khách khác/cấu trúc model; trích nguồn theo tên file; nói rõ khi không đủ thông tin; **ưu tiên hồ sơ khách hàng hơn tài liệu**; định dạng Markdown; không giả vờ chạy tính toán nền).

**⑥ Guardrail đầu ra** (`guardrails.py`). Câu trả lời bị hậu kiểm theo ba mức: **chặn cứng** nếu lỡ chứa tên bảng (`loan_applications`, `chat_messages`), câu SQL, khóa API (`sk-…`) hay metadata model — 14 mẫu, thay toàn bộ bằng thông báo an toàn; **đính kèm disclaimer** nếu lỡ hứa duyệt vay — 6 mẫu; và **cắt thông minh** tại ranh giới câu hoàn chỉnh nếu vượt `MAX_OUTPUT_LENGTH = 3000`.

Về xử lý ngoại lệ, hệ thống phản ánh đúng mức quan trọng của từng thành phần: `RetrievalError`/`RAGTimeoutError` ở khâu **truy xuất** chỉ ghi log và tiếp tục với `documents = []` (LLM vẫn trả lời được từ ngữ cảnh hồ sơ — truy xuất là tùy chọn); còn `LLMError`/`RAGTimeoutError` ở khâu **sinh văn bản** được đẩy lên `chat_service` trả HTTP 503 (không có LLM thì không thể trả lời).

---

## 5. Context Builder và các kỹ thuật nâng cao

Đây là chương trọng tâm của báo cáo. Nếu Chương 2–4 mô tả "ống dẫn" thì chương này mô tả **thứ chảy trong ống và làm nên giá trị thật sự** của hệ thống: cách một tầng phần mềm dựng ngữ cảnh trả lời **trực tiếp từ dữ liệu người dùng và kết quả học máy**, và các kỹ thuật quản lý dữ liệu hội thoại đi kèm.

### 5.1. Context Builder — tầng chuyển hóa dữ liệu thành ngữ cảnh

#### 5.1.1. Bản chất: một "khung nhìn tính toán" trên lược đồ quan hệ

Module `context_builder.py` lấy đơn vay **mới nhất** của người dùng và biến nó thành một khối văn bản có cấu trúc để nạp vào prompt. Nhìn dưới góc độ cơ sở dữ liệu, có thể coi Context Builder như một **khung nhìn tính toán (computed view)** đặt trên bảng `loan_applications`: nó không chỉ chiếu (project) các cột thô, mà còn **dẫn xuất** các đặc trưng mới bằng một bộ luật xác định, rồi tổng hợp tất cả thành **bốn khối ngữ cảnh**. Hàm `build_context_json()` truy vấn đơn mới nhất rồi gọi bốn hàm dựng khối:

```python
app = (db.query(LoanApplication)
         .filter(LoanApplication.user_id == user_id)
         .order_by(LoanApplication.submitted_at.desc())
         .first())
return {
    "form_context":     _build_form_context(app),     # Block 1 — chiếu cột thô
    "ml_context":       _build_ml_context(app),        # Block 2 — kết quả ML
    "advisory_context": _build_advisory_context(app, ml),  # Block 3 — dẫn xuất
    "data_quality":     _build_quality_context(app),   # Block 4 — metadata chất lượng
}
```

| Khối | Nội dung | Tương tự CSDL |
|---|---|---|
| Form Context | Trạng thái đơn, số tiền, kỳ hạn, thu nhập, DTI, điểm tín dụng, việc làm, CIC, nhân khẩu học | Phép **chiếu** cột trực tiếp |
| ML Context | Xác suất vỡ nợ, mức rủi ro, risk score, hạn mức/kỳ hạn đề xuất, phiên bản model | Đọc các cột **kết quả ML** |
| Advisory Context | So sánh vay/đề xuất, dải DTI & điểm tín dụng, yếu tố rủi ro, điểm tích cực, khuyến nghị | Cột **dẫn xuất** (computed) |
| Data Quality | Số trường bị impute → mức tin cậy + ghi chú | **Metadata** chất lượng dữ liệu |

#### 5.1.2. Late binding — truy vấn trực tiếp thay vì nhúng vào vector store

Quyết định kiến trúc quan trọng nhất ở đây là: **dữ liệu hồ sơ KHÔNG được nhúng vào Qdrant**, mà được truy vấn trực tiếp từ PostgreSQL tại thời điểm xử lý từng request rồi bơm thẳng vào prompt. Đây là mô hình **late binding** — gắn kết dữ liệu vào lúc xử lý truy vấn, không phải lúc lập chỉ mục — và nó xuất phát từ ba luận điểm cơ sở dữ liệu:

1. **Tránh "vector staleness".** Đơn vay là **dữ liệu trạng thái động**: tạo mới → chờ duyệt → phê duyệt/từ chối → cập nhật. Nếu nhúng vào vector store, mỗi lần trạng thái đổi sẽ khiến vector cũ không còn phản ánh thực tế, buộc phải re-ingest liên tục — vừa tốn chi phí embedding vừa sinh nguy cơ bất đồng bộ giữa hai kho.
2. **Nhất quán thời gian thực.** Truy vấn trực tiếp theo khóa chính cho độ trễ gần như hằng số và **luôn trả về dữ liệu mới nhất**, không có độ trễ lập chỉ mục.
3. **Bảo mật cách ly.** Vì dữ liệu cá nhân không bao giờ rời PostgreSQL để vào kho dùng chung, không tồn tại đường rò rỉ chéo giữa các khách hàng ở tầng vector; mỗi request chỉ đọc đúng `user_id` đã xác thực qua JWT.

### 5.2. Block 1 — Form Context (dữ liệu thô của khách hàng)

Form Context thiết lập "bức tranh tài chính cơ sở" của khách hàng — nền dữ liệu nguyên thủy để LLM hiểu nhu cầu vay trước khi tham chiếu tới bất kỳ đầu ra ML nào. Hàm `_build_form_context()` chiếu trực tiếp các cột của bản ghi `LoanApplication`, tổ chức thành năm nhóm logic:

| Nhóm | Các trường | Vai trò |
|---|---|---|
| Khoản vay cốt lõi | `loan_amount`, `term`, `monthly_income`, `dti`, điểm tín dụng | Nền định lượng để đánh giá tính khả thi của khoản vay |
| Việc làm | `employment_status`, `occupation_type`, `years_employed` | Độ ổn định nguồn thu (tập `_STABLE_EMPLOYMENT` được coi là tín hiệu tích cực) |
| Tài sản & mục đích | `is_homeowner`, `listing_category` | Tín hiệu ổn định tài chính; phù hợp chính sách sản phẩm |
| Lịch sử tín dụng (CIC) | `num_bureau_records`, `num_active_credit`, `total_overdue_amount`, `max_credit_overdue_days`, `has_bad_debt`, `income_verifiable_flag` | Bối cảnh tín dụng ngoài hệ thống; cảnh báo nợ quá hạn/nợ xấu |
| Nhân khẩu học | `age_years`, `gender`, `education_ordinal`, `is_married_flag`, `cnt_children`, `cnt_fam_members` | Chỉ tham chiếu khi chính sách yêu cầu rõ |

Một chi tiết về chất lượng dữ liệu cần nhấn mạnh ở trường **điểm tín dụng**: hệ thống lưu hai cột riêng — `credit_score` (khách **tự khai**, có thể trống) và `fico_score` (điểm Scorecard do mô hình hồi quy logistic tính ra, thang 300–850). Context Builder **ưu tiên `fico_score`** (điểm do hệ thống tính, đáng tin) và chỉ fallback về `credit_score` tự khai cho các đơn cũ chưa có điểm Scorecard. Quy ước này đảm bảo trợ lý hiển thị đúng điểm mô hình thay vì con số khách tự nhập. Đặc điểm quan trọng: Form Context **không chứa bất kỳ phép suy luận nào** — mọi diễn giải "DTI 45% là cao hay thấp" được ủy quyền hoàn toàn cho Block 3, theo nguyên tắc phân tách trách nhiệm.

### 5.3. Block 2 — ML Context và "hợp đồng dữ liệu" giữa ML và RAG

ML Context là khối làm cầu nối giữa **pipeline học máy** (mô hình LightGBM dự đoán rủi ro) và **lớp diễn giải ngôn ngữ** của RAG. Hàm `_build_ml_context()` đọc bảy trường kết quả đã được pipeline ML ghi vào `loan_applications`:

| Trường | Ý nghĩa | Cách RAG dùng |
|---|---|---|
| `default_probability` | Xác suất vỡ nợ ∈ [0,1]; ngưỡng `AUTO_REVIEW_THRESHOLD = 0.4` quyết định từ chối tự động | Diễn giải thành "khoảng 35%", giải thích lý do chấp nhận/từ chối |
| `risk_level` | Mức rủi ro rời rạc {Low, Medium, High} | Điều chỉnh giọng điệu phản hồi |
| `risk_score` | Điểm an toàn `= (1 − p) × 100`, **càng cao càng an toàn** | Trình bày kèm chú thích chiều đọc để tránh hiểu nhầm |
| `recommended_amount` | Hạn mức tối ưu mô hình đề xuất | So sánh với `loan_amount` ở Block 3 |
| `recommended_term` | Kỳ hạn tối ưu ∈ {12,…,60} | So sánh với `term` ở Block 3 |
| `model_version` | Định danh phiên bản, ví dụ `customer_lgbm_v4_stability` | Truy vết, kiểm toán |
| `has_prediction` | Cờ `default_probability is not None` | Kiểm tra trước khi render khối |

Điểm đáng chú ý nhất về mặt **kiến trúc dữ liệu** là: kết quả mô hình **không** được chuyền trực tiếp từ tiến trình suy luận ML sang prompt của RAG. Thay vào đó, chúng đi qua một chuỗi có kiểm soát: (1) `ml_service.predict()` hoàn tất suy luận → (2) ghi vào bảng `loan_applications` → (3) `_build_ml_context()` đọc lại từ bảng → (4) `_json_to_text()` định dạng → (5) bơm vào prompt. Bảng `loan_applications` ở giữa đóng vai trò một **hợp đồng dữ liệu (data contract) tường minh**: tập cột kết quả đã chuẩn hóa là **điểm giao tiếp duy nhất** giữa hai pipeline. Mô hình ML không cần biết RAG tồn tại, và RAG không cần biết kiến trúc nội tại của mô hình. Nhờ ranh giới này, hai thành phần độc lập, dễ bảo trì và thay thế — đây chính là tinh thần của thiết kế hướng-CSDL: dùng schema làm hợp đồng giữa các module.

### 5.4. Block 3 — Advisory Context: bộ máy luật xác định chống "bịa số"

Advisory Context là khối đặc biệt nhất: nó **không đọc từ kho lưu trữ nào**, mà được **sinh tại chỗ** bằng một bộ máy suy luận xác định trong `_build_advisory_context()`, kết hợp Form Context và ML Context để dẫn xuất các đặc trưng tư vấn. Có thể hình dung nó như logic của một **trigger / computed column** đặt ở tầng ứng dụng.

| Thành phần | Công thức / luật | Mục đích |
|---|---|---|
| `loan_vs_recommended` | `(loan − rec)/rec × 100`, phân ba vùng (cao hơn >10%, phù hợp ±10%, thấp hơn <−10%) | Đánh giá độ tương thích số tiền vay |
| `term_vs_recommended` | So `term` với `recommended_term` | Đề xuất điều chỉnh kỳ hạn |
| `dti_band` | Tra `_DTI_BANDS`: Tốt <30%, Cần chú ý 30–43%, Rủi ro cao >43% | Diễn giải DTI bằng nhãn định tính |
| `credit_score_band` | Tra `_CREDIT_BANDS`: Kém <580, Trung bình 580–669, Tốt 670–739, Rất tốt 740–799, Xuất sắc ≥800 | Phân loại điểm tín dụng theo thang chuẩn |
| `primary_risk_factors` | Tối đa 4, từ luật `if dti>0.43`, `if cs<580`, `if loan>rec×1.1`, `if has_bad_debt`, `if max_overdue>60`, `if total_overdue>0` | Nêu 2–4 nguyên nhân chính làm tăng rủi ro |
| `positive_factors` | Tối đa 4, từ `if is_homeowner`, `if dti<0.30`, `if cs≥740`, `if income_verifiable`, `if stable_employment`, `if years_employed≥3`, `if not has_bad_debt` | Cân bằng — ghi nhận điểm mạnh hồ sơ |
| `suggested_actions` | Danh sách khuyến nghị từ tập luật (giảm số tiền, giảm DTI, cải thiện điểm, xử lý nợ xấu) | Hướng dẫn cụ thể, hành động được |

Lý do đặt toàn bộ logic này **ở tầng Python theo luật cứng, không để LLM tự tính**, là một quyết định cốt lõi chống ảo giác. Nếu để LLM tự đánh giá "DTI 45% là cao hay thấp", kết quả sẽ thiếu nhất quán giữa các lượt vì `temperature > 0`. Bằng cách tính sẵn dải phân loại và yếu tố rủi ro ở tầng ứng dụng, hệ thống đảm bảo **mọi câu trả lời đều dựa trên cùng một bộ ngưỡng nghiệp vụ**, đồng thời cho phép **kiểm thử đơn vị (unit test) khối Advisory độc lập với LLM**. Về bản chất, Advisory Context là một **lớp chuyển ngữ**: biến các tham số kỹ thuật thô thành logic tư vấn có cấu trúc, triệt tiêu nguy cơ LLM bịa ra con số tài chính không có trong dữ liệu gốc.

### 5.5. Block 4 — Data Quality Context: định lượng độ tin cậy

Khối thứ tư đóng vai trò **hệ số bất định** cho toàn bộ phân tích. Hàm `_build_quality_context()` kiểm tra trường `imputed_features` — danh sách đặc trưng mà pipeline ML đã phải **gán giá trị mặc định (impute)** do khách hàng không cung cấp đủ. Dựa trên số lượng trường bị impute, hệ thống phân ba mức tin cậy:

| Số trường impute | Mức tin cậy | Chú thích bơm vào prompt |
|---|---|---|
| 0 | Cao | "Tất cả thông tin do khách hàng cung cấp trực tiếp." |
| 1–2 | Trung bình | "Một số dữ liệu được hệ thống mặc định… Kết quả tư vấn có thể chưa phản ánh toàn bộ tình hình." |
| ≥ 3 | Thấp | "Nhiều dữ liệu được hệ thống mặc định… Nên dùng ngôn ngữ thận trọng." |

Cơ chế này là một **tín hiệu kiểm soát (guardrail signal)** ở cấp ngữ cảnh đầu vào: khi tin cậy thấp, LLM được nhắc chuyển sang giọng thận trọng ("Dựa trên thông tin hiện có…") thay vì khẳng định tuyệt đối — bổ trợ trực tiếp cho Output Guardrail ở cấp văn bản. Đây là một ví dụ đẹp về việc **metadata chất lượng dữ liệu** được đưa thẳng vào vòng suy luận để điều tiết hành vi.

### 5.6. Định dạng và ví dụ render thực tế

Hàm `_json_to_text()` chuyển cấu trúc JSON bốn khối thành **văn bản phẳng có gạch đầu dòng** để bơm vào biến `{user_context}`. Định dạng văn bản (thay vì JSON/XML) được chọn vì thực nghiệm cho thấy Gemini hiểu danh sách rõ ràng tốt hơn, đồng thời dễ quan sát khi gỡ lỗi log. Ví dụ đầu ra cho một khách hàng rủi ro cao:

```
THÔNG TIN ĐƠN VAY GẦN NHẤT
- Trạng thái đơn: PENDING_REVIEW
- Số tiền xin vay: $20,000 | Kỳ hạn: 36 tháng | Thu nhập: $12,000
- DTI: 46.0% — Rủi ro cao (> 43%)
- Điểm tín dụng: 564 — Kém (< 580)
KẾT QUẢ ML
- Xác suất vỡ nợ: 43.2% | Mức rủi ro: High | Risk score: 57/100 (càng cao càng an toàn)
- Hạn mức đề xuất: $3,000 / 12 tháng | So sánh: cao hơn đề xuất 567%
PHÂN TÍCH TƯ VẤN
- Yếu tố rủi ro: DTI quá cao; điểm tín dụng thấp; số tiền vượt hạn mức đề xuất
- Điểm tích cực: việc làm ổn định; không có nợ xấu
- Khuyến nghị: giảm số tiền về $3,000; giảm DTI; cải thiện điểm tín dụng
ĐỘ TIN CẬY DỮ LIỆU
- Mức độ tin cậy: Trung bình (một số trường được mặc định)
```

### 5.7. Lắp ghép prompt và cơ chế định vị kép (dual-grounding)

Prompt cuối cùng (`prompts.py`) là một `ChatPromptTemplate` gồm **8 biến**: phần system chứa 6 placeholder (tên khách hàng, hướng dẫn giọng điệu, hướng dẫn theo ý định, **hồ sơ khách hàng / User Context**, tóm tắt hội thoại, **tài liệu liên quan / Knowledge Base**), cộng `chat_history` và `question`. Quy tắc số 7 trong system prompt quy định thứ tự ưu tiên khi hai nguồn mâu thuẫn: *"Với câu hỏi cá nhân, LUÔN ưu tiên THÔNG TIN HỒ SƠ KHÁCH HÀNG; TÀI LIỆU LIÊN QUAN chỉ là bổ trợ chính sách."*

Đây là cơ chế **định vị kép (dual-grounding)** — sức mạnh trung tâm của hệ thống:

- **Định vị tĩnh (Static Grounding):** câu hỏi về chính sách/quy trình được neo vào `policy.md`, `faq.md` truy xuất từ Qdrant — đảm bảo độ chính xác thực tế.
- **Định vị động (Dynamic Grounding):** câu hỏi về hồ sơ cá nhân/kết quả ML được neo vào 4-block User Context bơm trực tiếp từ PostgreSQL — đảm bảo cá nhân hóa và đúng dữ liệu thật.

Sự phân tách này giải thích một hiện tượng đáng chú ý ở phần đánh giá (Chương 6): các câu hỏi cá nhân hóa có **Context Precision = 0** (không tài liệu KB nào được truy xuất) nhưng vẫn trả lời đúng — vì chúng được định vị từ User Context chứ không từ KB. Đây không phải lỗi pipeline, mà là hệ quả tất yếu của kiến trúc dual-grounding.

### 5.8. Chat Memory — quản lý vòng đời dữ liệu hội thoại

Bộ nhớ hội thoại là một bài toán quản lý dữ liệu thuần túy: hội thoại càng dài thì prompt càng phình, tốn token; nhưng cắt cụt lịch sử lại khiến trợ lý quên ngữ cảnh. Hàm `load_memory()` (`memory.py`) hóa giải bằng **hai cơ chế bổ sung cho nhau**, đọc/ghi trên `chat_sessions` và `chat_messages`.

**(a) Cửa sổ trượt theo ngân sách token.** Hệ thống lấy các tin của phiên (lọc bỏ tin lỗi qua `WHERE error = false`, và loại riêng tin user vừa lưu qua `exclude_message_id`), sắp xếp mới-nhất-trước, rồi `_split_window` duyệt ngược về quá khứ cộng dồn chi phí token ước lượng thô (`len(text) // 4`) cho tới khi chạm trần `rag_memory_window_token_budget = 2000`. Phần "gần đây" trong cửa sổ được đưa nguyên văn vào `chat_history`. Một chi tiết bảo vệ tinh tế: **lượt mới nhất không bao giờ bị loại** dù tự thân nó vượt ngân sách, để câu hỏi vừa đặt luôn hiện diện.

**(b) Đệm tóm tắt lười (lazy summary buffer) với con trỏ bao phủ.** Phần hội thoại cũ hơn cửa sổ được nén thành một bản tóm tắt tiếng Việt lưu ở cột `chat_sessions.summary`. Điểm "lười" — và là một kỹ thuật quản lý dữ liệu đẹp — nằm ở **con trỏ bao phủ `summary_covers_until_id`**, hoạt động như một **watermark/checkpoint**: tóm tắt chỉ thực sự được tính lại khi (1) số tin cũ chưa tóm tắt đạt ngưỡng `rag_memory_min_messages_to_summarize = 6`, **và** (2) bản tóm tắt hiện có chưa bao phủ tới tin cũ nhất (`summary_covers_until_id != last_id`). Nhờ watermark, hệ thống tránh tính lại tóm tắt vô ích sau mỗi tin nhắn — tiết kiệm phần lớn chi phí LLM mà vẫn giữ ngữ cảnh dài hạn.

**(c) Ghi tóm tắt có giao dịch (transactional).** Khi cần tóm tắt, một LLM riêng (`temperature=0.2`, `max_tokens=500`) hợp nhất tóm tắt cũ với các lượt mới. Việc cập nhật ba trường (`summary`, `summary_covers_until_id`, `summary_updated_at`) được bao trong một giao dịch: nếu `commit` thất bại, hệ thống **rollback và khôi phục cả ba trường về giá trị cũ**, đảm bảo trạng thái tóm tắt luôn nhất quán. Đúng triết lý suy giảm duyên dáng, nếu việc tóm tắt lỗi thì lượt chat không sập — chỉ giữ tóm tắt cũ và ghi log cảnh báo.

### 5.9. Loan Adjustment Tool — RAG hành động trên dữ liệu, bảo toàn lịch sử

Tính năng điều chỉnh khoản vay biến trợ lý từ "cỗ máy trả lời" thành **tác nhân hành động**: khi một đơn rơi vào `AUTO_REJECTED`, thay vì chỉ giải thích, trợ lý có thể tự mô phỏng phương án và **nộp lại đơn** thay khách (`loan_adjustment_tool.py`, điều phối bởi `chat_service.py`).

**Phát hiện ý định.** `_is_loan_adjustment_request` dùng bộ luật từ khóa tiếng Việt (cả biến thể không dấu), cố tình bao gồm chính những cụm mà trợ lý gợi ý làm nút trả lời nhanh ("gói vay phù hợp", "đề xuất phương án") để khép kín vòng tương tác.

**Sinh và kiểm chứng phương án.** `find_best_reapplication_option` dựng tập ứng viên từ **hai nguồn rồi hợp nhất**: (1) một **bộ đề xuất mềm bằng LLM** (`loan_adjustment_reasoner`, bật qua `rag_loan_reasoner_enabled`) đọc bản tóm tắt rủi ro tất định của đơn bị từ chối và đề xuất tối đa sáu phương án JSON, với ràng buộc chỉ giảm số tiền và chỉ giữ/tăng kỳ hạn; (2) một **lưới cứng tất định** (`_grid_candidates`) thử kéo dài kỳ hạn trong {12,…,60} và giảm số tiền theo các mốc 75%/50%/25%/sàn 500$. `merge_candidates` gộp (ưu tiên LLM), làm sạch và khử trùng. Mấu chốt độ tin cậy: **mọi ứng viên đều được đưa lại đúng mô hình ML production qua `ml_service.predict` trong một lượt quét duy nhất**, lấy xác suất vỡ nợ thật; một ứng viên chỉ "đạt" khi `prob < 0.4` **và** qua `validate_confirmed_values`. Các phương án đạt được xếp hạng bằng khoá thống nhất **ưu tiên thay đổi ít nhất so với đơn gốc** (`_unified_rank`), trả về tối đa ba; nếu không phương án nào lọt ngưỡng, hệ thống chuyển `fallback_proposal` trình bày ba biểu mẫu tốt nhất kèm cảnh báo cần admin duyệt.

**Vòng xác nhận có trạng thái, lưu trên JSONB.** Phương án được lưu vào cột `chat_sessions.pending_action` (kiểu **JSONB** trên PostgreSQL) kèm thời gian sống 30 phút (`PENDING_ACTION_TTL_MINUTES`). Ở lượt kế, `_handle_pending_loan_adjustment_response` đọc câu trả lời của khách; nếu phủ định thì hủy, nếu khẳng định thì `_confirm_pending_loan_adjustment` gọi `application_service.confirm`. Việc dùng một cột JSONB để lưu trạng thái hành động đang chờ là một lựa chọn dữ liệu linh hoạt: nó cho phép lưu cấu trúc lồng (danh sách phương án, mốc thời gian) ngay trong bản ghi phiên mà không cần bảng phụ.

**Bảo toàn tính toàn vẹn lịch sử.** Một nguyên tắc dữ liệu được tuân thủ tuyệt đối: thao tác nộp lại **tạo một bản ghi `loan_applications` hoàn toàn mới** (chỉ khác số tiền và kỳ hạn, giữ nguyên mọi số liệu còn lại), **không bao giờ sửa đơn bị từ chối cũ**. Đơn cũ được giữ nguyên trạng như một bản ghi lịch sử bất biến (append-only), bảo đảm khả năng kiểm toán và truy vết toàn bộ vòng đời hồ sơ.

### 5.10. Singleton và an toàn đa luồng — quản lý tài nguyên dùng chung

Backend FastAPI phục vụ nhiều request đồng thời trên nhiều luồng, trong khi khởi tạo client LLM/embedding/Qdrant và đặc biệt nạp mô hình reranker ~1,1 GB đều rất tốn kém. Để tránh khởi tạo lặp, các tài nguyên dùng chung được cache ở mức module theo mẫu **khóa kiểm tra hai lần (double-checked locking)**:

```python
def get_chain():
    global _chain
    if _chain is None:                 # kiểm tra 1 (không khóa, đường nóng)
        with _chain_lock:              # chỉ khóa khi cần khởi tạo
            if _chain is None:         # kiểm tra 2 (trong khóa, an toàn)
                _chain = chat_prompt | llm | StrOutputParser()
    return _chain
```

Kiểm tra ngoài khóa cho đường nóng (đã khởi tạo) chạy không tranh chấp; khóa chỉ chặn lần đầu; kiểm tra lần hai bên trong khóa đảm bảo đúng một luồng khởi tạo. Mẫu này lặp lại ở `get_retriever`, `_get_classifier_llm` và LLM của bộ reasoner. Reranker đi xa hơn với **lazy loading**: `Reranker._ensure_loaded` chỉ nạp `TextCrossEncoder` ở lần rerank đầu tiên, nên nếu rerank bị tắt qua config thì mô hình 1,1 GB không bao giờ được tải. Để tránh độ trễ ở request thật đầu tiên, `main.py` thực hiện **pre-warm** reranker qua sự kiện `startup` (tải mô hình ngay khi khởi động server). Nhìn chung, đây là các kỹ thuật **quản lý vòng đời tài nguyên/kết nối** — tương tự connection pooling — áp dụng cho các đối tượng nặng dùng chung giữa nhiều request.

---

## 6. Đánh giá chất lượng

### 6.1. Một khung đánh giá xác định, tái lập được

Đánh giá hệ thống RAG vốn khó vì đầu ra là văn bản tự do, không có đáp án duy nhất để so khớp như bài toán phân loại. Cách phổ biến là dùng một LLM khác chấm điểm, nhưng cách đó vừa đắt, vừa chậm, vừa thiếu tái lập (bản thân LLM chấm điểm cũng ngẫu nhiên). CreditIntel chọn hướng khác: xây một **khung đánh giá hoàn toàn xác định, không cần LLM chấm điểm**, gồm ba module `eval_metrics.py`, `eval_runner.py`, `eval_dataset.py`. Khung chạy nhanh, cho kết quả lặp lại giữa các lần chạy, và đủ nhẹ để nhúng vào CI như một cổng chặn chất lượng.

Nền tảng là một **bộ dữ liệu kiểm thử** lưu trong JSON do `eval_dataset.py` quản lý, với ràng buộc cứng **30–50 case**. Mỗi case mô tả đầy đủ một tình huống: câu hỏi, đáp án tham chiếu (`ground_truth`), nguồn tài liệu kỳ vọng (`expected_sources`), thuật ngữ kỳ vọng trong ngữ cảnh (`expected_context_terms`), cụm bắt buộc có (`must_include`), cụm cấm tuyệt đối (`must_not_include`), và nhãn nhóm (`group`: policy/faq/guardrail/edge_case/personalized). Bộ nạp **từ chối** dataset thiếu trường bắt buộc hoặc trùng `id` — một ràng buộc toàn vẹn ngay ở đầu vào, giống ràng buộc khóa/NOT NULL trong CSDL.

### 6.2. Ba chỉ số

| Chỉ số | Công thức | Đo điều gì |
|---|---|---|
| **Faithfulness** | `0.7 × độ phủ + 0.3 × tỷ lệ có cơ sở − 0.25 × số cụm cấm xuất hiện` | Câu trả lời có chứa ý bắt buộc và có cơ sở trong ngữ cảnh/hồ sơ không |
| **Context Precision** | tỷ lệ đoạn truy xuất thực sự liên quan / tổng đoạn trả về | Độ "sạch" của khâu truy xuất |
| **Overall** | `0.6 × Faithfulness + 0.4 × Context Precision` | Điểm tổng hợp mỗi case |

Một case "đạt" khi `Overall ≥ PASS_THRESHOLD = 0.75`. Toàn bộ việc khớp cụm đi qua `normalize_text` (chuẩn hóa dấu câu, hạ chữ thường, gộp khoảng trắng) và hỗ trợ cú pháp biến thể `"A | B"` để bám sát sự đa dạng tiếng Việt. Khung còn có cơ chế **phát hiện hồi quy** cho CI: `diff_results` so kết quả với baseline theo từng `id`; một case bị gắn cờ nếu tụt quá `CASE_REGRESSION_DELTA = −0.15` hoặc rơi từ đạt xuống không đạt, và cả run bị gắn cờ nếu điểm trung bình tụt quá `RUN_REGRESSION_DELTA = −0.05`. Với cờ `--fail-on-regression`, runner trả mã thoát khác 0 để tự động chặn merge.

### 6.3. Kết quả thực nghiệm

Bộ eval **31 case** chạy trên pipeline hiện hành (hybrid + rerank k=20→12, top_k=4 parent, Gemini `temperature=0.3`), trên collection `creditintel-kb` (76 điểm). Không case nào lỗi gọi hàm.

| Chỉ số (toàn bộ 31 case) | Giá trị |
|---|---|
| Faithfulness trung bình | 0.850 |
| Context Precision trung bình | 0.774 |
| Overall trung bình | 0.819 |
| Số case đạt (`overall ≥ 0.75`) | 23/31 |

Tách theo nhóm cho thấy phân bố không đều và làm lộ một **artifact của thước đo**:

| Nhóm | n | Faithfulness | Context Precision | Overall |
|---|---|---|---|---|
| `policy` | 5 | 0.953 | 0.950 | 0.952 |
| `faq` | 10 | 0.930 | 0.975 | 0.948 |
| `guardrail` | 6 | 0.692 | 1.000 | 0.815 |
| `edge_case` | 5 | 0.787 | 0.700 | 0.752 |
| `personalized` | 5 | 0.837 | **0.000** | 0.502 |

Năm case `personalized` "rớt" (`overall ≈ 0.50`) **không phải vì câu trả lời sai**, mà vì chúng lấy cơ sở từ **User Context** (4-block hồ sơ tính sẵn) chứ không từ tài liệu KB — trong khi Context Precision chỉ chấm độ sạch của tài liệu KB trả về. Với câu hỏi cá nhân, retrieval thường không (và không cần) trả về doc KB nào, nên precision = 0 **theo thiết kế**. Faithfulness của nhóm này vẫn cao (0.837), xác nhận nội dung trả lời đúng. Nếu loại artifact này (bỏ nhóm personalized khỏi phép đo precision), Context Precision trên 26 case còn lại đạt **≈ 0.92** và tỷ lệ đạt thực chất là 23/26 (~88%).

Hiện tượng này chính là **bằng chứng định lượng** cho luận điểm trung tâm của chương: kiến trúc **dual-grounding** khiến một phần lớn giá trị của hệ thống đến từ **User Context dựng từ dữ liệu người dùng + kết quả ML**, chứ không từ kho tri thức tĩnh — và đó là điều một thước đo precision-trên-KB không nắm bắt được. Đây cũng là hạn chế đã biết của khung đo: hướng khắc phục là tách một chỉ số **"user-context grounding"** riêng cho nhóm cá nhân hóa, và bổ sung tập "đoạn vàng" để đo Context Recall đúng nghĩa. *(Phần bàn luận tổng về điểm mạnh, hạn chế và hướng phát triển của toàn hệ thống được trình bày ở chương kết luận của báo cáo.)*



