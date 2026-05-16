# CreditIntel - Hệ Thống Quản Lý & Đánh Giá Rủi Ro Khoản Vay

> Dự án môn Hệ Quản Trị CSDL - Nhóm KH086  
> FastAPI Backend + React Frontend + Home Credit ETL + Machine Learning + RAG Chatbot

## Cấu Trúc Dự Án

Repo hiện được chia thành 3 thư mục chính để dễ quản lý:

```text
Loan_ETL/
├── backend/              # FastAPI API, auth, services, DB models, RAG runtime
├── frontend/             # React 18 + Vite + Tailwind customer/admin UI
├── machinelearning/      # ETL, SQL transforms, data, notebooks, ML training
├── docs/                 # Tài liệu dự án
├── AGENTS.md             # Quy ước làm việc trong repo
├── requirements.txt      # Aggregate: backend + machinelearning requirements
└── README.md
```

Chi tiết `machinelearning/`:

```text
machinelearning/
├── requirements.txt              # Dependencies cho ETL + training
├── config/etl_db.env             # Cấu hình DuckDB/Postgres cho ETL
├── data/                         # DuckDB local + Home Credit CSV files
├── database/                     # SQL transforms Bronze -> Silver -> Gold
├── etl/                          # load_bronze, etl_silver, etl_gold, pipeline
├── ml/                           # train LightGBM risk model + LR scorecard
├── notebooks/                    # EDA/training notebooks
└── utils/                        # Shared DB connection utility
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

cd backend
python init_db.py
uvicorn main:app --reload
```

Swagger UI: http://localhost:8000/docs

Backend dùng model artifacts tại:

- `machinelearning/ml/models/customer_risk_model.pkl`
- `machinelearning/ml/models/scorecard_model.pkl`

### 3. Frontend React

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run mock     # chạy UI với mock API
npm run build    # production build
```

### 4. ETL Pipeline

Đặt các file Home Credit CSV vào `machinelearning/data/home_credit/`, ví dụ:

- `application_train.csv`
- `previous_application.csv`
- `bureau.csv`

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

### 5. Machine Learning

```bash
python -m machinelearning.ml.validate_data
python -m machinelearning.ml.retrain_customer_model
python -m machinelearning.ml.train_scorecard
```

Kiểm tra contract artifact:

```bash
python -m machinelearning.ml.check_customer_model_contract
```

## Công Nghệ Sử Dụng

| Layer | Công nghệ |
|---|---|
| Backend API | Python, FastAPI, SQLAlchemy 2.0, Pydantic v2, JWT, bcrypt |
| Frontend | React 18, Vite, TailwindCSS, Axios, Zustand, React Router |
| Database | PostgreSQL/Supabase, DuckDB local cho ETL |
| ETL | Python, pandas, SQLAlchemy, DuckDB |
| ML | LightGBM, scikit-learn, pandas, joblib |
| RAG Chatbot | LangChain, OpenRouter/OpenAI-compatible LLM, Pinecone |

## Tài Liệu

| Tài liệu | Đường dẫn |
|---|---|
| Backend Architecture | [`backend/README.md`](backend/README.md) |
| Frontend Guide | [`frontend/README.md`](frontend/README.md) |
| Data Dictionary | [`docs/data_dictionary/`](docs/data_dictionary/) |
| ML Documentation | [`docs/ml_md/`](docs/ml_md/) |
| Project Overview | [`docs/overall/`](docs/overall/) |
| Admin Guide | [`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md) |

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
