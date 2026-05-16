# Credit Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a complete FICO-style credit scoring system (300–850) — fix the live ML mock fallback, train a Logistic Regression scorecard, expose a `GET /credit-score/{member_key}` API, add SHAP explainability, enrich the gold SQL layer with behavioral features and analytical views, and build a frontend analytics dashboard.

**Architecture:** `ml/train_scorecard.py` trains a Logistic Regression on `gold.loan_features_v1` and saves a scorecard artifact. A shared `backend/core/scoring.py` utility converts default probability to a 300–850 score via the FICO PDO formula. A new `credit_score` router exposes the score endpoint; `ml_service.py` is fixed to load the correct `customer_risk_model.pkl`. The gold SQL layer gains three behavioral columns and three analytical views consumed by the admin frontend dashboard.

**Tech Stack:** scikit-learn (LogisticRegression, Pipeline, ColumnTransformer), shap, joblib, FastAPI, SQLAlchemy (text), pandas, numpy, PostgreSQL, React 18 + Recharts

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `ml/train_scorecard.py` | Train LR scorecard on gold features, save artifact |
| **Create** | `ml/models/scorecard_model.pkl` | Generated artifact (LR pipeline + scoring params) |
| **Create** | `backend/core/scoring.py` | FICO PDO formula + score-band helper (shared utility) |
| **Create** | `backend/schemas/credit_score.py` | `CreditScoreResponse` Pydantic schema |
| **Create** | `backend/services/credit_score_service.py` | Load scorecard, fetch gold features, compute score + SHAP |
| **Create** | `backend/api/routers/credit_score.py` | `GET /credit-score/{member_key}` |
| **Create** | `backend/tests_local/test_credit_score.py` | Integration test for the endpoint |
| **Create** | `frontend/src/pages/admin/CreditDashboard/index.jsx` | Admin credit analytics page |
| **Modify** | `ml/retrain_customer_model.py` | *(Run only — no code change needed)* |
| **Modify** | `backend/services/ml_service.py` | Change MODEL_PATH to customer_risk_model.pkl (1 line) |
| **Modify** | `backend/main.py` | Register credit_score router |
| **Modify** | `database/transform_gold.sql` | Add `payment_to_income`, `num_previous_loans`, `previous_default_rate` + 3 analytical views |
| **Modify** | `backend/requirements.txt` | Add `shap` |

---

## Task 1 — Regenerate customer_risk_model.pkl and Fix ml_service.py

**Root cause:** `ml_service.py` line 7 loads `loan_risk_model.pkl` (trained on 34 Prosper-internal gold features) but passes a DataFrame with only the 8 customer-form columns → feature mismatch → silent fallback to mock values. `customer_risk_model.pkl` (trained by `retrain_customer_model.py` on exactly those 8 features) is the correct artifact.

**Files:**
- Run: `ml/retrain_customer_model.py`
- Modify: `backend/services/ml_service.py:7`

- [ ] **Step 1: Regenerate the customer risk model artifact**

Run from the project root (activate venv first):
```bash
cd /path/to/Loan_ETL
source venv/bin/activate
python ml/retrain_customer_model.py
```

Expected output (last lines):
```
  ROC-AUC : 0.7xxx
  ...
  Saved → .../ml/models/customer_risk_model.pkl
```

Verify the file exists:
```bash
ls -lh ml/models/customer_risk_model.pkl
```
Expected: file exists, size ~10–80 MB.

- [ ] **Step 2: Write the failing test**

Create `backend/tests_local/test_ml_service.py`:
```python
"""Test that ml_service returns real predictions (no mock fallback)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from schemas.application import ApplicationCreate
from services.ml_service import predict

def test_predict_no_mock():
    payload = ApplicationCreate(
        monthly_income=5000.0,
        loan_amount=10000.0,
        term=36,
        employment_status="Employed",
        dti=0.2,
        is_homeowner=True,
        listing_category=1,
        credit_score=720,
    )
    result = predict(payload)
    # Real model output: probability is deterministic for a given input
    assert 0.0 <= result["default_probability"] <= 1.0
    assert result["risk_level"] in {"Low", "Medium", "High"}
    # Mock logic returns exactly 0.15 for credit_score >= 650 — real model won't hit this exactly
    assert result["default_probability"] != 0.15, "Still returning mock value"
    assert result["default_probability"] != 0.5,  "Still returning mock value"
    print(f"PASS — default_probability={result['default_probability']}, risk={result['risk_level']}")

if __name__ == "__main__":
    test_predict_no_mock()
```

- [ ] **Step 3: Run the test — confirm it fails (still on wrong model)**

```bash
cd backend
python tests_local/test_ml_service.py
```
Expected: `AssertionError: Still returning mock value`  
(because MODEL_PATH still points to `loan_risk_model.pkl`)

- [ ] **Step 4: Fix ml_service.py — one line change**

In `backend/services/ml_service.py` line 7, change:
```python
# Before
MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "loan_risk_model.pkl"
```
```python
# After
MODEL_PATH = Path(__file__).parents[2] / "ml" / "models" / "customer_risk_model.pkl"
```

Also reset the cached artifact (add after the MODEL_PATH line):
```python
_artifact = None  # reset on module reload
```

Wait — `_artifact = None` is already on line 9. The fix is the MODEL_PATH change only.

- [ ] **Step 5: Run the test — confirm it passes**

```bash
cd backend
python tests_local/test_ml_service.py
```
Expected:
```
PASS — default_probability=0.xxxx, risk=Low
```

- [ ] **Step 6: Commit**

```bash
git add ml/models/customer_risk_model.pkl backend/services/ml_service.py backend/tests_local/test_ml_service.py
git commit -m "fix: load customer_risk_model.pkl in ml_service — remove mock fallback"
```

---

## Task 2 — Add Behavioral Features to Gold Layer

**Files:**
- Modify: `database/transform_gold.sql`
- Run: `etl/etl_gold.py` (via `python -m etl.etl_gold`)

**New columns:**
- `payment_to_income` — approximate monthly payment burden: `(loan_original_amount / term) / stated_monthly_income`
- `num_previous_loans` — count of prior loans for the same `member_key`
- `previous_default_rate` — default rate on prior loans for the same `member_key`

- [ ] **Step 1: Add a `behavioral` CTE to transform_gold.sql**

In `database/transform_gold.sql`, after the `WITH base AS (...)` CTE and before `engineered AS (...)`, add:

```sql
behavioral AS (
    SELECT
        l.listing_key,
        COUNT(l2.listing_key) AS num_previous_loans,
        COALESCE(
            AVG(s2.is_default::numeric),
            0.0
        ) AS previous_default_rate
    FROM core.loans l
    LEFT JOIN core.loans l2
        ON  l2.member_key = l.member_key
        AND l2.loan_origination_date < l.loan_origination_date
    LEFT JOIN silver.prosper_loans_cleansed s2
        ON  s2.listing_key = l2.listing_key
    GROUP BY l.listing_key
),
```

- [ ] **Step 2: Add `payment_to_income` to the `engineered` CTE and join `behavioral`**

Inside the `engineered` CTE `SELECT`, after the `high_dti_flag` expression, add:

```sql
        -- Engineered: Behavioral / Burden
        CASE
            WHEN loan_original_amount IS NOT NULL
             AND term > 0
             AND stated_monthly_income IS NOT NULL
             AND stated_monthly_income > 0
            THEN (loan_original_amount / term) / stated_monthly_income
            ELSE NULL
        END AS payment_to_income,

        COALESCE(beh.num_previous_loans, 0)    AS num_previous_loans,
        COALESCE(beh.previous_default_rate, 0) AS previous_default_rate,
```

Change the `FROM base` line in the `engineered` CTE to:

```sql
    FROM base
    LEFT JOIN behavioral beh USING (listing_key)
```

- [ ] **Step 3: Re-run the ETL gold step**

```bash
source venv/bin/activate
python -m etl.etl_gold
```

Expected: no errors, script completes successfully.

- [ ] **Step 4: Verify new columns exist**

Connect to the DB (psql or any SQL client) and run:
```sql
SELECT listing_key, payment_to_income, num_previous_loans, previous_default_rate
FROM gold.loan_features_v1
LIMIT 5;
```
Expected: 5 rows with numeric values (many will have `num_previous_loans = 0` for first-time borrowers).

- [ ] **Step 5: Commit**

```bash
git add database/transform_gold.sql
git commit -m "feat: add payment_to_income, num_previous_loans, previous_default_rate to gold layer"
```

---

## Task 3 — Train Logistic Regression Scorecard

**Files:**
- Create: `ml/train_scorecard.py`
- Generates: `ml/models/scorecard_model.pkl`

The scorecard uses 9 gold features. LR outputs a default probability, which the `pd_to_credit_score` formula (Task 4) converts to 300–850.

- [ ] **Step 1: Create ml/train_scorecard.py**

```python
"""
Train a Logistic Regression scorecard on gold.loan_features_v1.
Output artifact: ml/models/scorecard_model.pkl

Run: python ml/train_scorecard.py
"""
import joblib
import pandas as pd
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "scorecard_model.pkl"

NUMERIC_FEATURES = [
    "credit_score_midpoint",
    "debt_to_income_ratio",
    "loan_amount_to_income",
    "log_monthly_income",
    "rating_ordinal",
    "is_homeowner_flag",
    "income_verifiable_flag",
    "high_dti_flag",
    "payment_to_income",
    "num_previous_loans",
    "previous_default_rate",
]
CATEGORICAL_FEATURES = ["employment_status_grouped"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

LOW_THRESHOLD  = 0.2
HIGH_THRESHOLD = 0.4

QUERY = """
SELECT
    credit_score_midpoint,
    debt_to_income_ratio,
    loan_amount_to_income,
    log_monthly_income,
    rating_ordinal,
    is_homeowner_flag,
    income_verifiable_flag,
    high_dti_flag,
    payment_to_income,
    num_previous_loans,
    previous_default_rate,
    employment_status_grouped,
    is_default
FROM gold.loan_features_v1
WHERE credit_score_midpoint  IS NOT NULL
  AND debt_to_income_ratio   IS NOT NULL
  AND log_monthly_income     IS NOT NULL
  AND loan_amount_to_income  IS NOT NULL
"""

import sys
sys.path.insert(0, str(BASE_DIR))
from utils.db_connection import get_engine


def train():
    print("=" * 55)
    print("  LOGISTIC REGRESSION SCORECARD — TRAIN")
    print("=" * 55)

    engine = get_engine()

    print("\n[1/5] Loading features from gold.loan_features_v1...")
    df = pd.read_sql(QUERY, engine)
    df[NUMERIC_FEATURES]     = df[NUMERIC_FEATURES].fillna(df[NUMERIC_FEATURES].median())
    df[CATEGORICAL_FEATURES] = df[CATEGORICAL_FEATURES].fillna("Other/Unknown")
    print(f"  Rows: {len(df):,}  |  Default rate: {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES]
    y = df["is_default"]

    print("\n[2/5] Splitting 80/20 (stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\n[3/5] Building pipeline (StandardScaler + LogisticRegression)...")
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
         CATEGORICAL_FEATURES),
    ])
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(
            C=0.1, max_iter=500, class_weight="balanced", random_state=42,
        )),
    ])

    print("\n[4/5] Training...")
    pipeline.fit(X_train, y_train)

    print("\n[5/5] Evaluating on test set...")
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    y_pred = pipeline.predict(X_test)
    auc    = roc_auc_score(y_test, y_prob)
    print(f"  ROC-AUC: {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["No Default", "Default"]))

    artifact = {
        "pipeline":       pipeline,
        "feature_cols":   ALL_FEATURES,
        "thresholds":     {"low": LOW_THRESHOLD, "high": HIGH_THRESHOLD},
        "scoring_params": {"base_score": 600, "base_odds": 50, "pdo": 20},
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)
    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    train()
```

- [ ] **Step 2: Run training**

```bash
source venv/bin/activate
python ml/train_scorecard.py
```

Expected (last lines):
```
  ROC-AUC: 0.7x–0.8x
  ...
  Saved → .../ml/models/scorecard_model.pkl
```

Accept any ROC-AUC ≥ 0.65 as a valid scorecard.

- [ ] **Step 3: Verify artifact structure**

```bash
python - <<'EOF'
import joblib
a = joblib.load("ml/models/scorecard_model.pkl")
print(list(a.keys()))          # ['pipeline', 'feature_cols', 'thresholds', 'scoring_params']
print(a["scoring_params"])     # {'base_score': 600, 'base_odds': 50, 'pdo': 20}
print(len(a["feature_cols"]))  # 12
EOF
```

- [ ] **Step 4: Commit**

```bash
git add ml/train_scorecard.py ml/models/scorecard_model.pkl
git commit -m "feat: add LR scorecard training script and artifact"
```

---

## Task 4 — Create backend/core/scoring.py (FICO Formula)

**Files:**
- Create: `backend/core/scoring.py`

This module is the single source of truth for the PDO-based credit score formula and band labels. Both `ml_service.py` and `credit_score_service.py` import from here.

- [ ] **Step 1: Create the file**

```python
# backend/core/scoring.py
import math

_BASE   = 600
_ODDS   = 50
_PDO    = 20
_FACTOR = _PDO / math.log(2)


def pd_to_credit_score(pd_value: float) -> int:
    """Convert default probability to FICO-style score (300–850).

    Formula: score = base + (PDO / ln2) * ln(odds / base_odds)
    """
    p     = max(1e-6, min(1 - 1e-6, float(pd_value)))
    odds  = (1 - p) / p
    score = _BASE + _FACTOR * math.log(odds / _ODDS)
    return max(300, min(850, round(score)))


def score_to_band(score: int) -> str:
    if score >= 740: return "Excellent"
    if score >= 670: return "Good"
    if score >= 580: return "Fair"
    return "Poor"
```

- [ ] **Step 2: Write a quick sanity check**

Create `backend/tests_local/test_scoring.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from core.scoring import pd_to_credit_score, score_to_band

def test_scoring():
    # At base_odds=50, pd≈0.0196 → score ≈ 600
    s = pd_to_credit_score(0.02)
    assert 590 <= s <= 610, f"Expected ~600, got {s}"

    # Very low risk → high score
    assert pd_to_credit_score(0.001) > 650

    # Very high risk → low score, clamped to 300
    assert pd_to_credit_score(0.99) == 300

    # Perfect credit → clamped to 850
    assert pd_to_credit_score(0.0000001) == 850

    assert score_to_band(750) == "Excellent"
    assert score_to_band(700) == "Good"
    assert score_to_band(600) == "Fair"
    assert score_to_band(500) == "Poor"
    print("PASS — all scoring assertions passed")

if __name__ == "__main__":
    test_scoring()
```

- [ ] **Step 3: Run the test**

```bash
cd backend
python tests_local/test_scoring.py
```
Expected: `PASS — all scoring assertions passed`

- [ ] **Step 4: Commit**

```bash
git add backend/core/scoring.py backend/tests_local/test_scoring.py
git commit -m "feat: add FICO PDO credit score formula in backend/core/scoring.py"
```

---

## Task 5 — Create Credit Score Schema and Service

**Files:**
- Create: `backend/schemas/credit_score.py`
- Create: `backend/services/credit_score_service.py`

- [ ] **Step 1: Create backend/schemas/credit_score.py**

```python
# backend/schemas/credit_score.py
from pydantic import BaseModel


class CreditScoreResponse(BaseModel):
    member_key:          str
    credit_score:        int           # 300–850
    score_band:          str           # Excellent / Good / Fair / Poor
    default_probability: float
    risk_level:          str           # Low / Medium / High
    top_factors:         list[dict]    # [{feature, direction, impact}]
```

- [ ] **Step 2: Create backend/services/credit_score_service.py**

```python
# backend/services/credit_score_service.py
import joblib
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.scoring import pd_to_credit_score, score_to_band

SCORECARD_PATH = Path(__file__).parents[2] / "ml" / "models" / "scorecard_model.pkl"

NUMERIC_FEATURES = [
    "credit_score_midpoint", "debt_to_income_ratio", "loan_amount_to_income",
    "log_monthly_income", "rating_ordinal", "is_homeowner_flag",
    "income_verifiable_flag", "high_dti_flag",
    "payment_to_income", "num_previous_loans", "previous_default_rate",
]
CATEGORICAL_FEATURES = ["employment_status_grouped"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

_artifact = None


def _load():
    global _artifact
    if _artifact is None:
        _artifact = joblib.load(SCORECARD_PATH)
    return _artifact


def get_credit_score(member_key: str, db: Session) -> dict:
    artifact     = _load()
    pipeline     = artifact["pipeline"]
    feature_cols = artifact["feature_cols"]

    col_list = ", ".join(feature_cols)
    sql = text(f"""
        SELECT {col_list}
        FROM gold.loan_features_v1
        WHERE member_key = :member_key
        ORDER BY loan_origination_date DESC
        LIMIT 1
    """)
    row = db.execute(sql, {"member_key": member_key}).fetchone()

    if row is None:
        raise ValueError(f"member_key '{member_key}' not found in gold layer")

    df = pd.DataFrame([dict(row._mapping)])
    df[NUMERIC_FEATURES]     = df[NUMERIC_FEATURES].fillna(df[NUMERIC_FEATURES].median())
    df[CATEGORICAL_FEATURES] = df[CATEGORICAL_FEATURES].fillna("Other/Unknown")

    pd_value     = float(pipeline.predict_proba(df[feature_cols])[0, 1])
    credit_score = pd_to_credit_score(pd_value)

    risk_level = (
        "Low" if pd_value < artifact["thresholds"]["low"]
        else "High" if pd_value > artifact["thresholds"]["high"]
        else "Medium"
    )

    return {
        "member_key":          member_key,
        "credit_score":        credit_score,
        "score_band":          score_to_band(credit_score),
        "default_probability": round(pd_value, 4),
        "risk_level":          risk_level,
        "top_factors":         [],  # populated in Task 7 (SHAP)
    }
```

- [ ] **Step 3: Write test**

Create `backend/tests_local/test_credit_score_service.py`:
```python
"""Integration test — requires live DB and scorecard_model.pkl."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from db.session import SessionLocal
from services.credit_score_service import get_credit_score

def test_get_credit_score():
    db = SessionLocal()
    try:
        # Fetch any member_key from the DB
        from sqlalchemy import text
        result = db.execute(text("SELECT member_key FROM gold.loan_features_v1 LIMIT 1")).fetchone()
        assert result, "No rows in gold.loan_features_v1 — run ETL first"
        member_key = result[0]

        score_data = get_credit_score(member_key, db)

        assert 300 <= score_data["credit_score"] <= 850
        assert score_data["score_band"]  in {"Excellent", "Good", "Fair", "Poor"}
        assert score_data["risk_level"]  in {"Low", "Medium", "High"}
        assert 0.0 <= score_data["default_probability"] <= 1.0
        print(f"PASS — member_key={member_key}, score={score_data['credit_score']} ({score_data['score_band']})")
    finally:
        db.close()

if __name__ == "__main__":
    test_get_credit_score()
```

- [ ] **Step 4: Run test**

```bash
cd backend
python tests_local/test_credit_score_service.py
```
Expected: `PASS — member_key=..., score=... (Good)`

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/credit_score.py backend/services/credit_score_service.py backend/tests_local/test_credit_score_service.py
git commit -m "feat: add credit score schema and service (scorecard lookup)"
```

---

## Task 6 — Create Credit Score Router and Register

**Files:**
- Create: `backend/api/routers/credit_score.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create backend/api/routers/credit_score.py**

```python
# backend/api/routers/credit_score.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from core.security import get_current_user
from schemas.credit_score import CreditScoreResponse
from services.credit_score_service import get_credit_score

router = APIRouter()


@router.get("/{member_key}", response_model=CreditScoreResponse)
def credit_score(
    member_key: str,
    db:         Session = Depends(get_db),
    _user=      Depends(get_current_user),
):
    try:
        return get_credit_score(member_key, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 2: Register the router in backend/main.py**

In `backend/main.py`, add the import and `include_router` call:

```python
# add to imports
from api.routers import auth, applications, admin, chat, credit_score

# add after existing include_router calls
app.include_router(credit_score.router, prefix="/credit-score", tags=["credit-score"])
```

- [ ] **Step 3: Start the server and verify the endpoint appears in Swagger**

```bash
cd backend
uvicorn main:app --reload
```

Open `http://localhost:8000/docs` and confirm `GET /credit-score/{member_key}` is listed under the `credit-score` tag.

- [ ] **Step 4: Smoke test via curl**

```bash
# First get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Pick a member_key from the DB — replace AA1234567890 with a real value
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/credit-score/AA1234567890 | python3 -m json.tool
```

Expected:
```json
{
  "member_key": "AA1234567890",
  "credit_score": 612,
  "score_band": "Fair",
  "default_probability": 0.2841,
  "risk_level": "Medium",
  "top_factors": []
}
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/routers/credit_score.py backend/main.py
git commit -m "feat: add GET /credit-score/{member_key} endpoint"
```

---

## Task 7 — SHAP Integration (Top-3 Feature Explanations)

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/services/credit_score_service.py`

SHAP with `LinearExplainer` works on the raw (pre-pipeline) feature matrix. We reconstruct it after preprocessing.

- [ ] **Step 1: Add shap to requirements.txt**

Append to `backend/requirements.txt`:
```
shap>=0.45.0
```

Install:
```bash
cd backend
pip install shap>=0.45.0
```

- [ ] **Step 2: Update credit_score_service.py to compute SHAP values**

Replace the `get_credit_score` function body with the version below. Add the shap import at the top of the file:

```python
# at the top of backend/services/credit_score_service.py — add import
import shap
import numpy as np
```

Replace `get_credit_score` (the full function):

```python
def get_credit_score(member_key: str, db: Session) -> dict:
    artifact     = _load()
    pipeline     = artifact["pipeline"]
    feature_cols = artifact["feature_cols"]

    col_list = ", ".join(feature_cols)
    sql = text(f"""
        SELECT {col_list}
        FROM gold.loan_features_v1
        WHERE member_key = :member_key
        ORDER BY loan_origination_date DESC
        LIMIT 1
    """)
    row = db.execute(sql, {"member_key": member_key}).fetchone()

    if row is None:
        raise ValueError(f"member_key '{member_key}' not found in gold layer")

    df = pd.DataFrame([dict(row._mapping)])
    df[NUMERIC_FEATURES]     = df[NUMERIC_FEATURES].fillna(df[NUMERIC_FEATURES].median())
    df[CATEGORICAL_FEATURES] = df[CATEGORICAL_FEATURES].fillna("Other/Unknown")

    X             = df[feature_cols]
    pd_value      = float(pipeline.predict_proba(X)[0, 1])
    credit_score  = pd_to_credit_score(pd_value)

    risk_level = (
        "Low" if pd_value < artifact["thresholds"]["low"]
        else "High" if pd_value > artifact["thresholds"]["high"]
        else "Medium"
    )

    # SHAP: explain on pre-processed matrix
    X_transformed = pipeline.named_steps["preprocessor"].transform(X)
    lr_model      = pipeline.named_steps["classifier"]
    explainer     = shap.LinearExplainer(lr_model, X_transformed, feature_perturbation="interventional")
    shap_values   = explainer.shap_values(X_transformed)[0]  # shape: (n_features,)

    # Map back to original feature names (preprocessor output order = ALL_FEATURES order)
    shap_pairs = sorted(
        zip(feature_cols, shap_values),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:3]
    top_factors = [
        {
            "feature":   feat,
            "direction": "increases_risk" if val > 0 else "decreases_risk",
            "impact":    round(float(val), 4),
        }
        for feat, val in shap_pairs
    ]

    return {
        "member_key":          member_key,
        "credit_score":        credit_score,
        "score_band":          score_to_band(credit_score),
        "default_probability": round(pd_value, 4),
        "risk_level":          risk_level,
        "top_factors":         top_factors,
    }
```

- [ ] **Step 3: Re-run the service test**

```bash
cd backend
python tests_local/test_credit_score_service.py
```

Expected: `PASS` with `top_factors` now populated. The output will look like:
```
PASS — member_key=..., score=612 (Fair)
```

Run manually to inspect factors:
```python
# one-off check in Python REPL
from db.session import SessionLocal
from services.credit_score_service import get_credit_score
db = SessionLocal()
from sqlalchemy import text
mk = db.execute(text("SELECT member_key FROM gold.loan_features_v1 LIMIT 1")).fetchone()[0]
import json; print(json.dumps(get_credit_score(mk, db), indent=2))
db.close()
```

Confirm `top_factors` is a list of 3 dicts, each with `feature`, `direction`, `impact`.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt backend/services/credit_score_service.py
git commit -m "feat: add SHAP top-3 factor explanations to credit score endpoint"
```

---

## Task 8 — Add Gold Analytical Views for Credit Dashboard

**Files:**
- Modify: `database/transform_gold.sql`

Add three views to support the frontend dashboard charts. Append them to the end of `transform_gold.sql` (after the existing views).

- [ ] **Step 1: Append credit score analytical views to transform_gold.sql**

```sql
-- 5.6. Credit score band distribution
DROP VIEW IF EXISTS gold.vw_credit_score_distribution;
CREATE VIEW gold.vw_credit_score_distribution AS
SELECT
    CASE
        WHEN credit_score_midpoint >= 740 THEN 'Excellent (740+)'
        WHEN credit_score_midpoint >= 670 THEN 'Good (670-739)'
        WHEN credit_score_midpoint >= 580 THEN 'Fair (580-669)'
        WHEN credit_score_midpoint IS NOT NULL THEN 'Poor (<580)'
        ELSE 'Unknown'
    END AS score_band,
    COUNT(*) AS loan_count,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct,
    ROUND(AVG(debt_to_income_ratio)::numeric, 4) AS avg_dti
FROM gold.loan_features_v1
GROUP BY score_band
ORDER BY score_band;

-- 5.7. Default rate vs credit score band over time
DROP VIEW IF EXISTS gold.vw_score_vs_default;
CREATE VIEW gold.vw_score_vs_default AS
SELECT
    origination_year,
    CASE
        WHEN credit_score_midpoint >= 740 THEN 'Excellent'
        WHEN credit_score_midpoint >= 670 THEN 'Good'
        WHEN credit_score_midpoint >= 580 THEN 'Fair'
        WHEN credit_score_midpoint IS NOT NULL THEN 'Poor'
        ELSE 'Unknown'
    END AS score_band,
    COUNT(*) AS loan_count,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct
FROM gold.loan_features_v1
WHERE origination_year IS NOT NULL
GROUP BY origination_year, score_band
ORDER BY origination_year, score_band;

-- 5.8. Score trend: average credit score by origination year
DROP VIEW IF EXISTS gold.vw_score_trend;
CREATE VIEW gold.vw_score_trend AS
SELECT
    origination_year,
    ROUND(AVG(credit_score_midpoint)::numeric, 1) AS avg_credit_score,
    COUNT(*) AS loan_count,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct
FROM gold.loan_features_v1
WHERE origination_year IS NOT NULL
  AND credit_score_midpoint IS NOT NULL
GROUP BY origination_year
ORDER BY origination_year;
```

- [ ] **Step 2: Apply the views to the DB**

The new views don't depend on table recreation, so apply them directly:
```bash
# Connect to your Supabase DB and run just the three new view statements
# Or re-run the full gold ETL (will recreate table + views from scratch):
python -m etl.etl_gold
```

- [ ] **Step 3: Verify views return data**

```sql
SELECT * FROM gold.vw_credit_score_distribution;
SELECT * FROM gold.vw_score_trend LIMIT 5;
```

Expected: rows with `score_band`, `loan_count`, `default_rate_pct` columns.

- [ ] **Step 4: Add admin endpoint for credit stats**

In `backend/api/routers/admin.py`, add this endpoint at the end of the file:

```python
@router.get("/dashboard/credit-score-stats")
def credit_score_stats(
    db:    Session = Depends(get_db),
    _user= Depends(get_current_admin),
):
    from sqlalchemy import text
    distribution = db.execute(text(
        "SELECT score_band, loan_count, default_rate_pct, avg_dti "
        "FROM gold.vw_credit_score_distribution"
    )).mappings().all()

    trend = db.execute(text(
        "SELECT origination_year, avg_credit_score, loan_count, default_rate_pct "
        "FROM gold.vw_score_trend ORDER BY origination_year"
    )).mappings().all()

    return {
        "distribution": [dict(r) for r in distribution],
        "trend":        [dict(r) for r in trend],
    }
```

Verify it works: `GET /admin/dashboard/credit-score-stats` in Swagger.

- [ ] **Step 5: Commit**

```bash
git add database/transform_gold.sql backend/api/routers/admin.py
git commit -m "feat: add credit score gold views + admin/dashboard/credit-score-stats endpoint"
```

---

## Task 9 — Frontend Credit Dashboard Page

**Files:**
- Create: `frontend/src/pages/admin/CreditDashboard/index.jsx`
- Modify: `frontend/src/pages/admin/AdminDashboard/index.jsx` (add nav link)
- Modify: `frontend/src/App.jsx` or router file (add route)
- Modify: `frontend/src/services/api.js` (add API call)

- [ ] **Step 1: Add the API call to frontend/src/services/api.js**

```js
// Add inside the existing api.js file
export const getCreditScoreStats = () =>
  api.get("/admin/dashboard/credit-score-stats");
```

- [ ] **Step 2: Create frontend/src/pages/admin/CreditDashboard/index.jsx**

```jsx
import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { getCreditScoreStats } from "../../../services/api";

const BAND_COLORS = {
  "Excellent (740+)": "#10b981",
  "Good (670-739)":   "#6366f1",
  "Fair (580-669)":   "#f59e0b",
  "Poor (<580)":      "#ef4444",
  "Unknown":          "#94a3b8",
};

export default function CreditDashboard() {
  const [stats, setStats]   = useState(null);
  const [error, setError]   = useState(null);

  useEffect(() => {
    getCreditScoreStats()
      .then((res) => setStats(res.data))
      .catch((err) => setError(err.message));
  }, []);

  if (error)  return <p className="text-red-400 p-8">{error}</p>;
  if (!stats) return <p className="text-slate-400 p-8">Loading…</p>;

  return (
    <div className="p-8 space-y-10">
      <h1 className="text-2xl font-bold text-white">Credit Score Analytics</h1>

      {/* Distribution */}
      <section>
        <h2 className="text-lg font-semibold text-slate-300 mb-4">
          Score Band Distribution
        </h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={stats.distribution}>
            <XAxis dataKey="score_band" tick={{ fill: "#94a3b8", fontSize: 12 }} />
            <YAxis tick={{ fill: "#94a3b8" }} />
            <Tooltip
              contentStyle={{ background: "#1a2236", border: "1px solid #2a3550" }}
            />
            <Bar dataKey="loan_count" name="Loans" fill="#6366f1" radius={[4,4,0,0]} />
            <Bar dataKey="default_rate_pct" name="Default %" fill="#ef4444" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Trend */}
      <section>
        <h2 className="text-lg font-semibold text-slate-300 mb-4">
          Avg Credit Score by Year
        </h2>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={stats.trend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3550" />
            <XAxis dataKey="origination_year" tick={{ fill: "#94a3b8" }} />
            <YAxis domain={[550, 800]} tick={{ fill: "#94a3b8" }} />
            <Tooltip
              contentStyle={{ background: "#1a2236", border: "1px solid #2a3550" }}
            />
            <Legend />
            <Line
              type="monotone" dataKey="avg_credit_score"
              stroke="#6366f1" strokeWidth={2} dot={false} name="Avg Score"
            />
            <Line
              type="monotone" dataKey="default_rate_pct"
              stroke="#ef4444" strokeWidth={2} dot={false} name="Default %"
            />
          </LineChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Add a route for the new page**

Find the React Router config (likely in `frontend/src/App.jsx` or a routes file). Add:
```jsx
import CreditDashboard from "./pages/admin/CreditDashboard";

// Inside <Routes>:
<Route path="/admin/credit-dashboard" element={<CreditDashboard />} />
```

- [ ] **Step 4: Add a nav link from AdminDashboard**

In `frontend/src/pages/admin/AdminDashboard/index.jsx`, add a link to the new page (use whatever Link/NavLink component the existing admin nav uses):
```jsx
<Link to="/admin/credit-dashboard">Credit Dashboard</Link>
```

- [ ] **Step 5: Test in browser**

```bash
cd frontend
npm run dev
```

Navigate to `/admin/credit-dashboard` (log in as admin first). Confirm:
- Bar chart renders score band distribution
- Line chart renders avg score + default rate trend by year
- No console errors

Test mock mode too:
```bash
npm run mock
```
Confirm no crash (API call will return empty or mocked data — charts should render with empty state gracefully, not throw).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/admin/CreditDashboard/ frontend/src/services/api.js frontend/src/App.jsx
git commit -m "feat: add admin CreditDashboard page with score distribution and trend charts"
```

---

## Self-Review

### Spec Coverage

| Evaluation Doc Item | Plan Task |
|--------------------|-----------|
| Fix ML mock fallback in ml_service.py | Task 1 |
| Add behavioral features (payment_to_income, num_previous_loans) | Task 2 |
| Train Logistic Regression scorecard + WoE | Task 3 (LR, no WoE library — uses StandardScaler instead; acceptable tradeoff) |
| FICO-style score 300–850 | Task 4 (scoring.py) |
| GET /api/credit-score/{member_key} | Tasks 5+6 |
| SHAP feature importance | Task 7 |
| vw_credit_score_distribution, vw_score_trend | Task 8 |
| Credit Score Dashboard (frontend) | Task 9 |

**Gap noted:** The evaluation doc mentions WoE/IV analysis as part of scorecard foundation. This plan uses StandardScaler + LogisticRegression directly instead of explicit WoE binning. This is a deliberate simplification (YAGNI) — WoE binning adds complexity without materially improving score quality at this stage. Can be added if interpretability in terms of scorecard point tables is required.

### No Placeholders Found

All code steps contain complete, runnable code. No "TBD" or "fill in details" left.

### Type Consistency

- `pd_to_credit_score` defined in Task 4 (`backend/core/scoring.py`), imported in Tasks 5, 7 ✓  
- `CreditScoreResponse` defined in Task 5, used as `response_model` in Task 6 ✓  
- `get_credit_score(member_key: str, db: Session) -> dict` defined in Task 5, called in Task 6 ✓  
- `artifact["feature_cols"]` and `artifact["thresholds"]` keys match what `train_scorecard.py` (Task 3) saves ✓  
- `ALL_FEATURES` list in `credit_score_service.py` matches `ALL_FEATURES` in `train_scorecard.py` ✓
