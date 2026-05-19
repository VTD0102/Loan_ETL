# Backend Quality Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 non-RAG quality issues uncovered during a code audit: a frontend route ordering bug, inconsistent datetime usage, lax CORS and bare `/health`, mid-file imports + overly broad exception catches in `admin_service`, and missing backend test coverage for admin and credit-score service endpoints.

**Architecture:** Surgical edits across backend services, `main.py`, `App.jsx`, and new test scripts under `backend/tests_local/`. No database migration. No RAG changes.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, React 18 + Vite, standalone test scripts in `backend/tests_local/`.

**Independent from:** All RAG plans in `docs/superpowers/plans/2026-05-19-rag-*.md` — touches no RAG files.

---

## Summary of Issues Found

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | **Bug** | `frontend/src/App.jsx` L128-133 | `/history` route is placed **after** the `*` wildcard catch-all → never matched, always 404. |
| 2 | **Code smell** | `admin_service.py` L127, L151 | Uses `datetime.now()` (local tz); `chat_service.py` L80, L144, `security.py` L17, `rag/memory.py` L138 use `datetime.utcnow()` (deprecated in 3.12). Mixed conventions → subtle time bugs on deployed servers. |
| 3 | **Security** | `main.py` L18 | `allow_origins=["*"]` with `allow_credentials=False` — the `origins` list on L8-14 is defined but unused. Production domain placeholder `"https://your-production-domain.com"` is still there. |
| 4 | **Code smell** | `admin_service.py` L110 | `from fastapi import HTTPException` import is placed mid-file (line 110), after it's already used on L106. Also bare `except Exception:` blocks on L132, L157 swallow errors silently. |
| 5 | **Operability** | `main.py` L32-34 | `/health` endpoint returns `{"status": "ok"}` but doesn't verify DB connectivity — misleading for monitoring. |
| 6 | **Test gap** | `backend/tests_local/` | No tests for admin approve/reject flow or dashboard summary aggregation. |

---

## File Structure

**Modified files:**
- `frontend/src/App.jsx` — move `/history` route above `*` catch-all.
- `backend/services/admin_service.py` — move import to top, narrow exception catches, use `datetime.now(timezone.utc)`.
- `backend/services/chat_service.py` — replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.
- `backend/core/security.py` — replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.
- `backend/rag/memory.py` — replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.
- `backend/main.py` — tighten CORS origins, enrich `/health` with DB ping.

**New files:**
- `backend/tests_local/test_admin_service.py` — tests for approve/reject/dashboard.

---

## Task 1: Fix `/history` route ordering in `App.jsx`

**Files:**
- Modify: `frontend/src/App.jsx`

The `/history` route on lines 129–133 is placed **after** the `<Route path="*" />` catch-all on line 128. React Router matches top-to-bottom, so `*` absorbs `/history` first → the page always shows `NotFound`.

- [ ] **Step 1: Move the route block**

In `frontend/src/App.jsx`, move the `/history` route **above** the `*` catch-all. The result should look like:

```diff
+    <Route path="/history" element={
+      <ProtectedRoute>
+        <WithNav><HistoryPage /></WithNav>
+      </ProtectedRoute>
+    } />
     {/* Fallback */}
     <Route path="*" element={<NotFound />} />
-    <Route path="/history" element={
-      <ProtectedRoute>
-        <WithNav><HistoryPage /></WithNav>
-      </ProtectedRoute>
-    } />
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: no errors. The `/history` page should now render correctly in `npm run dev`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "fix: move /history route above catch-all wildcard in App.jsx"
```

---

## Task 2: Standardize datetime usage (timezone-aware UTC)

**Files:**
- Modify: `backend/services/admin_service.py` (2 occurrences)
- Modify: `backend/services/chat_service.py` (2 occurrences)
- Modify: `backend/core/security.py` (1 occurrence)
- Modify: `backend/rag/memory.py` (1 occurrence)

`datetime.utcnow()` is deprecated since Python 3.12 ([PEP 670](https://peps.python.org/pep-0670/)), and `datetime.now()` returns naive local time which silently breaks on servers in non-UTC timezones. Standardize all to `datetime.now(timezone.utc)`.

- [ ] **Step 1: Update `admin_service.py`**

Add `from datetime import datetime, timezone` at the top (the existing `from datetime import datetime` on line 112 should be **removed** — it's already imported inline mid-file). Then replace:

```diff
-    app.reviewed_at = datetime.now()
+    app.reviewed_at = datetime.now(timezone.utc)
```

on both lines 127 and 151.

- [ ] **Step 2: Update `chat_service.py`**

Replace import:

```diff
-from datetime import datetime, timedelta
+from datetime import datetime, timedelta, timezone
```

Replace usages:

```diff
-    session.updated_at = datetime.utcnow()
+    session.updated_at = datetime.now(timezone.utc)
```

```diff
-    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
+    one_min_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
```

- [ ] **Step 3: Update `core/security.py`**

```diff
-from datetime import datetime, timedelta
+from datetime import datetime, timedelta, timezone
```

```diff
-    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
+    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
```

- [ ] **Step 4: Update `rag/memory.py`**

Locate the `from datetime import datetime` import and add `timezone`:

```diff
-from datetime import datetime
+from datetime import datetime, timezone
```

Replace:

```diff
-    session.summary_updated_at = datetime.utcnow()
+    session.summary_updated_at = datetime.now(timezone.utc)
```

- [ ] **Step 5: Run existing tests to verify no breakage**

```bash
cd backend
PYTHONPATH=. python tests_local/test_chat_service_uses_memory.py
PYTHONPATH=. python tests_local/test_chat_service_excludes_current_user_message.py
PYTHONPATH=. python tests_local/test_chat_service_atomic_save.py
PYTHONPATH=. python tests_local/test_memory_long_conversation_summarizes.py
```

Expected: all pass. The test files themselves still use `datetime.utcnow()` which is fine — they're mocked test code, not production. If any import inside a test breaks because it patches the module-level datetime, update that test's mock too.

- [ ] **Step 6: Commit**

```bash
git add backend/services/admin_service.py backend/services/chat_service.py \
  backend/core/security.py backend/rag/memory.py
git commit -m "fix: replace deprecated datetime.utcnow() with timezone-aware datetime.now(UTC)"
```

---

## Task 3: Fix `admin_service.py` mid-file import and bare exception blocks

**Files:**
- Modify: `backend/services/admin_service.py`

The `from fastapi import HTTPException` import appears on **line 110**, after the module has already used `HTTPException` on line 106 in `get_by_id()`. This works only by coincidence (the function isn't called until after the module finishes loading). Move it to the top. Also the bare `except Exception:` on lines 132 and 157 silently swallows DB errors — narrow them to `IntegrityError`.

- [ ] **Step 1: Move the import to the top of the file**

Add to the existing import block at the top of the file (around lines 1–8):

```diff
+from fastapi import HTTPException
 from typing import Optional
 
 from sqlalchemy.orm import Session
+from sqlalchemy.exc import IntegrityError
```

Remove the mid-file import on line 110:

```diff
-from fastapi import HTTPException
-from models.user import User
-from datetime import datetime
```

Move `from models.user import User` and `from datetime import datetime, timezone` to the top import block.

- [ ] **Step 2: Narrow the exception catches**

Replace on lines 131–134 and 156–159:

```diff
-    except Exception:
+    except IntegrityError:
         db.rollback()
-        raise HTTPException(500, "Lỗi khi duyệt đơn")
+        raise HTTPException(500, "Lỗi DB khi duyệt đơn")
```

```diff
-    except Exception:
+    except IntegrityError:
         db.rollback()
-        raise HTTPException(500, "Lỗi khi từ chối đơn")
+        raise HTTPException(500, "Lỗi DB khi từ chối đơn")
```

- [ ] **Step 3: Verify server starts**

```bash
cd backend
PYTHONPATH=. python -c "from services.admin_service import approve_application; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add backend/services/admin_service.py
git commit -m "refactor: move admin_service imports to top, narrow bare except to IntegrityError"
```

---

## Task 4: Harden CORS + enrich `/health` endpoint

**Files:**
- Modify: `backend/main.py`

Two issues: (1) `origins` list is defined but `allow_origins=["*"]` overrides it; (2) `/health` doesn't verify DB connectivity.

- [ ] **Step 1: Use the `origins` list properly**

Replace the CORS block:

```diff
 origins = [
     "http://localhost:3000",
     "http://127.0.0.1:3000",
     "http://localhost:5173",
     "http://127.0.0.1:5173",
-    "https://your-production-domain.com"
 ]
 
 app.add_middleware(
     CORSMiddleware,
-    allow_origins=["*"],
-    allow_credentials=False,
+    allow_origins=origins,
+    allow_credentials=True,
     allow_methods=["*"],
     allow_headers=["*"],
 )
```

Remove the placeholder production domain — it was never a real value and adds confusion.

- [ ] **Step 2: Enrich `/health` with DB connectivity check**

```diff
+from db.session import SessionLocal
+from sqlalchemy import text
+
 @app.get("/health")
 def health():
-    return {"status": "ok"}
+    db_ok = False
+    try:
+        db = SessionLocal()
+        db.execute(text("SELECT 1"))
+        db_ok = True
+        db.close()
+    except Exception:
+        pass
+    return {
+        "status": "ok" if db_ok else "degraded",
+        "database": "connected" if db_ok else "unreachable",
+        "version": "1.0.0",
+    }
```

- [ ] **Step 3: Verify the health endpoint**

```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000 &
sleep 2
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
kill %1
```

Expected: `{"status": "ok", "database": "connected", "version": "1.0.0"}` if DB is up, or `"degraded"` if not.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "fix: use CORS origins list instead of wildcard, add DB check to /health"
```

---

## Task 5: Add admin service tests

**Files:**
- Create: `backend/tests_local/test_admin_service.py`

No tests exist for `admin_service.approve_application`, `reject_application`, or `dashboard_summary`. These are critical business operations.

- [ ] **Step 1: Create the test file**

Create `backend/tests_local/test_admin_service.py`:

```python
"""Tests for admin_service approve / reject / payload logic.

These tests mock the DB layer to verify service-level behavior
without requiring a live database connection.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def _make_app(**overrides):
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "status": "PENDING_REVIEW",
        "monthly_income": 5000,
        "loan_amount": 10000,
        "term": 36,
        "employment_status": "Employed",
        "dti": 0.35,
        "is_homeowner": True,
        "listing_category": "1",
        "credit_score": 650,
        "default_probability": 0.25,
        "risk_level": "Medium",
        "risk_score": 75,
        "recommended_amount": 8000,
        "recommended_term": 36,
        "model_version": "v4",
        "feature_snapshot": {},
        "imputed_features": [],
        "submitted_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewed_by": None,
        "admin_note": None,
        "user": SimpleNamespace(email="user@test.com", username="testuser"),
        "occupation_type": "IT",
        "years_employed": 5,
        "num_bureau_records": 2,
        "num_active_credit": 1,
        "total_overdue_amount": 0,
        "max_credit_overdue_days": 0,
        "has_bad_debt": False,
        "income_verifiable_flag": True,
        "age_years": 30,
        "gender_male_flag": True,
        "education_ordinal": 3,
        "cnt_children": 0,
        "cnt_fam_members": 2,
        "is_married_flag": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_admin():
    return SimpleNamespace(id=uuid4(), email="admin@test.com", role="admin")


class FakeQuery:
    def __init__(self, result=None):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDB:
    def __init__(self, user=None, app=None):
        self._user = user
        self._app = app
        self._committed = False

    def query(self, model):
        from models.user import User
        from models.application import LoanApplication
        if model is User:
            return FakeQuery(self._user)
        if model is LoanApplication:
            return FakeQuery(self._app)
        return FakeQuery(None)

    def commit(self):
        self._committed = True

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def test_approve_changes_status_to_awaiting_info():
    from services.admin_service import approve_application

    admin = _make_admin()
    app = _make_app(status="PENDING_REVIEW")
    db = FakeDB(user=admin, app=app)

    result = approve_application(db, str(app.id), admin.email)

    assert result.status == "AWAITING_INFO"
    assert result.reviewed_by == admin.id
    assert result.reviewed_at is not None
    assert db._committed


def test_reject_changes_status_to_admin_rejected():
    from services.admin_service import reject_application

    admin = _make_admin()
    app = _make_app(status="PENDING_REVIEW")
    db = FakeDB(user=admin, app=app)

    result = reject_application(db, str(app.id), admin.email, note="Hồ sơ thiếu")

    assert result.status == "ADMIN_REJECTED"
    assert result.admin_note == "Hồ sơ thiếu"
    assert result.reviewed_by == admin.id
    assert db._committed


def test_approve_non_pending_raises_400():
    from services.admin_service import approve_application
    from fastapi import HTTPException

    admin = _make_admin()
    app = _make_app(status="AWAITING_INFO")
    db = FakeDB(user=admin, app=app)

    raised = None
    try:
        approve_application(db, str(app.id), admin.email)
    except HTTPException as exc:
        raised = exc
    assert raised is not None
    assert raised.status_code == 400


def test_reject_non_pending_raises_400():
    from services.admin_service import reject_application
    from fastapi import HTTPException

    admin = _make_admin()
    app = _make_app(status="APPROVED")
    db = FakeDB(user=admin, app=app)

    raised = None
    try:
        reject_application(db, str(app.id), admin.email)
    except HTTPException as exc:
        raised = exc
    assert raised is not None
    assert raised.status_code == 400


def test_application_payload_includes_user_info():
    from services.admin_service import _application_payload

    app = _make_app()
    payload = _application_payload(app)

    assert payload["user_email"] == "user@test.com"
    assert payload["user_username"] == "testuser"
    assert payload["status"] == "PENDING_REVIEW"
    assert payload["risk_level"] == "Medium"


if __name__ == "__main__":
    test_approve_changes_status_to_awaiting_info()
    test_reject_changes_status_to_admin_rejected()
    test_approve_non_pending_raises_400()
    test_reject_non_pending_raises_400()
    test_application_payload_includes_user_info()
    print("admin service tests passed")
```

- [ ] **Step 2: Run**

```bash
cd backend
PYTHONPATH=. python tests_local/test_admin_service.py
```

Expected: `admin service tests passed`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests_local/test_admin_service.py
git commit -m "test: add admin approve/reject + payload tests"
```

---

## Task 6: Final sweep

- [ ] **Step 1: Verify frontend build**

```bash
cd frontend && npm run build
```

Expected: no errors.

- [ ] **Step 2: Run all non-RAG backend tests**

```bash
cd backend
for f in tests_local/test_admin_service.py \
         tests_local/test_application_terms.py \
         tests_local/test_credit_score_contract.py \
         tests_local/test_ml_service_contract.py \
         tests_local/test_model_feature_builder.py \
         tests_local/test_router.py; do
    echo "=== $f ==="
    PYTHONPATH=. python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All non-RAG backend tests passed"
```

- [ ] **Step 3: Run RAG test sweep for regression**

```bash
cd backend
SKIP=(
  tests_local/test_rag_benchmark.py
  tests_local/test_rag_evaluation_notebook.py
)
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    skip=false
    for s in "${SKIP[@]}"; do
        [[ "$f" == "$s" ]] && skip=true && break
    done
    [[ "$skip" == true ]] && { echo "=== $f === SKIPPED (live)"; continue; }
    echo "=== $f ==="
    PYTHONPATH=. python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All RAG tests passed (no regression)"
```

- [ ] **Step 4: No commit** (verification only).

---

## Acceptance criteria

- [ ] `/history` page renders correctly in the browser (no longer shows 404).
- [ ] All datetime usages in production code use `datetime.now(timezone.utc)` — no `datetime.utcnow()` or naive `datetime.now()`.
- [ ] CORS middleware uses the explicit `origins` list, not `["*"]`.
- [ ] `/health` endpoint returns `{"status": "ok", "database": "connected", "version": "1.0.0"}`.
- [ ] `admin_service.py` has no mid-file imports and no bare `except Exception:`.
- [ ] `test_admin_service.py` passes all 5 test cases.
- [ ] All existing RAG / chat / memory tests still pass.
