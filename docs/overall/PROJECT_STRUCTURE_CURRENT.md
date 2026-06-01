# Cấu trúc thư mục dự án (Directory Structure) - Hiện Trạng Thực Tế

Tài liệu này phản ánh chính xác 100% cấu trúc thư mục hiện tại của hệ thống CreditIntel, dựa trên sự phân chia rành mạch giữa Backend, Frontend, Machine Learning và các thành phần đánh giá.

```text
Loan_ETL/
├── backend/                    # FastAPI application (Logic API chính)
│   ├── main.py                 # App entry point, đăng ký các router
│   ├── init_db.py              # Script khởi tạo các bảng PostgreSQL
│   ├── requirements.txt        # Thư viện cho Backend
│   ├── api/
│   │   ├── dependencies.py     # get_current_user, get_db, get_bureau_db
│   │   └── routers/            # Chứa các endpoint API (auth.py, applications.py, admin.py, credit_score.py, chat.py)
│   ├── core/
│   │   ├── config.py           # Cấu hình biến môi trường từ .env (Pydantic Settings)
│   │   ├── security.py         # JWT encode/decode, mã hóa mật khẩu
│   │   └── scoring.py          # Hàm chuyển đổi pd_to_credit_score(), score_to_band()
│   ├── db/
│   │   └── session.py          # SQLAlchemy engine (Main DB & Bureau DB) & SessionLocal
│   ├── models/                 # SQLAlchemy ORM models (Bảng DB)
│   │   ├── user.py             # Bảng Users
│   │   ├── application.py      # Bảng LoanApplication
│   │   ├── cic.py              # Bảng CICRecord (Lưu tại Bureau DB)
│   │   ├── chat.py             # Bảng ChatSession, ChatMessage
│   │   └── personal_info.py    # Bảng PersonalInfo
│   ├── schemas/                # Pydantic validation (Request/Response schemas)
│   ├── services/               # Logic nghiệp vụ trung tâm
│   │   ├── auth_service.py     # Đăng ký, đăng nhập
│   │   ├── application_service.py # Xử lý đơn vay, kết nối ML predict
│   │   ├── cic_service.py      # Xử lý trích xuất Features từ CIC Bureau
│   │   ├── credit_score_service.py # Cấp điểm FICO dựa trên thẻ điểm LR Scorecard
│   │   ├── ml_service.py       # Wrapper giao tiếp model LightGBM
│   │   ├── admin_service.py    # Thống kê, duyệt đơn
│   │   ├── synthetic_service.py# Trình giả lập dữ liệu vay
│   │   └── chat_service.py     # Xử lý Chatbot RAG
│   ├── scripts/                # Scripts vận hành phụ trợ
│   │   ├── reset_databases.py  # Xóa trắng và khởi tạo lại toàn bộ DB
│   │   └── seed_synthetic.py   # Chạy giả lập hàng loạt dữ liệu mẫu
│   ├── rag/                    # Kiến trúc RAG Chatbot
│   │   ├── ingest.py           # Nhúng (embed) tài liệu lên Pinecone
│   │   ├── chain.py            # ConversationalRetrievalChain
│   │   ├── retriever.py        # Cấu hình Pinecone retriever (hybrid/rerank)
│   │   ├── context_builder.py  # Build context cá nhân hóa theo đơn vay
│   │   └── knowledge/          # Folder chứa tài liệu markdown nhúng
│   └── tests_local/            # Local integration/smoke tests cho backend
│
├── frontend/                   # React 18 + Vite app (Giao diện Web)
│   ├── package.json            # Quản lý dependencies (npm)
│   ├── vite.config.js          # Cấu hình Vite build tool
│   ├── tailwind.config.js      # Cấu hình giao diện CSS Tailwind
│   ├── .env.mock               # Biến môi trường chạy mock API
│   └── src/
│       ├── App.jsx             # Router config (Customer / Admin routes)
│       ├── index.css           # Global style
│       ├── main.jsx            # React root
│       ├── store/              
│       │   └── authStore.js    # Quản lý state đăng nhập (Zustand)
│       ├── services/           # Gọi API backend (axios instance)
│       │   ├── api.js          # Cấu hình interceptor bắt lỗi JWT
│       │   ├── auth.js, applications.js, admin.js, cic.js, chat.js
│       ├── mocks/              # Data ảo (MSW) cho dev offline
│       ├── components/         # Các khối UI tái sử dụng
│       │   ├── common/         # Khối cơ bản (Loading, Navbar, Toast...)
│       │   ├── customer/       # Giao diện dành riêng cho Customer (Form, Chat, RiskGauge)
│       │   ├── admin/          # Giao diện cho Admin (Dashboard, Chart, FilterBar)
│       │   └── ProtectedRoute.jsx
│       └── pages/              # Trang hoàn chỉnh (Page-level)
│           ├── customer/       # Login, Register, Apply, Dashboard, Chat...
│           └── admin/          # Admin Login, PendingList, UserDetail...
│
├── machinelearning/            # Phân hệ Model & ETL (Đổi tên từ etl/ml cũ)
│   ├── requirements.txt        # Dependencies cho phân hệ data/ML
│   ├── config/
│   │   └── etl_db.env          # Config duckdb path
│   ├── etl/                    # Pipeline Data Engineering (DuckDB)
│   │   ├── pipeline.py         # Orchestrator (Bronze -> Silver -> Gold)
│   │   ├── load_bronze.py      # Load raw Kaggle CSV -> Bronze
│   │   ├── etl_silver.py       # Bronze -> Silver (Clean)
│   │   └── etl_gold.py         # Silver -> Gold (Feature Engineering)
│   ├── database/               # SQL transform scripts
│   │   └── transform_*.sql
│   ├── notebooks/              # Jupyter Notebooks nghiên cứu thuật toán (EDA)
│   ├── utils/                  # Tiện ích chung cho ML (DB connect)
│   └── ml/                     # ML Model Training Code
│       ├── retrain_customer_model.py # Script train thuật toán LightGBM rủi ro
│       ├── train_scorecard.py        # Script train Scorecard Logistic Regression
│       ├── validate_data.py          # Script kiểm định đầu vào
│       ├── check_customer_model_contract.py
│       ├── models/                   # Folder lưu trữ Model Weights
│       │   ├── customer_risk_model.pkl # Model duyệt khoản vay (~27MB)
│       │   └── scorecard_model.pkl     # LR Scorecard cấp điểm tín dụng (~6KB)
│       └── tests/                    # Tests luồng ML
│
├── RAG_eval/                   # Benchmark Framework đánh giá RAG
│   ├── rag_evaluation.ipynb    # Notebook so sánh điểm Retriever/Rerank
│   └── (rag_eval_*.json)       # Logs kết quả benchmark của từng kịch bản
│
├── docs/                       # Hệ thống tài liệu dự án
│   ├── overall/                # Tổng quan kiến trúc, Modules, Admin Guide
│   ├── ml/                     # Hướng dẫn ML, metrics, scorecard
│   ├── rag/                    # Sơ đồ và checklist cho Chatbot RAG
│   └── superpowers/            # Kế hoạch & Specs chi tiết của Agent
│
├── CLAUDE.md / AGENTS.md       # Chỉ dẫn và nguyên tắc code cho Agent
├── README.md                   # Hướng dẫn run dự án
├── .gitignore                  # Bỏ qua git (node_modules, .env, .venv, pkl lớn...)
└── requirements.txt            # Root requirements list
```
