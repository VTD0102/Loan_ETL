# TÀI LIỆU TỔNG QUAN HỆ THỐNG CREDITINTEL (OVERALL DOCUMENTATION)

> *Cập nhật lần cuối: 2026-05-13 — phản ánh hiện trạng thực tế của codebase.*

---

## 1. Giới thiệu dự án (Project Overview)

**CreditIntel** là hệ thống toàn diện kết hợp **Data Engineering**, **Machine Learning** và **Web Application** phục vụ quản lý rủi ro danh mục cho vay và dự đoán rủi ro vỡ nợ tín dụng.

**Hai nguồn dữ liệu song song:**
- **Prosper Loan Dataset** (~113K khoản vay, 2005-2014): xây dựng luồng Core DB (PostgreSQL/Supabase).
- **Home Credit Default Risk dataset** (Kaggle): dùng để train mô hình rủi ro `customer_risk_model.pkl` (LightGBM) và LR Scorecard `scorecard_model.pkl` (Logistic Regression).

**Mục tiêu cốt lõi:**
- Chuẩn hóa quy trình xử lý dữ liệu từ thô đến phân tích (Data Lakehouse).
- Cung cấp mô hình ML đánh giá rủi ro và tự động hóa quyết định cho vay.
- Giao diện Web đầy đủ cho **Customer** (đăng ký, nộp đơn, chat) và **Admin** (quản lý, xét duyệt, dashboard).
- Tích hợp **RAG Chatbot** (LangChain + Pinecone) hỗ trợ tư vấn tài chính cá nhân hóa.

---

## 2. Kiến trúc hệ thống (System Architecture)

Hệ thống gồm 4 thành phần chính:

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React 18 + Vite + Tailwind CSS)              │
│  Customer Portal  |  Admin Portal                       │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API (HTTP/JSON)
┌───────────────────────▼─────────────────────────────────┐
│  Backend (FastAPI)                                       │
│  /auth  /applications  /admin  /chat  /credit-score     │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
┌──────▼───┐  ┌───────▼──────┐  ┌───▼──────────────────┐
│PostgreSQL│  │ ML Models    │  │ RAG (LangChain +     │
│(Supabase)│  │(pkl files)   │  │  Pinecone)           │
└──────────┘  └──────────────┘  └──────────────────────┘
       ▲
┌──────┴───────────────────────────────────────────────────┐
│  ETL Pipeline (DuckDB local → PostgreSQL)                │
│  Home Credit: Bronze → Silver → Gold                     │
│  Prosper: database/ SQL scripts                          │
└──────────────────────────────────────────────────────────┘
```

### 2.1. Data Pipeline — Hai nhánh song song

#### Nhánh A: Home Credit (ETL Python + DuckDB)
Xử lý dataset Kaggle Home Credit thông qua pipeline Python thuần:
- **Bronze** (`bronze.home_credit_raw`, `bronze.previous_application_raw`, `bronze.bureau_raw`): Load CSV thô vào DuckDB local.
- **Silver** (`silver.home_credit_cleansed`): Làm sạch, xử lý missing, tính `is_default`.
- **Gold** (`gold.hc_features_v1`): Feature engineering đầy đủ (~25 features) phục vụ train LR Scorecard.

#### Nhánh B: Prosper (SQL Scripts + PostgreSQL)
Xử lý Prosper Loan Data thông qua script SQL chạy trên Supabase:
- **Bronze** (`bronze.raw_loans`): Dữ liệu thô từ CSV.
- **Silver** (`silver.prosper_loans_cleansed`): Làm sạch, chuẩn hóa, tạo `is_default`.
- **Core** (`core.*`): Schema chuẩn hóa nghiệp vụ: `loans`, `borrowers`, `credit_profiles`, `risk_assessment`, `dim_*`.
- **Gold** (`gold.loan_features_v1`): Feature engineering từ dữ liệu Prosper cũ.

### 2.2. Backend API (FastAPI)

- **Entry point:** `backend/main.py` — FastAPI app với CORS middleware.
- **Routers đang active:** `/auth`, `/applications`, `/admin`, `/chat`, `/credit-score`.
- **Router tạm disabled:** `/predict` (comment trong code, logic đã tích hợp vào `application_service`).
- **ORM:** SQLAlchemy 2.x tương tác PostgreSQL (Supabase).
- **Auth:** JWT (python-jose) + Bcrypt (passlib).
- **Rate limiting:** slowapi.

### 2.3. Machine Learning — Hai Model Song Song

| Model | File | Thuật toán | Mục đích |
|---|---|---|---|
| Customer Risk Model | `ml/models/customer_risk_model.pkl` | LightGBM | Dự đoán P(default) để xét duyệt đơn |
| Scorecard Model | `ml/models/scorecard_model.pkl` | Logistic Regression (FICO PDO) | Tính điểm tín dụng 300–850 cho khách hàng |

**Thresholds chung:** Low < 0.20 ≤ Medium ≤ 0.40 < High

### 2.4. RAG Chatbot (LangChain + Pinecone)

- Nhúng tài liệu từ `backend/rag/knowledge/` lên Pinecone index.
- `ConversationalRetrievalChain` dùng OpenAI/OpenRouter LLM.
- Lịch sử chat lưu vào PostgreSQL (`chat_messages`, `chat_sessions`).
- Context builder tổng hợp thông tin đơn vay hiện tại của user vào prompt.

### 2.5. Frontend Web App (React 18 + Vite + Tailwind CSS)

- Phân tách rõ **Customer Portal** và **Admin Portal** với `ProtectedRoute`.
- State management: Zustand (`authStore.js`).
- API client: axios wrapper tại `frontend/src/services/`.
- Mock mode: `npm run mock` dùng `mockHandlers.js` + `mockData.js`.

---

## 3. Cấu trúc thư mục dự án (Directory Structure)

```
Loan_ETL/
├── backend/                    # FastAPI application
│   ├── main.py                 # App entry point, router registration
│   ├── init_db.py              # Khởi tạo bảng PostgreSQL
│   ├── requirements.txt
│   ├── api/
│   │   ├── dependencies.py     # get_current_user, get_db
│   │   └── routers/
│   │       ├── auth.py         # POST /auth/register, /auth/login
│   │       ├── applications.py # POST /applications/submit, GET list/detail
│   │       ├── admin.py        # GET /admin/dashboard, pending, approve/reject
│   │       ├── chat.py         # POST /chat/send, GET /chat/history
│   │       ├── credit_score.py # GET /credit-score/me
│   │       └── predict.py      # (disabled) POST /predict
│   ├── core/
│   │   ├── config.py           # Settings từ .env (Pydantic Settings)
│   │   ├── security.py         # JWT encode/decode
│   │   └── scoring.py          # pd_to_credit_score(), score_to_band()
│   ├── db/
│   │   └── session.py          # SQLAlchemy engine & SessionLocal
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py             # User table
│   │   ├── application.py      # LoanApplication table
│   │   ├── personal_info.py    # PersonalInfo table
│   │   └── chat.py             # ChatSession, ChatMessage tables
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── user.py
│   │   ├── application.py
│   │   ├── personal_info.py
│   │   ├── credit_score.py
│   │   └── chat.py
│   ├── services/               # Business logic layer
│   │   ├── auth_service.py
│   │   ├── application_service.py
│   │   ├── admin_service.py
│   │   ├── chat_service.py
│   │   ├── ml_service.py       # Wrapper gọi model inference (load pkl files)
│   │   └── credit_score_service.py  # FICO scorecard inference + SHAP
│   ├── rag/                    # RAG Chatbot module
│   │   ├── ingest.py           # Embed docs lên Pinecone
│   │   ├── chain.py            # ConversationalRetrievalChain
│   │   ├── retriever.py        # Pinecone retriever setup
│   │   ├── memory.py           # Chat history management
│   │   ├── context_builder.py  # Build user context từ DB
│   │   ├── prompts.py          # System/user prompt templates
│   │   ├── config.py           # RAG config (model, index name...)
│   │   └── knowledge/          # Tài liệu embed (markdown files)
│   └── tests_local/            # Local integration/smoke tests
│       ├── test_db.py
│       ├── test_ml.py
│       ├── test_task_1_3.py through test_task_1_11.py
│       └── test_task_5_3.py
│
├── frontend/                   # React 18 + Vite app
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx             # Router config (React Router v6)
│       ├── main.jsx
│       ├── index.css
│       ├── store/
│       │   └── authStore.js    # Zustand auth state
│       ├── services/           # API client helpers (axios)
│       │   ├── api.js          # Axios instance + interceptors
│       │   ├── auth.js
│       │   ├── applications.js
│       │   ├── admin.js
│       │   └── chat.js
│       ├── mocks/              # MSW mock handlers
│       │   ├── mockHandlers.js
│       │   └── mockData.js
│       ├── components/
│       │   ├── ProtectedRoute.jsx
│       │   ├── common/         # Badge, LoadingSpinner, Modal, Navbar
│       │   ├── customer/       # ApplicationCard, ApplicationTimeline,
│       │   │                   # ChatMessage, LoanStatusCard, RiskGauge
│       │   └── admin/          # AdminLayout, ApplicationTable, ApplicationsTable,
│       │                       # ApproveRejectButtons, FilterBar, MLResultsDisplay,
│       │                       # ReviewModal, RiskChart, StatsCard, SummaryCard
│       └── pages/
│           ├── customer/       # Landing, Login, Register, Apply, Dashboard,
│           │                   # ApplicationDetail, Chat, SubmitInfo
│           └── admin/          # Login, Dashboard, PendingList,
│                               # ApplicationList, ApplicationDetail, PersonalInfoView
│
├── etl/                        # Home Credit ETL pipeline (DuckDB)
│   ├── __init__.py
│   ├── pipeline.py             # Orchestrator: bronze → silver → gold
│   ├── load_bronze.py          # Load CSV → bronze.home_credit_raw + prev + bureau
│   ├── etl_silver.py           # Bronze → silver.home_credit_cleansed
│   └── etl_gold.py             # Silver → gold.hc_features_v1
│
├── ml/                         # Machine Learning scripts
│   ├── __init__.py
│   ├── ML_INTEGRATION_CHECKLIST.md # Checklist tích hợp ML
│   ├── retrain_customer_model.py   # Train LightGBM trên Home Credit features
│   ├── train_scorecard.py          # Train LR Scorecard trên HC features (~25)
│   ├── validate_data.py            # Kiểm tra data trước khi train
│   ├── models/
│   │   ├── customer_risk_model.pkl # LightGBM artifact (27MB)
│   │   └── scorecard_model.pkl     # LR Scorecard artifact (6KB)
│   └── requirements.txt            # ML dependencies
│
├── config/
│   └── etl_db.env              # Cấu hình đường dẫn cho ETL DuckDB
│
├── data/
│   ├── etl.duckdb              # Database DuckDB local cho Home Credit
│   └── home_credit/            # Chứa các file CSV của Home Credit (application_train.csv, previous_application.csv, bureau.csv, ...)
│
├── database/                   # SQL scripts cho Prosper/PostgreSQL
│   ├── init_database.sql       # Tạo Bronze schema
│   ├── init_core.sql           # Tạo Core schema & tables
│   ├── transform_silver.sql    # Bronze → Silver (Prosper)
│   ├── transform_core.sql      # Silver → Core (Prosper)
│   ├── transform_gold.sql      # Core → Gold (Prosper, loan_features_v1)
│   ├── transform_silver_homecredit.sql  # Silver HC (PostgreSQL version)
│   └── transform_gold_homecredit.sql    # Gold HC (hc_features_v1 PostgreSQL)
│
├── notebooks/
│   └── home_credit_eda.ipynb   # EDA notebook
│
├── docs/
│   ├── ADMIN_GUIDE.md
│   ├── 01_muc_tieu_project.html → 09_van_de_can_giai_quyet.html
│   ├── data_dictionary/
│   ├── ml_md/
│   ├── overall/                # File tài liệu tổng quan (thư mục này)
│   ├── superpowers/
│   └── task/
│
├── utils/
│   └── db_connection.py        # get_engine(), load_config(), _ETL_ENV_FILE
│
├── AGENTS.md                   # Project coding guidelines
├── AdminRules.md               # Quy tắc nghiệp vụ Admin
├── CLAUDE.md                   # Claude agent instructions
└── README.md
```

---

## 4. Các Module Cốt Lõi & Chức Năng

### 4.1. ETL Pipeline — Home Credit (DuckDB)

| Script | Input | Output | Mô tả |
|---|---|---|---|
| `etl/load_bronze.py` | CSV files (Kaggle `data/home_credit/`) | `bronze.home_credit_raw`, `bronze.previous_application_raw`, `bronze.bureau_raw` | Load dữ liệu thô, chọn lọc cột cần thiết |
| `etl/etl_silver.py` | bronze tables | `silver.home_credit_cleansed` | Làm sạch, tính `is_default`, xử lý missing |
| `etl/etl_gold.py` | silver table | `gold.hc_features_v1` | Feature engineering ~25 features cho Scorecard |
| `etl/pipeline.py` | — | — | Orchestrator chạy load_bronze→etl_silver→etl_gold tuần tự |

**Chạy pipeline:**
```bash
python -m etl.pipeline
# Hoặc từng bước:
python -m etl.load_bronze
python -m etl.etl_silver
python -m etl.etl_gold
```

### 4.2. Machine Learning

#### Model 1: Customer Risk Model (LightGBM)
- **Train:** `ml/retrain_customer_model.py` — Train trên dữ liệu Home Credit (`gold.hc_features_v1`), lưu vào `ml/models/customer_risk_model.pkl`.
- **Inference:** `backend/services/ml_service.py::predict(payload: ApplicationCreate)` — Nhận input từ form, kết hợp với các feature khác từ schema, load pkl → prediction dict.
- **Input features (từ ApplicationCreate schema):**

| Feature | Type | Mô tả |
|---|---|---|
| `monthly_income` | float | Thu nhập hàng tháng (USD) |
| `loan_amount` | float | Số tiền muốn vay (USD) |
| `term` | int | Kỳ hạn: 12, 36 hoặc 60 tháng |
| `employment_status` | str | Employed / Self-employed / Retired / Not employed / Other |
| `dti` | float | Debt-to-income ratio |
| `is_homeowner` | bool | Sở hữu nhà |
| `listing_category` | int | Mục đích vay (0–20) |
| `credit_score` | float | Điểm tín dụng tự khai (300–850) |

- **Output dict:**

| Field | Mô tả |
|---|---|
| `probability_of_default` | Xác suất vỡ nợ (0.0–1.0) |
| `risk_level` | Low / Medium / High |
| `risk_score_internal` | Điểm nội bộ 0–100 (= (1 - PD) × 100) |
| `auto_decision` | AUTO_REJECTED hoặc PENDING_REVIEW (nếu P(default) > 0.4 → AUTO_REJECTED) |
| `recommended_amount` | Khuyến nghị số tiền vay |
| `recommended_term` | Khuyến nghị kỳ hạn |

#### Model 2: LR Scorecard (FICO-style)
- **Train:** `ml/train_scorecard.py` — Logistic Regression trên `gold.hc_features_v1` (~25 features).
- **FICO PDO params:** `base_score=600`, `base_odds_good=50`, `PDO=20`.
- **Output score:** 300–850. Bands: Poor (<580) / Fair (580–669) / Good (670–739) / Excellent (≥740).
- **Inference:** `backend/services/credit_score_service.py::get_credit_score()` — Load `ml/models/scorecard_model.pkl` + SHAP.
- **SHAP:** Dùng `LinearExplainer` để trả về top 3 factors ảnh hưởng điểm.

### 4.3. Backend Services

| Service | Chức năng chính |
|---|---|
| `auth_service.py` | Đăng ký, đăng nhập, hash/verify password |
| `application_service.py` | Nộp đơn (gọi ML), lấy danh sách, nộp thông tin định danh |
| `admin_service.py` | Dashboard stats, danh sách pending, approve/reject |
| `ml_service.py` | Load model pkl, predict P(default), fallback mock nếu pkl lỗi |
| `chat_service.py` | Lưu/load lịch sử chat, gọi RAG chain |
| `credit_score_service.py` | Tính FICO score từ scorecard + SHAP top factors |

### 4.4. Luồng Trạng Thái Đơn Vay (Application State Machine)

```
[Customer submit form]
        │
        ▼
[ML predict P(default)]
        │
   P > 0.4 ──────────► AUTO_REJECTED
        │
   P ≤ 0.4
        │
        ▼
  PENDING_REVIEW
        │
   [Admin review]
        ├── Reject ──► ADMIN_REJECTED
        │
        └── Approve ► AWAITING_INFO
                            │
                   [Customer nộp CCCD, SĐT...]
                            │
                            ▼
                      INFO_SUBMITTED
```

### 4.5. RAG Chatbot

| Module | Chức năng |
|---|---|
| `rag/ingest.py` | Embed tài liệu markdown → Pinecone index |
| `rag/chain.py` | ConversationalRetrievalChain setup |
| `rag/retriever.py` | Kết nối Pinecone retriever |
| `rag/memory.py` | Quản lý lịch sử hội thoại |
| `rag/context_builder.py` | Tổng hợp context từ đơn vay hiện tại của user |
| `rag/prompts.py` | System prompt, user prompt templates |

---

## 5. Tech Stack & Libraries

| Category | Technologies |
|---|---|
| **Language** | Python 3.10+, JavaScript (ES2022) |
| **Backend** | FastAPI ≥0.115, Uvicorn, Pydantic v2, python-jose, passlib, slowapi |
| **Database** | PostgreSQL (Supabase), SQLAlchemy 2.x, psycopg2-binary |
| **ETL (HC)** | DuckDB, pandas, duckdb Python client |
| **ML** | scikit-learn ≥1.4, LightGBM ≥4.6, numpy, pandas, joblib, shap |
| **RAG** | LangChain ≥0.3, langchain-openai, langchain-pinecone, pinecone ≥6.0 |
| **Frontend** | React 18, Vite, Tailwind CSS, React Router v6, Zustand, Axios |
| **Dev Tools** | python-dotenv, PyYAML, kaggle CLI, Git |

---

## 6. Cấu hình & Biến môi trường

### Backend (`backend/.env`)
```env
DATABASE_URL=postgresql://...          # Supabase connection string
SECRET_KEY=...                         # JWT signing key
OPENAI_API_KEY=...                     # Hoặc OpenRouter key
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...
```

### ETL (`etl/.env` hoặc file được `_ETL_ENV_FILE` trỏ tới)
```env
etl_db_path=data/etl.duckdb           # Đường dẫn DuckDB file local
```

### Frontend (`frontend/.env.mock`)
```env
VITE_USE_MOCK=true                     # Bật mock API mode
```

---

## 7. Hướng dẫn Chạy & Phát triển

### Backend
```bash
cd backend
pip install -r requirements.txt
python init_db.py          # Tạo bảng PostgreSQL lần đầu
uvicorn main:app --reload  # Dev server: http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # Vite dev server: http://localhost:5173 (real API)
npm run mock     # Dev với mock API (không cần backend)
npm run build    # Production bundle
```

### ETL (Home Credit)
```bash
# Đặt CSV files vào data/home_credit/ (download từ Kaggle)
python -m etl.pipeline     # Chạy toàn bộ bronze→silver→gold
```

### Train ML Models
```bash
# Customer Risk Model (Home Credit - LightGBM)
python -m ml.retrain_customer_model

# LR Scorecard (Home Credit)
python ml/train_scorecard.py

# Validate data trước khi train
python ml/validate_data.py
```

### Tests Backend
```bash
cd backend
python tests_local/test_db.py
python tests_local/test_ml.py
python tests_local/test_task_1_3.py
# ... test_task_1_4.py đến test_task_1_11.py
python tests_local/test_task_5_3.py
```

---

## 8. Hiệu năng Model (Kết quả đánh giá)

### Customer Risk Model (LightGBM — Home Credit data)
- **ROC-AUC:** ~0.75 trên test set.
- **Đặc điểm:** Xử lý class imbalance (tỉ lệ 11:1) bằng `is_unbalance=True`. Top features: `credit_score_midpoint`, `ext_source_3`, `num_bureau_records`, `age_years`.
- **Pipeline:** OrdinalEncoder + LGBMClassifier.

### LR Scorecard (Home Credit data)
- **ROC-AUC:** ~0.73 trên test set.
- **Algorithm:** Logistic Regression (C=0.1) — không dùng class_weight để giữ calibration tự nhiên.
- **FICO PDO:** Score range 300–850, base=600, mean~trung bình của tập test.
- **SHAP:** LinearExplainer cung cấp top-3 factors giải thích điểm cho từng user.

---

## 9. Điểm Khác Biệt So Với Phiên Bản Cũ (PROJECT_OVERVIEW.md)

| Điểm | Phiên bản cũ | Hiện tại |
|---|---|---|
| Frontend | Streamlit | React 18 + Vite + Tailwind |
| ETL engine | pandas + SQLAlchemy (Prosper) | DuckDB (Home Credit) song song với SQL scripts (Prosper) |
| ML Models | 1 model (loan_risk_model.pkl) | 2 models: customer_risk_model.pkl (LightGBM) + scorecard_model.pkl (LR) |
| Credit Score | Không có | FICO-style scorecard (300–850) với SHAP explanation |
| Chatbot | Không có | RAG (LangChain + Pinecone) đầy đủ |
| Dataset | Chỉ Prosper | Prosper + Home Credit Default Risk (Kaggle) |
| API | Không có | FastAPI với 5 routers đang active |

---

*(Tài liệu này là nguồn sự thật duy nhất — "single source of truth" — cho kiến trúc kỹ thuật của toàn bộ dự án CreditIntel)*
