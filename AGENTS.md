# Repository Guidelines

## Project Structure & Module Organization

`backend/` contains the FastAPI app: `api/routers/`, `services/`, `models/`, `schemas/`, `core/`, `db/`, and `rag/`. Local backend smoke and integration scripts live in `backend/tests_local/`.

`frontend/` is a React 18 + Vite + Tailwind app. Source is in `frontend/src/`: reusable UI in `components/`, route pages in `pages/`, API clients in `services/`, Zustand state in `store/`, and mock data in `mocks/`.

`etl/` holds the Bronze -> Silver -> Core -> Gold pipeline. `ml/` contains the two supported training scripts: `retrain_customer_model.py` for risk prediction and `train_scorecard.py` for credit scorecard. Runtime inference lives in backend services. `database/` stores SQL init and transform scripts. `docs/` contains architecture notes, data dictionaries, and guides.

## Build, Test, and Development Commands

Backend:

```bash
cd backend
pip install -r requirements.txt
python init_db.py
uvicorn main:app --reload
```

Swagger docs: `http://localhost:8000/docs`.

Frontend:

```bash
cd frontend
npm install
npm run dev      # Vite dev server on port 5173
npm run mock     # frontend with mocked API responses
npm run build    # production bundle in dist/
npm run preview  # preview production build
```

ETL and ML from the repository root:

```bash
python -m etl.load_bronze
python -m etl.etl_silver
python -m etl.etl_core
python -m etl.etl_gold
python -m ml.retrain_customer_model
python ml/train_scorecard.py
```

## Coding Style & Naming Conventions

Use Python 3.10+ with 4-space indentation and absolute imports inside `backend/`, such as `from core.config import settings`. Keep API handlers thin; place business logic in `services/`, tables in `models/`, and request/response contracts in `schemas/`.

React components use PascalCase names, for example `ApplicationCard/index.jsx`. API helpers live under `frontend/src/services/`. Prefer Tailwind utilities and existing shared components before adding new styling patterns.

## Testing Guidelines

Backend tests are local scripts under `backend/tests_local/`. Run them from `backend/` so imports resolve consistently:

```bash
cd backend
python tests_local/test_db.py
python tests_local/test_task_1_3.py
```

Add backend checks as `test_<feature>.py`. For frontend work, verify `npm run build` and the affected flow in `npm run dev` or `npm run mock`.

## Commit & Pull Request Guidelines

Git history uses short messages with prefixes such as `feat:`, `fix`, `refactor:`, `update`, and `merge:`. Keep scope clear, for example `feat: add admin risk filter`.

Pull requests should describe the change, list backend/frontend/database impact, mention required environment variables, and include screenshots for UI changes. Link issues or task docs when available, and note commands run.

## Security & Configuration Tips

Keep secrets in local `.env` files, especially `backend/.env` database credentials, JWT `SECRET_KEY`, and AI keys. Do not commit virtual environments, build outputs, or private datasets unless explicitly tracked.
