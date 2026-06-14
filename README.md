# CreditIntel - Hệ Thống Quản Lý & Đánh Giá Rủi Ro Khoản Vay

> Dự án môn Hệ Quản Trị CSDL - Nhóm KH086  
> FastAPI Backend + React Frontend + Home Credit Stability ETL + Machine Learning

## Kiến Trúc Tổng Quan Hệ Thống

Dự án CreditIntel được phát triển theo mô hình phân lớp rõ ràng, kết hợp chặt chẽ giữa xử lý dữ liệu (Data Engineering), huấn luyện mô hình (Machine Learning) và vận hành trực tuyến (Web Application + RAG Chatbot).

```mermaid
graph TB
    User(("👤 Người dùng")) --> Login["🔐 Đăng nhập / Đăng ký"]
    Login --> JWT["🔑 Zustand Store\n(Bearer JWT Auth)"]

    %% Phân nhánh theo vai trò
    JWT -->|Role: Customer| FE_C
    JWT -->|Role: Admin| FE_A

    subgraph FE_C["📋 Giao diện Khách hàng (React)"]
        direction TB
        C_MAIN["📊 Portal (Dashboard / Apply / History)"]
        C_CHAT["💬 Chat AI (RAG Chatbot)"]
    end

    subgraph FE_A["🛡️ Giao diện Admin (React)"]
        direction TB
        A_PANEL["🖥️ Admin Panel (Review & Stats)"]
    end

    %% Kết nối Frontend -> API Gateway
    C_MAIN -->|"REST API"| ROUTERS
    C_CHAT -->|"REST API"| ROUTERS
    A_PANEL -->|"REST API"| ROUTERS

    subgraph BACKEND["⚙️ Backend & API Layer (FastAPI)"]
        direction TB
        subgraph API_GW["🌐 API Gateway & Security"]
            ROUTERS["🌐 API Routers\n/auth · /applications · /admin · /chat · /credit-score"]
            JWT_MW["🛂 JWT Auth Middleware\n(Roles verification & Verification)"]
            ROUTERS --> JWT_MW
        end

        subgraph SERVICES["📦 Business Services"]
            direction TB
            SVC_AUTH["🔑 auth_service\n(Đăng nhập / Đăng ký / JWT)"]
            SVC_APP["📄 application_service\n(Nghiệp vụ hồ sơ vay)"]
            SVC_ADMIN["🛡️ admin_service\n(Phê duyệt & Thống kê)"]
            SVC_ML["🧠 ml_service\n(LightGBM risk inference)"]
            SVC_CS["📈 credit_score_service\n(FICO score & SHAP)"]
            SVC_CHAT["💬 chat_service\n(Orchestrate RAG session)"]
            SVC_ADJ["🛠️ loan_adjustment_tool\n(Mô phỏng khoản vay)"]
            
            SVC_CHAT --> SVC_ADJ
            SVC_CHAT --> SVC_APP
            SVC_APP --> SVC_ML
            SVC_ADJ --> SVC_ML
        end
        JWT_MW --> SERVICES
    end

    %% Kết nối Services -> Chuyên sâu RAG / ML
    SVC_CHAT -->|"Gọi RAG Pipeline"| RAG_MOD
    SVC_ML -->|"Chạy mô hình"| ML_MOD
    SVC_CS -->|"Tính FICO / SHAP"| ML_MOD

    subgraph RAG_MOD["🤖 RAG Module (backend/rag/)"]
        direction TB
        CHAIN["chain.py (RAG Pipeline)"]
        RETRIEVER["retriever.py (Hybrid Search)"]
        CHAIN --> RETRIEVER
    end

    subgraph ML_MOD["🧠 ML Module (machinelearning/)"]
        direction TB
        RISK_M["customer_risk_model.pkl\n(LightGBM v4)"]
        SCORE_M["scorecard_model.pkl\n(FICO score)"]
    end

    %% Kết nối xuống Cơ sở dữ liệu và API ngoài
    RAG_MOD -->|"Search vector"| QD[("🔷 Qdrant\nVector DB")]
    RAG_MOD -->|"LLM & Embed"| OR["☁️ OpenRouter API\n(Gemini 2.5 Flash)"]
    SERVICES -->|"Lưu đơn/Chat/Users"| PG[("🐘 PostgreSQL")]

    %% ===== STYLING =====
    classDef user fill:#6366f1,stroke:#4f46e5,color:#fff,stroke-width:2px
    classDef auth fill:#14b8a6,stroke:#0d9488,color:#fff
    classDef jwt fill:#f97316,stroke:#ea580c,color:#fff
    classDef cust fill:#0ea5e9,stroke:#0284c7,color:#fff
    classDef adm fill:#f97316,stroke:#c2410c,color:#fff
    classDef be fill:#f59e0b,stroke:#d97706,color:#fff
    classDef jwt_mw fill:#ef4444,stroke:#dc2626,color:#fff
    classDef svc fill:#fbbf24,stroke:#d97706,color:#000
    classDef rag fill:#8b5cf6,stroke:#7c3aed,color:#fff
    classDef ml fill:#10b981,stroke:#059669,color:#fff
    classDef db fill:#64748b,stroke:#475569,color:#fff
    classDef ext fill:#ec4899,stroke:#db2777,color:#fff

    class User user
    class Login auth
    class JWT jwt
    class C_MAIN,C_CHAT cust
    class A_PANEL adm
    class ROUTERS be
    class JWT_MW jwt_mw
    class SVC_AUTH,SVC_APP,SVC_ADMIN,SVC_ML,SVC_CS,SVC_CHAT,SVC_ADJ svc
    class CHAIN,RETRIEVER rag
    class RISK_M,SCORE_M ml
    class PG,QD db
    class OR ext

    style FE_C fill:transparent,stroke:#0ea5e9,stroke-width:2px
    style FE_A fill:transparent,stroke:#f97316,stroke-width:2px
    style BACKEND fill:transparent,stroke:#f59e0b,stroke-width:2px
    style API_GW fill:transparent,stroke:#fbbf24,stroke-width:1px,stroke-dasharray:5 5
    style SERVICES fill:transparent,stroke:#d97706,stroke-width:1px,stroke-dasharray:5 5
    style RAG_MOD fill:transparent,stroke:#7c3aed,stroke-width:3px
    style ML_MOD fill:transparent,stroke:#10b981,stroke-width:3px
```



> **Chú thích kiến trúc tổng quan:**
> 1. **Giao thức & Phân Quyền**: Người dùng đăng nhập qua JWT Bearer. Token được lưu trữ tại Zustand store ở Frontend và được tự động đính kèm vào header của mọi API request. Backend verify JWT thông qua Middleware kiểm tra vai trò khách hàng (`require_customer`) hoặc quản trị viên (`require_admin`).
> 2. **Xử Lý Nghiệp Vụ (Services)**: Lớp dịch vụ FastAPI quản lý toàn bộ business logic. `ml_service` thực hiện dự đoán rủi ro vỡ nợ tức thời (LightGBM) khi người dùng nộp đơn; `credit_score_service` tính toán FICO score và giải thích SHAP; `chat_service` điều phối hội thoại RAG và gọi `loan_adjustment_tool`.
> 3. **Huấn Luyện ML Offline**: Các mô hình ML được huấn luyện offline bằng DuckDB local từ nguồn dữ liệu Kaggle Home Credit Stability, xuất ra các file `.pkl` để Backend sử dụng trực tiếp tại runtime.
> 4. **Hệ Thống RAG**: RAG được cô lập khỏi DB nghiệp vụ và liên kết trực tiếp với Qdrant Vector DB, sử dụng OpenRouter làm cổng kết nối LLM (Gemini) và dense embeddings.

---

## Kiến Trúc RAG Pipeline Chi Tiết

Hệ thống RAG của CreditIntel triển khai một pipeline đa giai đoạn cực kỳ bảo mật, chính xác cao và tích hợp sẵn máy trạng thái (state machine) giúp người dùng thực hiện nộp lại hồ sơ thay đổi kỳ hạn trực tiếp từ giao diện chat.

```mermaid
flowchart TD
    UserMsg(["👤 Câu hỏi của User"]) --> InputGuard{"🛂 Input Guardrail"}

    InputGuard -->|Không an toàn| BlockedMsg["❌ Từ chối\n· Bảo mật / Độ dài"]
    InputGuard -->|An toàn| IntentRoute{"🔀 Intent Router"}

    subgraph RETRIEVAL["🔍 Retrieval Pipeline"]
        QueryRewrite["🔄 Query Rewriter\nViết lại truy vấn độc lập"]
        HybridSearch[("🔷 Qdrant Hybrid Search\nDense + Sparse BM25")]
        Rerank["⚡ Cross-Encoder Reranker\nTop-20 → Top-12"]
        ParentExpand["📂 Parent Document Expansion\nTop-12 → Top-4 Sections"]

        QueryRewrite --> HybridSearch --> Rerank --> ParentExpand
    end

    IntentRoute -->|Inquiry / Policy / Risk| QueryRewrite
    IntentRoute -->|Greeting / Off-topic| SkipRetrieval["Bỏ qua Retrieval"]

    subgraph LOAN_ADJ["🛠️ Loan Adjustment State Machine"]
        AdjCheck{"Kiểm tra\npending_action"}
        RunAdj["Chạy ML simulate\nTìm phương án tối ưu"]
        SetPending["Lưu pending_action\nĐề xuất kỳ hạn/hạn mức"]
        ProcessConfirm["📝 Tự động nộp\nđơn vay mới"]

        AdjCheck -->|Chưa có proposal| RunAdj --> SetPending
        AdjCheck -->|Nhận xác nhận| ProcessConfirm
    end

    IntentRoute -->|Loan adjustment| AdjCheck

    subgraph PROMPT["📝 Prompt Assembly"]
        SysPrompt["System Prompt + Rules"]
        UserCtx["4-Block User Context\n· DB: Info, ML, Rec"]
        RetContext["Retrieved Docs\n· Knowledge Base"]
        ToneCtx["Personalization Tone\n· Status-based"]
        ConvMem["Conversation Summary\n+ Window History"]
    end

    ParentExpand --> PROMPT
    SkipRetrieval --> PROMPT
    SetPending --> PROMPT

    PROMPT --> LLMGen["🤖 LLM Gemini 2.5 Flash\ntemperature = 0.3"]
    LLMGen --> OutputGuard{"🛂 Output Guardrail"}

    OutputGuard -->|Rò rỉ DB/Key| Sanitize["Thay nội dung an toàn"]
    OutputGuard -->|Hứa phê duyệt| Disclaimer["Chèn disclaimer"]
    OutputGuard -->|Đạt chuẩn| SaveMsg["💾 Lưu Q&A + Memory"]

    Sanitize --> SaveMsg
    Disclaimer --> SaveMsg
    ProcessConfirm --> UserResponse
    SaveMsg --> UserResponse(["👤 Trả lời + Sources"])

    %% ===== Node colors =====
    classDef guard fill:#ef4444,stroke:#dc2626,color:#fff
    classDef retrieval fill:#8b5cf6,stroke:#7c3aed,color:#fff
    classDef prompt fill:#0ea5e9,stroke:#0284c7,color:#fff
    classDef llm fill:#ec4899,stroke:#db2777,color:#fff
    classDef adj fill:#f59e0b,stroke:#d97706,color:#fff
    classDef store fill:#64748b,stroke:#475569,color:#fff

    class InputGuard,OutputGuard,BlockedMsg guard
    class QueryRewrite,HybridSearch,Rerank,ParentExpand,SkipRetrieval,IntentRoute retrieval
    class SysPrompt,UserCtx,RetContext,ToneCtx,ConvMem prompt
    class LLMGen llm
    class AdjCheck,RunAdj,SetPending,ProcessConfirm adj
    class Sanitize,Disclaimer,SaveMsg,UserResponse store

    %% ===== Subgraph: viền rõ, nền trong suốt =====
    style RETRIEVAL fill:transparent,stroke:#7c3aed,stroke-width:3px
    style LOAN_ADJ fill:transparent,stroke:#f59e0b,stroke-width:3px
    style PROMPT fill:transparent,stroke:#0ea5e9,stroke-width:2px
```

### Các Giai Đoạn Trong RAG Pipeline:

1. **Input Guardrail (`guardrails.py`)**: 
   - Kiểm soát độ dài đầu vào (`MAX_INPUT_LENGTH = 2000`).
   - Sử dụng các mẫu Regex cứng để phát hiện các cuộc tấn công prompt-injection (như jailbreak, yêu cầu in system prompt) hoặc thăm dò thông tin cá nhân (PII probing - cố tình hỏi thông tin của khách hàng khác). Nếu kích hoạt, tin nhắn bị chặn ngay lập tức.
2. **Intent Router (`router.py`)**: 
   - Phân loại tin nhắn của người dùng vào 1 trong 6 ý định: `loan_inquiry`, `risk_explanation`, `policy_question`, `personal_advice`, `greeting`, `off_topic`.
   - Kết hợp khớp nhanh từ khóa (keyword fast-path) để giảm độ trễ và gọi LLM phân loại JSON nếu không khớp từ khóa.
   - Các ý định `greeting` và `off_topic` sẽ bỏ qua bước tìm kiếm tài liệu để tiết kiệm chi phí.
3. **Query Rewriter (`query_rewriter.py`)**:
   - Sử dụng mô hình `google/gemini-2.5-flash` để chuyển câu hỏi hiện tại của người dùng thành câu truy vấn độc lập (standalone query) dựa trên tóm tắt hội thoại và lịch sử chat (tối đa 6 tin nhắn gần nhất) nhằm tối ưu hóa kết quả tìm kiếm ngữ nghĩa.
4. **Hybrid Search & Reranking (`retriever.py`, `reranker.py`, `chunking.py`)**:
   - **Tìm kiếm hỗn hợp (Hybrid Search)**: Qdrant kết hợp tìm kiếm vector dense (OpenAI `text-embedding-3-small` qua OpenRouter) và tìm kiếm vector sparse (BM25 thông qua thư viện `FastEmbedSparse` local).
   - **Reranker**: Sử dụng Cross-Encoder Reranker (`fastembed.rerank.cross_encoder.TextCrossEncoder`) để chấm điểm độ liên quan trực tiếp giữa câu hỏi và top 20 chunks kết quả, lấy ra top 12.
   - **Parent-Child Expansion (Bản đồ phân mảnh)**: Chunks được lưu trữ ở dạng child chunks nhỏ (tối đa 700 ký tự) để tăng độ chính xác khi đối sánh vector, nhưng khi trả về cho prompt sẽ được ánh xạ ngược lên parent document/section hoàn chỉnh chứa heading tương ứng (tối đa 3500 ký tự) để tránh đứt gãy ngữ cảnh.
5. **Personalization (`personalizer.py`)**:
   - Tự động điều chỉnh giọng điệu và chỉ dẫn (tone/instructions) cho LLM theo trạng thái hồ sơ thực tế của người dùng:
     - `auto_rejected` / `admin_rejected` -> Đồng cảm, khích lệ, gợi ý hướng cải thiện (giảm DTI, tăng FICO).
     - `pending_review` -> Hướng dẫn quy trình, thông tin thời gian xử lý.
     - `approved` / `awaiting_info` -> Chúc mừng, hướng dẫn các tài liệu cần tải lên (CCCD, SĐT).
     - `info_submitted` -> Yên tâm, giải thích bước xử lý tiếp theo.
     - Không có hồ sơ -> Thân thiện, giới thiệu dịch vụ.
6. **Memory & Persistence (`memory.py`)**:
   - Áp dụng chiến lược bộ nhớ đệm trượt (sliding window) kết hợp tóm tắt lười (lazy summarization). 
   - Duy trì các tin nhắn gần nhất trong giới hạn token budget. Các tin nhắn cũ hơn sẽ được LLM tự động tóm tắt gộp vào `ChatSession.summary` và lưu vào PostgreSQL để giữ bộ nhớ dài hạn mà không làm tràn ngữ cảnh LLM.
7. **Máy trạng thái điều chỉnh khoản vay (Loan Adjustment State Machine)**:
   - Nếu người dùng có đơn bị `AUTO_REJECTED` hỏi về các phương án điều chỉnh (thay đổi kỳ hạn/số tiền vay), `chat_service` sẽ chuyển luồng xử lý tới `loan_adjustment_tool`.
   - Tool tự động giả định (simulate) qua mô hình ML các tổ hợp kỳ hạn (12, 24, 36, 48, 60 tháng) và số tiền vay tối ưu để tìm ra phương án có xác suất vỡ nợ dưới ngưỡng an toàn `0.4`.
   - Nếu tìm thấy, phương án điều chỉnh sẽ được lưu dưới dạng `pending_confirmation` trong cột `pending_action` của session chat, và chatbot hiển thị câu hỏi đề xuất đồng ý/từ chối.
   - Nếu người dùng nhập các từ khóa xác nhận ("đồng ý", "xác nhận", "ok"), hệ thống tự động gọi service nộp lại hồ sơ mới (`application_service.confirm`) và thông báo kết quả tức thời.
8. **Output Guardrail (`guardrails.py`)**:
   - Kiểm tra kết quả đầu ra của LLM trước khi hiển thị cho người dùng.
   - Phát hiện và che giấu các rò rỉ dữ liệu hệ thống (như tên bảng DB, chuỗi API key, password hash).
   - Phát hiện các câu hứa hẹn phê duyệt 100% của LLM để tự động chèn cảnh báo từ chối trách nhiệm (disclaimer) - khẳng định quyết định cuối cùng thuộc về Admin.

---

## Kiến Trúc ETL & Machine Learning

```mermaid
flowchart TD
    subgraph SOURCE["📂 Nguồn Dữ Liệu"]
        CSV["Home Credit Stability\ntrain_base.parquet\nbureau · previous_application"]
    end

    CSV --> BRONZE

    subgraph ETL["🔄 ETL Pipeline — machinelearning/etl/"]
        BRONZE["🥉 load_bronze.py\nLoad Parquet → DuckDB raw"]
        SILVER["🥈 etl_silver.py\nClean + Transform\ntransform_silver_hcv2.sql"]
        GOLD["🥇 etl_gold.py\nFeature Engineering\ntransform_gold_hcv2.sql"]

        BRONZE -->|Raw data| SILVER -->|Clean data| GOLD
    end

    GOLD -->|"gold.hc_features_v2"| VALIDATE

    subgraph TRAINING["🧠 ML Training — machinelearning/ml/"]
        VALIDATE["validate_data.py\nKiểm tra chất lượng"]
        TRAIN_RISK["retrain_customer_model.py\nLightGBM · 35 features\nDự đoán rủi ro vỡ nợ"]
        TRAIN_SCORE["train_scorecard.py\nLogistic Regression\nFICO Scorecard 300–850"]

        VALIDATE --> TRAIN_RISK
        VALIDATE --> TRAIN_SCORE
    end

    TRAIN_RISK -->|Xuất model| PKL_RISK
    TRAIN_SCORE -->|Xuất model| PKL_SCORE

    subgraph ARTIFACTS["📦 Model Artifacts — .pkl"]
        PKL_RISK["customer_risk_model.pkl\npipeline + thresholds + feature_cols"]
        PKL_SCORE["scorecard_model.pkl\npipeline + thresholds + dti_p75"]
    end

    PKL_RISK -->|"joblib.load()"| ML_RT
    PKL_SCORE -->|"joblib.load()"| CS_RT

    subgraph RUNTIME["⚡ Runtime Inference — backend/services/"]
        ML_RT["ml_service.py\npredict → risk level + suggestion"]
        CS_RT["credit_score_service.py\nget_credit_score → FICO"]
    end

    DUCKDB[("🦆 DuckDB\nmachinelearning/data/")]
    BRONZE -.-> DUCKDB
    SILVER -.-> DUCKDB
    GOLD -.-> DUCKDB

    %% ===== Node colors =====
    classDef source fill:#f59e0b,stroke:#d97706,color:#fff
    classDef etl fill:#0ea5e9,stroke:#0284c7,color:#fff
    classDef ml fill:#8b5cf6,stroke:#7c3aed,color:#fff
    classDef artifact fill:#10b981,stroke:#059669,color:#fff
    classDef runtime fill:#ef4444,stroke:#dc2626,color:#fff
    classDef db fill:#64748b,stroke:#475569,color:#fff

    class CSV source
    class BRONZE,SILVER,GOLD etl
    class VALIDATE,TRAIN_RISK,TRAIN_SCORE ml
    class PKL_RISK,PKL_SCORE artifact
    class ML_RT,CS_RT runtime
    class DUCKDB db

    %% ===== Subgraph: viền rõ, nền trong suốt =====
    style SOURCE fill:transparent,stroke:#d97706,stroke-width:2px
    style ETL fill:transparent,stroke:#0284c7,stroke-width:3px
    style TRAINING fill:transparent,stroke:#7c3aed,stroke-width:3px
    style ARTIFACTS fill:transparent,stroke:#059669,stroke-width:2px
    style RUNTIME fill:transparent,stroke:#dc2626,stroke-width:2px
```

> **Chú thích ETL & ML:**
> - **Bronze**: Load raw Parquet của Home Credit Credit Risk Model Stability vào DuckDB, giữ nguyên schema gốc.
> - **Silver**: Làm sạch dữ liệu (xử lý null, chuẩn hóa kiểu dữ liệu, loại bỏ outliers) theo SQL transforms.
> - **Gold**: Feature engineering nâng cao (tạo các chỉ số tài chính, aggregation từ bureau/previous applications/CB queries) → bảng `gold.hc_features_v2`.
> - **Training**: 2 model được train: LightGBM v4 cho dự đoán rủi ro vỡ nợ (35 feature, không dùng `credit_score` tự khai báo) và Logistic Regression scorecard (30 feature, FICO-style 300–850).
> - **Runtime**: Backend load model artifacts bằng `joblib` và chạy inference real-time khi khách hàng nộp đơn.
---

## Cấu Trúc Dự Án

```text
Loan_ETL/
├── backend/                              # FastAPI API server
│   ├── main.py                           # Entry point — mount routers, CORS
│   ├── init_db.py                        # Tạo / migrate bảng DB
│   ├── api/
│   │   ├── dependencies.py               # Shared deps: get_current_user, require_role
│   │   └── routers/                      # Route handlers (thin): auth, applications,
│   │                                     #   admin, chat, credit_score, cic
│   ├── services/                         # Business logic layer
│   │   ├── auth_service.py               # JWT authentication + bcrypt
│   │   ├── application_service.py        # CRUD đơn vay, submit workflow (ngưỡng 0.4)
│   │   ├── admin_service.py              # Admin approve/reject đơn
│   │   ├── ml_service.py                 # Load LightGBM model, predict risk
│   │   ├── credit_score_service.py       # Load scorecard, compute FICO + SHAP
│   │   ├── chat_service.py               # Điều phối RAG chatbot & flow nộp lại
│   │   ├── loan_adjustment_tool.py       # Tìm phương án điều chỉnh hạn mức/kỳ hạn tối ưu
│   │   ├── loan_adjustment_reasoner.py   # Luật mềm xếp hạng phương án điều chỉnh
│   │   ├── loan_suggestion_service.py    # Binary search optimal loan
│   │   ├── model_feature_builder.py      # Map form data → ML features
│   │   ├── cic_service.py                # Tích hợp dữ liệu CIC (credit bureau)
│   │   └── document_service.py           # Upload / manage documents
│   ├── rag/                              # RAG chatbot engine
│   │   ├── chain.py                      # Pipeline: Guardrail→Route→Rewrite→Retrieve→Rerank→LLM→Guardrail
│   │   ├── router.py                     # Phân loại ý định (từ khóa + LLM JSON)
│   │   ├── query_rewriter.py             # Viết lại truy vấn độc lập theo lịch sử
│   │   ├── retriever.py                  # Qdrant Hybrid Search retriever
│   │   ├── reranker.py                   # Cross-Encoder Reranker (fastembed)
│   │   ├── chunking.py                   # Phân mảnh hierarchical (Parent-Child)
│   │   ├── context_builder.py            # Build 4-block user context từ DB
│   │   ├── personalizer.py               # Điều chỉnh giọng điệu theo trạng thái đơn
│   │   ├── guardrails.py                 # Kiểm soát input (injection) & output (data leak)
│   │   ├── memory.py                     # Sliding window + conversation summarization
│   │   ├── prompts.py                    # System prompt template (tiếng Việt)
│   │   ├── ingest.py                     # Nạp docs → chunk → embed → Qdrant
│   │   ├── config.py                     # Cấu hình RAG (model, collection, top-k)
│   │   ├── exceptions.py                 # RAGError → fallback HTTP 503
│   │   ├── eval_runner.py / eval_metrics.py  # Kiểm thử & chấm điểm RAG offline
│   │   └── knowledge/                    # Markdown knowledge base (faq.md, policy.md)
│   ├── models/                           # SQLAlchemy ORM: User, LoanApplication, PersonalInfo, Chat*, CIC
│   ├── schemas/                          # Pydantic v2 request/response contracts
│   ├── core/                             # config.py (env), security.py (JWT), scoring.py
│   ├── db/                               # session.py, init_app.sql
│   ├── scripts/                          # Maintenance: seed, backfill FICO, reset DB
│   └── tests_local/                      # Standalone integration test scripts
│
├── frontend/                             # React 18 + Vite + TailwindCSS
│   └── src/
│       ├── App.jsx / main.jsx            # Router (public/customer/admin) & entrypoint
│       ├── pages/
│       │   ├── customer/                 # Landing, Login, Register, Dashboard, Apply,
│       │   │                             #   Chat, History, ApplicationDetail, SubmitInfo
│       │   └── admin/                    # Dashboard, PendingList, ApplicationList,
│       │                                 #   ApplicationDetail, PersonalInfoView, Profile
│       ├── components/                   # common/ · customer/ · admin/ (PascalCase)
│       ├── services/                     # Axios API clients (api.js + JWT interceptor)
│       ├── store/                        # Zustand state: authStore
│       ├── hooks/ · utils/               # Custom React hooks & helpers
│       └── mocks/                        # Mock handlers cho `npm run mock`
│
├── machinelearning/                      # ETL + ML training (offline)
│   ├── etl/                              # load_bronze, etl_silver, etl_gold, pipeline
│   ├── database/                         # SQL transforms: silver + gold
│   ├── ml/                               # retrain_customer_model, train_scorecard, validate_data
│   │   ├── models/                       # Exported .pkl artifacts
│   │   └── tests/                        # ML unit tests
│   ├── data/                             # DuckDB + raw Parquet (Home Credit Stability)
│   ├── config/                           # etl_db.env
│   ├── notebooks/                        # EDA / training notebooks
│   └── utils/                            # Shared DB connection helper
│
├── docs/                                 # Project documentation
│   ├── overall/                          # Architecture notes, admin guide
│   ├── ml/ · rag/                        # ML & RAG design docs, benchmark notes
│   ├── data_dictionary/                  # Feature definitions, Kaggle overview
│   └── superpowers/                      # plans/ + specs/ (lịch sử thiết kế tính năng)
│
├── RAG_eval/                             # Bộ dữ liệu & kết quả benchmark RAG
├── qdrant_storage/                       # Docker-mounted Qdrant persistent data
├── export_eda_views.py                   # Export EDA views từ DuckDB
├── requirements.txt                      # Aggregate Python dependencies (full-stack)
├── AGENTS.md / CLAUDE.md                 # Repository conventions cho AI agents
└── README.md
```

## Khởi Chạy Nhanh

> Chạy các lệnh Python từ thư mục gốc project (`Loan_ETL/`) trừ khi có ghi chú khác.

### 1. Tạo môi trường Python

```bash
python -m venv .venv
source .venv/bin/activate
```

Nếu muốn cài tất cả Python dependencies cho cả backend và ML/ETL:

```bash
pip install -r requirements.txt
```

Nếu chỉ làm một phần, cài riêng theo layer:

```bash
pip install -r backend/requirements.txt
pip install -r machinelearning/requirements.txt
```

### 2. Backend FastAPI

```bash
pip install -r backend/requirements.txt

python -m venv .venv
source .venv/bin/activate
cd backend
python init_db.py
uvicorn main:app --reload
```

Swagger UI: http://localhost:8000/docs

Backend dùng model artifacts tại:

- `machinelearning/ml/models/customer_risk_model.pkl`
- `machinelearning/ml/models/scorecard_model.pkl`

Model hiện tại:

- `customer_lgbm_v4_stability`: 35 feature từ `gold.hc_features_v2`, ROC-AUC gần nhất `0.8065`.
- `scorecard_model.pkl`: 30 feature, FICO-style 300–850, ROC-AUC gần nhất `0.7367`.

### 3. Frontend React

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run mock     # chạy UI với mock API
npm run build    # production build
```

### 4. RAG Chatbot + Qdrant

Backend chat dùng OpenRouter cho LLM/embeddings và Qdrant local cho vector search.
Khi chạy local bằng Docker, `QDRANT_API_KEY` để trống.

```bash
# Chạy từ root project
pkexec systemctl start docker   # hoặc: sudo systemctl start docker

pkexec docker run -d \
  --name creditintel-qdrant \
  -p 6333:6333 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant

curl http://127.0.0.1:6333/
```

Nếu user của bạn đã thuộc group `docker`, có thể bỏ `pkexec`. Nếu chưa, thêm quyền rồi logout/login lại:

```bash
sudo usermod -aG docker "$USER"
```

Nạp tài liệu vào collection `creditintel-kb`:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.ingest
curl http://127.0.0.1:6333/collections
```

Env cần có trong `backend/.env`:

```env
OPENROUTER_API_KEY=sk-or-...
RAG_LLM_MODEL=google/gemini-2.5-flash
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=creditintel-kb
```

### 5. ETL Pipeline

Đặt dataset Home Credit Credit Risk Model Stability dạng Parquet vào:

`machinelearning/data/home-credit-credit-risk-model-stability/parquet_files/train/`

Các file tối thiểu mà loader đang dùng:

- `train_base.parquet`
- `train_static_0_*.parquet`
- `train_static_cb_0.parquet`
- `train_person_1.parquet`
- `train_credit_bureau_a_1_*.parquet`
- `train_applprev_1_*.parquet`

Chạy toàn bộ pipeline:

```bash
pip install -r machinelearning/requirements.txt
python -m machinelearning.etl.pipeline
```

Hoặc chạy từng bước:

```bash
python -m machinelearning.etl.load_bronze
python -m machinelearning.etl.etl_silver
python -m machinelearning.etl.etl_gold
```

### 6. Machine Learning

```bash
python -m machinelearning.ml.validate_data
python -m machinelearning.ml.retrain_customer_model
python -m machinelearning.ml.train_scorecard
```

Kiểm tra contract artifact:

```bash
python -m machinelearning.ml.check_customer_model_contract
```

Notebook EDA/evaluation chính:

```bash
jupyter lab machinelearning/notebooks/home_credit_eda.ipynb
```

## Công Nghệ Sử Dụng

| Layer | Công nghệ |
|---|---|
| Backend API | Python, FastAPI, SQLAlchemy 2.0, Pydantic v2, JWT, bcrypt |
| Frontend | React 18, Vite, TailwindCSS, Axios, Zustand, React Router |
| Database | PostgreSQL/Supabase, DuckDB local cho ETL |
| ETL | Python, pandas, SQLAlchemy, DuckDB |
| ML | LightGBM, scikit-learn, pandas, joblib |
| RAG Chatbot | LangChain, OpenRouter (Gemini 2.5 Flash), Qdrant Vector DB |
| DevOps | Docker (Qdrant), Vite dev server, Uvicorn |

## Tài Liệu

| Tài liệu | Đường dẫn |
|---|---|
| Backend Architecture | [`backend/README.md`](backend/README.md) |
| Frontend Guide | [`frontend/README.md`](frontend/README.md) |
| Overall Documentation | [`docs/overall/`](docs/overall/) |
| ML Documentation | [`docs/ml/`](docs/ml/) |
| RAG Documentation | [`docs/rag/`](docs/rag/) |
| Admin Guide | [`docs/overall/ADMIN_GUIDE.md`](docs/overall/ADMIN_GUIDE.md) |

## Phạm Vi Theo Nhóm

| Vai trò | Phạm vi |
|---|---|
| Backend Developer | `backend/` - API, auth, admin, DB, RAG integration |
| Frontend Developer | `frontend/` - React UI, pages, components, API client |
| ML Engineer | `machinelearning/ml/` - training scripts, artifacts, model contracts |
| Data Engineer | `machinelearning/etl/`, `machinelearning/database/`, `machinelearning/data/` |
| AI/RAG Engineer | `backend/rag/`, `backend/services/chat_service.py` |

## Ghi Chú Cấu Hình

- Secrets đặt trong `backend/.env`, không commit lên Git.
- ETL config đặt tại `machinelearning/config/etl_db.env`.
- `requirements.txt` ở root chỉ dùng để cài full-stack Python; khi làm riêng backend hoặc ML, ưu tiên file requirements của từng thư mục.
