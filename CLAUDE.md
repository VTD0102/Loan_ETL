# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CreditIntel** is a full-stack loan management and risk assessment system. It combines a FastAPI backend, React frontend, PostgreSQL database (hosted on Supabase), a LightGBM risk model, an LR scorecard model, a LangChain RAG chatbot (Pinecone + OpenRouter), and a Bronze→Silver→Core→Gold ETL pipeline.

## Commands

### Backend (FastAPI)
```bash
cd backend
source ../venv/bin/activate
pip install -r requirements.txt
python init_db.py              # Create/migrate DB tables
python -m uvicorn main:app --reload      # http://localhost:8000 — Swagger at /docs
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (requires running backend)
npm run mock     # Full app using mocked API responses — no backend needed
npm run build
npm run preview
```

### ETL Pipeline (run from repo root)
```bash
source venv/bin/activate
python -m etl.pipeline        # chạy bronze → silver → gold một lần
# hoặc từng bước:
# python -m etl.load_bronze
# python -m etl.etl_silver
# python -m etl.etl_gold
```

### Machine Learning
```bash
python -m ml.retrain_customer_model
python ml/train_scorecard.py
```

### Backend Tests
```bash
cd backend
python tests_local/test_db.py
python tests_local/test_task_1_3.py
```

## Architecture

### Request Flow
1. **Frontend** (React/Zustand) → HTTP with JWT → **Backend API** (FastAPI)
2. **Backend** → SQL → **PostgreSQL** (Supabase)
3. **Backend** → `customer_risk_model.pkl` loaded via joblib → **ML risk prediction** on loan submission
4. **Backend** → LangChain RAG → **Pinecone** vector store + **OpenRouter** (Gemini Flash 1.5)

### Backend Layer Structure (`backend/`)
- `api/routers/` — thin route handlers (`auth`, `applications`, `admin`, `chat`)
- `services/` — all business logic; routers delegate here
- `models/` — SQLAlchemy ORM table definitions (`User`, `LoanApplication`, `PersonalInfo`, `ChatMessage`)
- `schemas/` — Pydantic V2 request/response contracts (separate from models)
- `core/` — `config.py` (settings from `.env`), `security.py` (JWT + bcrypt)
- `db/` — `session.py` (engine, `get_db` dependency)
- `rag/` — LangChain RAG chain, Pinecone retriever, conversation memory, ingestion script

### Loan Application State Machine
`DRAFT` → `PENDING_REVIEW` (auto-rejected if ML default probability > 0.4) → `AWAITING_INFO` (admin approves) → `APPROVED` / `REJECTED`

### Frontend Structure (`frontend/src/`)
- `pages/` — route-level components (customer: `Apply`, `Dashboard`, `Detail`; admin: `AdminDashboard`, `ApplicationDetail`)
- `components/` — reusable UI (PascalCase, e.g. `ApplicationCard/index.jsx`)
- `services/api.js` — single Axios instance with JWT interceptor; all HTTP calls go here
- `store/` — Zustand stores (`authStore`)
- `mocks/` — MSW-style mock handlers for `npm run mock` mode

## Key Conventions

**Backend:**
- Always use **absolute imports** inside `backend/`: `from core.config import settings`, not relative paths — this is required for `uvicorn` to resolve modules correctly.
- API handlers stay thin; business logic belongs in `services/`.
- `models/` defines DB schema; `schemas/` defines API contracts — keep them separate even when they look similar.
- UUIDs (not integer IDs) for `users` and `loan_applications`.
- RAG imports are lazy (`try/except ImportError`) so the API starts even if LangChain is not installed.

**Frontend:**
- Use `npm run mock` to develop UI features without a running backend.
- Add new API calls to `services/api.js` — never call `axios` directly in components.
- Use existing Tailwind utilities and shared components before introducing new patterns.

**Commits:** Use prefixes `feat:`, `fix:`, `refactor:`, `update:`, `merge:` with a concise scope, e.g. `feat: add admin risk filter`.

## Environment Variables

`backend/.env` (required, never commit):
```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD   # Supabase PostgreSQL
SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES # JWT
OPENROUTER_API_KEY, RAG_LLM_MODEL                  # OpenRouter (Gemini Flash 1.5)
RAG_EMBEDDING_MODEL                                # openai/text-embedding-3-small
PINECONE_API_KEY, PINECONE_INDEX_NAME              # creditintel-kb
PINECONE_CLOUD, PINECONE_REGION                    # aws / us-east-1
```

`frontend/.env`:
```
VITE_API_URL=http://localhost:8000
```

## Key Documentation
- `backend/BACKEND_API_SPEC.md` — full endpoint reference
- `ml/retrain_customer_model.py` — trains the LightGBM risk artifact consumed by `backend/services/ml_service.py`
- `ml/train_scorecard.py` — trains the LR scorecard artifact consumed by `backend/services/credit_score_service.py`
- `docs/ADMIN_GUIDE.md` — admin dashboard usage
- `docs/data_dictionary/` — ETL layer schemas

## Coding Guidelines

### Think Before Coding
- State assumptions explicitly before touching backend state machine logic, ML thresholds, or ETL transforms — these have downstream effects.
- If a request can be interpreted multiple ways (e.g., "update the risk model" could mean retrain, swap threshold, or change features), ask rather than pick silently.
- If `backend/ML_INTEGRATION_CHECKLIST.md` or `backend/BACKEND_API_SPEC.md` conflicts with the code, surface the discrepancy before resolving it.

### Simplicity First
- A new endpoint belongs in an existing router + service pair unless the domain is genuinely new. Don't create new files for single functions.
- Don't add Pydantic fields, DB columns, or ML features speculatively. Every addition must be tied to a concrete, requested behaviour.
- The ETL pipeline is already four layers; don't introduce a fifth transform stage for a one-off data fix.

### Surgical Changes
- When editing a service, don't reformat unrelated routers or schemas in the same file.
- Match existing Vietnamese error messages in `services/` — don't silently switch to English.
- If your change makes an import or schema field unused, remove it. Don't remove pre-existing dead code unless asked.

### Goal-Driven Execution
Before starting a multi-step task, state the plan and success criteria:
```
1. [change] → verify: [backend/tests_local/ script passes, or curl to /docs confirms endpoint]
2. [change] → verify: [npm run build succeeds, flow works in npm run mock]
```
- For bug fixes: reproduce the failure in `backend/tests_local/` first, then fix.
- For new API endpoints: confirm the contract in `BACKEND_API_SPEC.md` before writing the router.
