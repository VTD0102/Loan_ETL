# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CreditIntel** — a loan credit risk management platform. It ingests the Prosper loan dataset through a four-layer ETL pipeline, trains a RandomForest default-prediction model, exposes a FastAPI backend with a RAG chatbot, and provides a Streamlit analytics dashboard. A React frontend is planned but currently only has placeholder directories.

## Environment Setup

```bash
# Root-level Python deps (ETL, Streamlit, ML)
pip install -r requirements.txt

# Backend deps (FastAPI, LangChain, Pinecone)
pip install -r backend/requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and fill in values for:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (Supabase PostgreSQL)
- `SECRET_KEY` (JWT, 32-char random string)
- `OPENROUTER_API_KEY`, `RAG_LLM_MODEL`, `RAG_EMBEDDING_MODEL`
- `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `PINECONE_CLOUD`, `PINECONE_REGION`

Root-level ETL uses `config/settings.yaml` for database credentials (no `.env` needed for ETL).

## Running the Services

```bash
# Streamlit dashboard (http://localhost:8501)
streamlit run ml_service/app.py

# FastAPI backend (http://localhost:8000, docs at /docs)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## ETL Pipeline

Run each layer in order from the repo root:

```bash
python -m ml_service.etl.load_bronze   # CSV → bronze.prosper_loans_raw
python -m ml_service.etl.etl_silver    # bronze → silver.prosper_loans_cleansed
python -m ml_service.etl.etl_core      # silver → core schema (normalized relational)
python -m ml_service.etl.etl_gold      # core → gold.loan_features_v1 (ML-ready features)
```

Database schemas must be initialized first (one-time):

```bash
psql ... < database/init_database.sql   # bronze + silver schemas
psql ... < database/init_core.sql       # core schema (dim/fact tables)
```

## ML Model

```bash
# Train and save model artifact
python ml/train_model.py
# Output: ml/models/loan_risk_model.pkl
```

The artifact contains the trained pipeline (StandardScaler → RandomForest), feature column names, and risk thresholds (`low` < 0.2, `high` > 0.4). The `predict_engine.py` loads this artifact and applies business rules (auto-reject on high debt-to-income ratio) on top of model scores.

## Architecture

### Data Layers (PostgreSQL / Supabase)

| Schema | Key Table | Purpose |
|--------|-----------|---------|
| `bronze` | `prosper_loans_raw` | Raw CSV ingestion |
| `silver` | `prosper_loans_cleansed` | Cleaned, deduplicated |
| `core` | loans, borrowers, credit_profiles, dim_* | Normalized relational model |
| `gold` | `loan_features_v1` + analytical views | Feature-engineered, ML-ready |

### Backend (`/backend/`)

FastAPI app with modular routers under `backend/api/routers/`. Key paths:

- `backend/core/config.py` — Pydantic settings loaded from `backend/.env`
- `backend/db/session.py` — SQLAlchemy session factory
- `backend/services/` — Business logic (auth, applications, ML predictions, chat)
- `backend/rag/` — RAG chatbot: `chain.py` builds a LangChain `ConversationalRetrievalChain` using OpenRouter as the LLM and Pinecone for vector retrieval; `ingest.py` populates the Pinecone index from markdown knowledge base files in `backend/rag/knowledge/`
- `backend/models/` — Pydantic request/response schemas (separate from SQLAlchemy ORM)

### Streamlit App (`/ml_service/`)

- `app.py` — Entry point; routes to Risk Dashboard or Underwriting System
- `dashboard.py` — Portfolio KPIs, charts, record search (reads `gold.loan_features_v1`)
- `prediction_ui.py` — Real-time loan risk form using `ml/predict_engine.py`
- `data_handler.py` — Loads gold layer with `@st.cache_data`

### Shared Database Connection

`utils/db_connection.py` provides a cached SQLAlchemy engine used by both the ETL scripts and the Streamlit app. It reads credentials from `config/settings.yaml` but environment variable overrides take precedence.

### Frontend (`/frontend/`)

Placeholder directory structure only — React pages and components have not been implemented yet.

## Key Docs

- `docs/overall/PROJECT_OVERVIEW.md` — Full architecture, data pipeline, and ML approach
- `docs/overall/APP_DEVELOPMENT_PLAN.md` — Web application design and feature roadmap (customer/admin roles)
- `docs/data_dictionary/` — Column-level schema documentation for each ETL layer
- `docs/ml_md/` — Model training details and feature reference
