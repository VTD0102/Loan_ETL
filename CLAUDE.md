# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CreditIntel** is a full-stack loan management and risk assessment system: a FastAPI backend, React frontend, PostgreSQL (Supabase) for transactional data, a LightGBM risk model + LR scorecard model trained offline, a LangChain RAG chatbot (Qdrant + OpenRouter), and a Bronze→Silver→Gold ETL pipeline on DuckDB over the Home Credit Credit Risk Model Stability dataset.

## Commands

All Python commands run from the repo root with the project's virtualenv activated:

```bash
source .venv/bin/activate
```

### Backend (FastAPI)
```bash
pip install -r backend/requirements.txt
cd backend
python init_db.py                  # create/migrate DB tables
uvicorn main:app --reload          # http://localhost:8000 — Swagger at /docs
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (requires running backend)
npm run mock     # full app using mocked API — no backend needed
npm run build
npm run preview
```

### ETL Pipeline (from repo root)
```bash
pip install -r machinelearning/requirements.txt
python -m machinelearning.etl.pipeline        # bronze → silver → gold
# or step-by-step:
python -m machinelearning.etl.load_bronze
python -m machinelearning.etl.etl_silver
python -m machinelearning.etl.etl_gold
```

ETL reads raw Parquet from `machinelearning/data/home-credit-credit-risk-model-stability/parquet_files/train/` and writes the DuckDB database under `machinelearning/data/`.

### Machine Learning (from repo root)
```bash
python -m machinelearning.ml.validate_data
python -m machinelearning.ml.retrain_customer_model      # LightGBM risk model
python -m machinelearning.ml.train_scorecard             # LR scorecard
python -m machinelearning.ml.check_customer_model_contract  # verify pkl contract
```

Artifacts land in `machinelearning/ml/models/`:
- `customer_risk_model.pkl` — LightGBM v4 (`customer_lgbm_v4_stability`), 35 features from `gold.hc_features_v2`, loaded by `backend/services/ml_service.py`.
- `scorecard_model.pkl` — LR scorecard, 30 features, FICO-style 300–850, loaded by `backend/services/credit_score_service.py`.

### Backend Tests
Run from `backend/` so imports resolve:
```bash
cd backend
python tests_local/test_db.py
python tests_local/test_ml.py
python tests_local/test_ml_service_contract.py
python tests_local/test_router.py
# any tests_local/test_*.py — they are standalone scripts, not pytest suites
```

## Architecture

### Request Flow
1. **Frontend** (React/Zustand) → HTTPS with JWT → **Backend API** (FastAPI)
2. **Backend** → SQL → **PostgreSQL** (Supabase)
3. **Backend** services load `customer_risk_model.pkl` and `scorecard_model.pkl` via `joblib` at startup → real-time inference on loan submission and credit score lookup
4. **Backend `chat_service`** → LangChain RAG → **Qdrant** vector store + **OpenRouter** LLM (Gemini 2.5 Flash)

### Backend Layer Structure (`backend/`)
- `api/routers/` — thin route handlers: `auth`, `applications`, `admin`, `chat`, `credit_score`
- `services/` — all business logic (`auth_service`, `application_service`, `admin_service`, `ml_service`, `credit_score_service`, `chat_service`, `model_feature_builder`, `loan_suggestion_service`, `document_service`)
- `models/` — SQLAlchemy ORM tables (`User`, `LoanApplication`, `PersonalInfo`, `ChatSession`, `ChatMessage`)
- `schemas/` — Pydantic V2 request/response contracts (kept separate from `models/` even when shapes look similar)
- `core/` — `config.py` (settings from `.env`), `security.py` (JWT + bcrypt)
- `db/` — `session.py` (engine, `get_db` dependency)
- `rag/` — `chain.py`, `retriever.py` (Qdrant), `context_builder.py`, `memory.py`, `prompts.py`, `guardrails.py`, `router.py`, `personalizer.py`, `ingest.py`, `knowledge/`

### Loan Application State Machine
`DRAFT` → on submit, `ml_service.predict()` is called. If default probability > **0.4**, status is set to **`AUTO_REJECTED`**; otherwise **`PENDING_REVIEW`**. Admin actions transition `PENDING_REVIEW` → `AWAITING_INFO` (request more info from customer) or → `REJECTED`. Customer responds to AWAITING_INFO to reach `APPROVED`. The 0.4 threshold lives in `backend/services/application_service.py`; risk-level cutoffs come from `thresholds` inside the model artifact.

### RAG Chat Flow
`POST /chat` → rate-limit check (≤20 msg/min) → ensure ML prediction exists for the application → `context_builder` assembles 4-block context (form, ML, advisory, data quality) → `memory.py` loads last ~10 turns from PostgreSQL → `retriever.py` vector-searches Qdrant collection `creditintel-kb` (top-k≈4) → `chain.py` calls OpenRouter → transcript saved to `chat_messages`.

### Frontend Structure (`frontend/src/`)
- `pages/customer/` — Landing, Login, Register, Dashboard, Apply, Chat, History, ApplicationDetail
- `pages/admin/` — Dashboard, PendingList, ApplicationList, ApplicationDetail, PersonalInfoView
- `components/` — shared UI (PascalCase, e.g. `ApplicationCard/index.jsx`); includes `ProtectedRoute`, `AdminLayout`, `Navbar`
- `services/api.js` — single Axios instance with JWT interceptor; all HTTP calls go here
- `store/authStore.js` — Zustand auth state (token, role)
- `mocks/` — handlers for `npm run mock` mode

## Key Conventions

**Backend:**
- Always use **absolute imports** inside `backend/`: `from core.config import settings`, not relative paths — required for `uvicorn` to resolve modules correctly.
- API handlers stay thin; business logic belongs in `services/`.
- `models/` defines DB schema; `schemas/` defines API contracts — keep them separate even when they look similar.
- UUIDs (not integer IDs) for `users` and `loan_applications`.
- RAG dependencies (LangChain, Qdrant, OpenAI SDK) are hard imports at module load — install `backend/requirements.txt` before starting the server. On upstream failure, `chat_service` catches `rag.exceptions.RAGError` and returns HTTP 503 with the assistant placeholder row already persisted (`error=True`).
- Match existing **Vietnamese error messages** in `services/` — don't silently switch to English.

**Frontend:**
- Use `npm run mock` to develop UI features without a running backend.
- Add new API calls to `services/api.js` — never call `axios` directly in components.
- Use existing Tailwind utilities and shared components before introducing new patterns.

**Commits:** Use prefixes `feat:`, `fix:`, `refactor:`, `update:`, `merge:` with a concise scope, e.g. `feat: add admin risk filter`.

## Environment Variables

`backend/.env` (required, never commit):
```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD     # Supabase PostgreSQL
SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES  # JWT
OPENROUTER_API_KEY                                  # OpenRouter
RAG_LLM_MODEL=google/gemini-2.5-flash
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                                     # empty for local Docker
QDRANT_COLLECTION=creditintel-kb
```

`frontend/.env`:
```
VITE_API_URL=http://localhost:8000
```

ETL/DB config lives in `machinelearning/config/etl_db.env`.

## Qdrant (local, for RAG)

```bash
docker run -d --name creditintel-qdrant \
  -p 6333:6333 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant

# Ingest knowledge base into Qdrant
cd backend

# Dry run — list docs + chunks, no writes
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --dry-run

# Incremental upsert (default — keeps existing collection)
PYTHONPATH=. ../.venv/bin/python -m rag.ingest

# Recreate collection (destructive — deletes existing data)
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --recreate
```

> **Note:** Sau khi nâng cấp chunking (V1+), bạn PHẢI chạy `--recreate` một lần để xoá chunks fixed-size cũ. Chạy không có `--recreate` sẽ trộn parent-child mới và fixed-size cũ trong cùng collection và làm hỏng parent expansion ở query time.

## Key Documentation
- `README.md` — full system diagrams and quickstart (Vietnamese)
- `backend/BACKEND_API_SPEC.md` — endpoint reference
- `backend/README.md` — backend architecture
- `frontend/README.md`, `frontend/RULES.md`, `frontend/CUSTOMER.md` — frontend specifics
- `docs/overall/ADMIN_GUIDE.md` — admin dashboard usage
- `docs/ml/`, `docs/rag/` — ML and RAG design notes
- `AGENTS.md` — repository conventions (overlaps with this file)

## Coding Guidelines

### Think Before Coding
- State assumptions explicitly before touching backend state machine logic, ML thresholds, or ETL transforms — these have downstream effects.
- If a request can be interpreted multiple ways (e.g., "update the risk model" could mean retrain, swap threshold, or change features), ask rather than pick silently.
- If `backend/BACKEND_API_SPEC.md` conflicts with the code, surface the discrepancy before resolving it.

### Simplicity First
- A new endpoint belongs in an existing router + service pair unless the domain is genuinely new. Don't create new files for single functions.
- Don't add Pydantic fields, DB columns, or ML features speculatively. Every addition must be tied to a concrete, requested behaviour.
- The ETL pipeline is already three layers (bronze→silver→gold); don't introduce a fourth transform stage for a one-off data fix — extend the existing SQL in `machinelearning/database/`.

### Surgical Changes
- When editing a service, don't reformat unrelated routers or schemas in the same file.
- If your change makes an import or schema field unused, remove it. Don't remove pre-existing dead code unless asked.

### Goal-Driven Execution
Before starting a multi-step task, state the plan and success criteria:
```
1. [change] → verify: [tests_local/ script passes, or curl to /docs confirms endpoint]
2. [change] → verify: [npm run build succeeds, flow works in npm run mock]
```
- For bug fixes: reproduce the failure in `backend/tests_local/` first, then fix.
- For new API endpoints: confirm the contract in `BACKEND_API_SPEC.md` before writing the router.
