# ML Pipeline v4 — Two-Stage Credit Scoring

## Overview

v4 resolves a fundamental flaw in v3: the application form asked users to self-report their credit score, which was then fed as the dominant input to the Scorecard model that was supposed to *compute* a credit score. The score output was essentially an echo of the user input.

**v4 Solution — Two-stage pipeline:**

```
User submits form (no credit score, no DTI)
       │
       ▼
  Stage 1: Scorecard LR (22 features)
       │  → P₁(default)
       │  → credit_score_computed (300–850, FICO PDO formula)
       ▼
  Stage 2: LightGBM (26 features)
       │  → P₂(default) = risk probability
       │  → risk_level (Low/Medium/High)
       ▼
  Evaluate response to user:
    - credit_score_computed (Stage 1)
    - default_probability (Stage 2)
    - suggested_amount + suggested_term
```

---

## Feature Comparison (v3 → v4)

| Feature | v3 Scorecard | v3 LightGBM | v4 Stage 1 | v4 Stage 2 | Notes |
|---------|:---:|:---:|:---:|:---:|-------|
| credit_score_midpoint | ✓ | ✓ | ✗ | ✗ | Removed: self-reported, dominated Stage 1 (+14.5 pts/std) |
| rating_ordinal | ✓ | ✓ | ✗ | ✗ | Removed: derived from credit_score (multicollinearity) |
| payment_to_income | ✓ | ✗ | ✗ | ✗ | Removed: exact duplicate of debt_to_income_ratio |
| has_bad_debt | ✓ | ✓ | ✗ | ✗ | Removed: 18/300k positive samples (zero variance) |
| listing_category | ✗ | ✓ | ✗ | ✗ | Removed: was hardcoded constant=1 (zero gain) |
| **credit_score_computed** | ✗ | ✗ | ✗ | **✓** | NEW: Stage 1 OOF output (300–850) |
| **loan_type** | ✗ | ✗ | **✓** | **✓** | NEW: 1=Cash, 0=Revolving (from NAME_CONTRACT_TYPE) |
| debt_to_income_ratio | ✓ | ✓ | ✓ | ✓ | Now HC-style: (loan_amount/term)/monthly_income |
| occupation_type | OrdinalEnc | OrdinalEnc | **TargetEnc** | OrdinalEnc | Stage 1: TargetEncoder encodes by mean default rate |
| All other features | ✓ | ✓ | ✓ | ✓ | Unchanged |

---

## Stage 1 — Scorecard LR (scorecard_lr_v4)

**File:** `machinelearning/ml/train_scorecard.py`  
**Artifact:** `machinelearning/ml/models/scorecard_model.pkl`  
**OOF output:** `machinelearning/ml/models/oof_stage1.csv`

### Features (22 total)

**Numeric (20):**

| Feature | Source | Description |
|---------|--------|-------------|
| debt_to_income_ratio | computed | HC-style: (loan_amount/term)/monthly_income |
| loan_amount_to_income | computed | loan_amount/(monthly_income×12) |
| log_monthly_income | computed | ln(1+monthly_income) |
| is_homeowner_flag | form | Binary: 1=owns home |
| income_verifiable_flag | form | Binary: 1=has verifiable income |
| high_dti_flag | computed | 1 if HC-DTI > p75 (~2.683) |
| num_previous_loans | DB | Prior approved applications |
| previous_default_rate | DB | Fraction of prior apps rejected |
| num_bureau_records | form | Total credit inquiries |
| num_active_credit | form | Currently active credit lines |
| total_overdue_amount | form | Total overdue balance (USD) |
| max_credit_overdue_days | form | Worst overdue duration (days) |
| years_employed | form | Employment tenure (0–50) |
| age_years | form | Applicant age (18–100) |
| gender_male_flag | form | Binary: 1=male |
| education_ordinal | form | 1 (Lower secondary) to 5 (Academic degree) |
| cnt_children | form | Number of children |
| cnt_fam_members | form | Total family members |
| is_married_flag | form | Binary: 1=married |
| loan_type | from loan_purpose | 1=Cash, 0=Revolving |

**Categorical (2):**

| Feature | Encoder | Description |
|---------|---------|-------------|
| employment_status_grouped | OrdinalEncoder | Employed/Self-employed/Retired/Not employed/Other/Unknown |
| occupation_type | **TargetEncoder** | Encodes by mean default rate per HC occupation category |

### FICO PDO Formula

```
logit = ln(P(default) / (1 - P(default)))
score = 600 - 28.854 × (logit - (-3.912))
score = clip(round(score), 300, 850)
```

Parameters: `base_score=600`, `base_odds_good=50`, `PDO=20`, `factor=PDO/ln(2)=28.854`

### v4 Training Results

| Metric | Value |
|--------|-------|
| OOF AUC (5-fold) | 0.6738 |
| Held-out AUC | 0.6821 |
| Score range (OOF) | 422 – 723 |
| Dataset | 300,360 rows, 8.07% default rate |

**Key feature contributions (pts/std):**

| Feature | pts/std | Direction |
|---------|---------|-----------|
| num_bureau_records | +8.06 | More records → lower risk |
| years_employed | +7.20 | More experience → lower risk |
| education_ordinal | +6.85 | Higher education → lower risk |
| age_years | +6.23 | Older → lower risk |
| num_active_credit | -11.66 | More active credit → higher risk |
| previous_default_rate | -6.11 | More rejections → higher risk |
| gender_male_flag | -4.10 | Male → slightly higher risk (HC data) |
| loan_type | -3.75 | Cash loans → higher risk than Revolving |

> Note: `occupation_type` pts/std is large (-69.66) because TargetEncoder output scale (~0.05 std) is not normalized by StandardScaler in the ColumnTransformer. The coefficient is large to compensate for the small input range. The model prediction is correct; only the display metric is misleading for this feature.

---

## Stage 2 — Customer Risk Model LightGBM (customer_lgbm_v4)

**File:** `machinelearning/ml/retrain_customer_model.py`  
**Artifact:** `machinelearning/ml/models/customer_risk_model.pkl`

### Features (26 total)

**Numeric (24):** All Stage 1 features minus Stage 1 aliases, plus:
- `monthly_income`, `loan_amount`, `term` (raw loan parameters)
- `dti` (HC-style, same as `debt_to_income_ratio` in Stage 1)
- `credit_score_computed` — **Stage 1 OOF output (FICO 300–850)**
- `loan_type` — 1=Cash, 0=Revolving

**Categorical (2):**
- `employment_status` (OrdinalEncoder, 5 categories)
- `occupation_type` (OrdinalEncoder, 19 categories)

### OOF Training Procedure

Stage 2 is trained on Stage 1's **out-of-fold** predictions to avoid data leakage:

```
1. Split gold data → 5 folds
2. For each fold k:
   a. Fit Stage 1 on folds 1..k-1,k+1..5
   b. Predict P₁(default) on fold k → OOF[k]
3. Convert OOF probs → credit_score_computed via FICO PDO
4. Fit final Stage 1 on all data
5. Train Stage 2 on [all features + credit_score_computed from step 3]
```

At inference: final Stage 1 runs first, then Stage 2 uses that output.

### v4 Training Results

| Metric | Value |
|--------|-------|
| ROC-AUC (held-out) | 0.7026 |
| Dataset | 300,360 rows (after OOF merge) |
| Thresholds | low=0.20, high=0.40 |

**Top feature importances:**

| Feature | Importance |
|---------|-----------|
| age_years | 3,518 |
| loan_amount | 3,101 |
| credit_score_computed | 2,898 |
| years_employed | 2,871 |
| dti | 2,865 |

`credit_score_computed` ranks #3 — contributing independently from all other features.

---

## Inference Flow (Backend)

```python
# 1. User submits form → ApplicationCreate (no credit_score, no dti)
payload = ApplicationCreate(
    monthly_income=5000, loan_amount=10000, term=36,
    loan_purpose="Personal", occupation_type="IT staff",
    years_employed=3, income_verifiable_flag=True,
    ...
)

# 2. Stage 1: compute credit_score_computed
stage1_features = build_stage1_input(payload, stage1_artifact, previous_applications)
credit_score_computed, stage1_prob = run_stage1(...)
# e.g. credit_score_computed=555, stage1_prob=0.086

# 3. Stage 2: predict risk
stage2_features = build_model_input(payload, stage2_artifact,
                                    credit_score_computed=555,
                                    previous_applications=...)
prob = stage2_pipeline.predict_proba(row)[0, 1]
# e.g. prob=0.06, risk_level="Low"

# 4. Loan suggestion (binary search also runs both stages)
suggestion = compute_suggestion(payload, stage1, stage2, ...)
```

**Key: HC-style DTI** = `(loan_amount / term) / monthly_income` — NOT user-input DTI ratio.  
At monthly_income=5000, loan_amount=10000, term=36: DTI = (10000/36)/5000 = 0.0556.

---

## loan_purpose → loan_type Mapping

| loan_purpose (form) | loan_type (model) |
|---------------------|:-----------------:|
| Education | 1 (Cash) |
| Home | 1 (Cash) |
| Car | 1 (Cash) |
| Business | 1 (Cash) |
| Medical | 1 (Cash) |
| Personal | 1 (Cash) |
| **Revolving** | **0 (Revolving)** |

---

## Retraining Guide

**Prerequisites:** ETL pipeline already ran, `gold.hc_features_v1` contains `loan_type` column.

```bash
# From project root
source venv/bin/activate

# Step 1 — (only if gold table needs to be rebuilt)
python -m machinelearning.etl.etl_gold

# Step 2 — Train Stage 1, generates OOF predictions
python -m machinelearning.ml.train_scorecard

# Step 3 — Train Stage 2 (requires oof_stage1.csv from Step 2)
python -m machinelearning.ml.retrain_customer_model
```

**Outputs:**
- `machinelearning/ml/models/scorecard_model.pkl` — Stage 1 artifact
- `machinelearning/ml/models/oof_stage1.csv` — OOF predictions (training artifact only)
- `machinelearning/ml/models/customer_risk_model.pkl` — Stage 2 artifact

**After retraining:** Restart the backend — artifacts are loaded lazily on first request.

---

## Fixes from v3

| Issue (v3) | Fix (v4) |
|------------|----------|
| credit_score self-reported on form → echoed as output | Removed from form; Stage 1 computes it independently |
| high_dti_flag always 0 in inference (form DTI 0–1 vs training HC-style 2.68 p75) | DTI now computed HC-style at inference |
| payment_to_income = debt_to_income_ratio (exact duplicate) | payment_to_income removed |
| listing_category hardcoded=1 (zero variance, gain=0) | Removed; replaced by loan_type from NAME_CONTRACT_TYPE |
| has_bad_debt: 18/300k positive (zero signal) | Removed from both models |
| rating_ordinal multicollinear with credit_score_midpoint | Removed |
| occupation_type OrdinalEncoder: arbitrary ordinals → near-zero LR coef | Stage 1 uses TargetEncoder |
