# 🏦 CreditIntel — Hệ Thống Quản Lý & Đánh Giá Rủi Ro Khoản Vay

> Dự án môn **Hệ Quản Trị CSDL** — Nhóm KH086  
> ETL Pipeline + Machine Learning + FastAPI Backend + React Frontend + RAG Chatbot

---

## 📂 Cấu Trúc Dự Án

```
Loan_ETL/
├── backend/          # FastAPI REST API (Auth, CRUD, Admin, Chat)
├── frontend/         # React + Vite + TailwindCSS (Customer & Admin UI)
├── ml/               # Machine Learning (risk retrain, scorecard train, artifacts)
├── etl/              # ETL Pipeline (Bronze → Silver → Core → Gold)
├── database/         # SQL Scripts khởi tạo & transform
├── data/             # Raw dataset (Prosper Loan)
├── docs/             # Tài liệu dự án (Data Dictionary, ML, Planning)
└── venv/             # Python Virtual Environment
```

---

## 🚀 Khởi Chạy Nhanh

### 1. Backend (FastAPI)
> **Lưu ý:** Chạy các lệnh dưới đây từ thư mục gốc của project (`Loan_ETL/`).

```bash
# Khởi tạo virtual environment nếu chưa có
python -m venv .venv
source .venv/bin/activate

# Cài đặt dependencies (file này nằm ở thư mục gốc)
pip install -r requirements.txt

# Chạy Backend
cd backend
python init_db.py              # Khởi tạo bảng DB
uvicorn main:app --reload      # http://localhost:8000
```
📖 Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

### 3. ETL Pipeline
```bash
# Chạy từ root project
source .venv/bin/activate
python -m etl.load_bronze
python -m etl.etl_silver
python -m etl.etl_core
python -m etl.etl_gold
```

### 4. Machine Learning
```bash
python -m ml.retrain_customer_model         # Train LightGBM risk model
python ml/train_scorecard.py                # Train LR scorecard model
```

---

## 🛠️ Công Nghệ Sử Dụng

| Layer | Công nghệ |
|-------|-----------|
| **Backend API** | Python, FastAPI, SQLAlchemy 2.0, Pydantic V2, JWT (python-jose), bcrypt |
| **Frontend** | React 18, Vite, TailwindCSS, Axios, Zustand, React Router v6 |
| **Database** | PostgreSQL (Supabase) |
| **ML** | LightGBM, scikit-learn, pandas, joblib |
| **AI Chatbot** | LangChain, RAG (Retrieval-Augmented Generation) |
| **ETL** | Python, pandas, psycopg2, SQLAlchemy |

---

## 📚 Tài Liệu Chi Tiết

| Tài liệu | Đường dẫn |
|-----------|-----------|
| Backend API Spec | [`backend/BACKEND_API_SPEC.md`](backend/BACKEND_API_SPEC.md) |
| Backend Architecture | [`backend/README.md`](backend/README.md) |
| ML Integration | [`backend/ML_INTEGRATION_CHECKLIST.md`](backend/ML_INTEGRATION_CHECKLIST.md) |
| Admin Guide | [`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md) |
| Data Dictionary | [`docs/data_dictionary/`](docs/data_dictionary/) |
| ML Documentation | [`docs/ml_md/`](docs/ml_md/) |
| Project Planning | [`docs/overall/`](docs/overall/) |
| Frontend Guide | [`frontend/README.md`](frontend/README.md) |

---

## 👥 Phân Công Nhóm

| Vai trò | Phạm vi |
|---------|---------|
| **Backend Developer** | `backend/` — API, Auth, Admin, DB, Chat Integration |
| **Frontend Developer** | `frontend/` — React UI, Components, Pages |
| **ML Engineer** | `ml/` — Model Training, Prediction Engine |
| **Data Engineer** | `etl/`, `database/` — ETL Pipeline, SQL Transforms |
| **AI/RAG Engineer** | `backend/rag/` — LangChain Chatbot |
