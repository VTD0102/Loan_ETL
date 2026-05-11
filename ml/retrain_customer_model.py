"""
Retrain model using only 8 features available from customer loan application form.
Saves artifact to ml/models/customer_risk_model.pkl.

Run from project root:
    python -m ml.retrain_customer_model
"""
import sys
from pathlib import Path

# ── Path fix — allow running from any working directory ─────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from utils.db_connection import get_engine

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"

# ── Risk thresholds — must stay in sync with predict_customer.py ─────────────
LOW_THRESHOLD  = 0.2
HIGH_THRESHOLD = 0.4

# ── Feature groups ───────────────────────────────────────────────────────────
NUMERIC_FEATURES     = [
    "monthly_income",
    "loan_amount",
    "term",
    "dti",
    "is_homeowner",
    "listing_category",
    "credit_score",
]
CATEGORICAL_FEATURES = ["employment_status"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# ── Query from silver layer ───────────────────────────────────────────────────
# FIX: correct column names from transform_silver.sql:
#   is_borrower_homeowner  BOOLEAN  (not is_homeowner / not 'Yes' string)
#   listing_category_numeric INTEGER (not listing_category_id)
#   employment_status      VARCHAR  ✅
SILVER_QUERY = """
SELECT
    stated_monthly_income
        AS monthly_income,
    loan_original_amount
        AS loan_amount,
    term,
    COALESCE(employment_status, 'Other')
        AS employment_status,
    debt_to_income_ratio
        AS dti,
    CASE WHEN is_borrower_homeowner IS TRUE THEN 1 ELSE 0 END
        AS is_homeowner,
    listing_category_numeric
        AS listing_category,
    (credit_score_range_upper + credit_score_range_lower) / 2.0
        AS credit_score,
    is_default
FROM silver.prosper_loans_cleansed
WHERE stated_monthly_income    IS NOT NULL
  AND loan_original_amount     IS NOT NULL
  AND debt_to_income_ratio     IS NOT NULL
  AND credit_score_range_upper IS NOT NULL
  AND credit_score_range_lower IS NOT NULL
  AND term                     IS NOT NULL
"""


def train():
    print("=" * 55)
    print("  CUSTOMER RISK MODEL — RETRAIN (8 features)")
    print("=" * 55)

    # ── 1. Connect & fetch ───────────────────────────────
    print("\n[1/6] Connecting to database...")
    engine = get_engine()

    print("[2/6] Fetching data from silver.prosper_loans_cleansed...")
    try:
        df = pd.read_sql(SILVER_QUERY, engine)
    except Exception as e:
        print(f"  ERROR fetching data: {e}")
        return

    if df.empty:
        print("  ERROR: No data returned from silver layer.")
        return

    print(f"  Rows fetched: {len(df)}")

    # ── 2. Clean ─────────────────────────────────────────
    print("\n[3/6] Cleaning data...")
    before = len(df)
    df = df.dropna(subset=ALL_FEATURES + ["is_default"])
    after = len(df)
    print(f"  Dropped {before - after} rows with nulls.")
    print(f"  Rows remaining: {after}")
    print(f"  Default rate  : {df['is_default'].mean():.2%}")
    print(f"  Employment status values: {sorted(df['employment_status'].unique().tolist())}")

    X = df[ALL_FEATURES]
    y = df["is_default"]

    # ── 3. Split ─────────────────────────────────────────
    print("\n[4/6] Splitting 80/20 (stratified by is_default)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )
    print(f"  Train: {len(X_train)} rows | Test: {len(X_test)} rows")

    # ── 4. Build pipeline ────────────────────────────────
    print("\n[5/6] Building pipeline...")

    # FIX: OneHotEncoder instead of OrdinalEncoder
    # OrdinalEncoder implies ordering (A < B < C) which is wrong for employment_status
    # OneHotEncoder creates a binary column per category — correct for nominal data
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(
                handle_unknown="ignore",   # unseen categories at predict time → all zeros
                sparse_output=False        # return dense array, easier to work with
            ), CATEGORICAL_FEATURES),
        ],
        remainder="drop"
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            min_samples_split=10,
            class_weight="balanced",    # handles 85/15 imbalance
            random_state=42,
            n_jobs=-1,
        )),
    ])

    print("  Pipeline: StandardScaler + OneHotEncoder → RandomForest(200 trees)")

    # ── 5. Train ─────────────────────────────────────────
    print("\n[6/6] Training...")
    pipeline.fit(X_train, y_train)

    # ── 6. Evaluate ──────────────────────────────────────
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)

    print(f"\n  --- Model Evaluation (Test Set) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(classification_report(
        y_test, y_pred,
        target_names=["No Default", "Default"]
    ))

    # ── 7. Save artifact ─────────────────────────────────
    # FIX: save feature_names_out (expanded after OneHotEncoder)
    # so predict_customer.py can align columns correctly at inference time
    ohe_feature_names = (
        pipeline
        .named_steps["preprocessor"]
        .named_transformers_["cat"]
        .get_feature_names_out(CATEGORICAL_FEATURES)
        .tolist()
    )
    feature_names_out = NUMERIC_FEATURES + ohe_feature_names

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "pipeline"         : pipeline,
        "feature_cols"     : ALL_FEATURES,        # 8 raw input columns (for form validation)
        "feature_names_out": feature_names_out,   # expanded columns after preprocessing
        "thresholds"       : {
            "low" : LOW_THRESHOLD,
            "high": HIGH_THRESHOLD,
        },
    }

    try:
        joblib.dump(artifact, MODEL_PATH)
        print(f"  Artifact saved → {MODEL_PATH}")
        print(f"  Keys: pipeline | feature_cols ({len(ALL_FEATURES)}) "
              f"| feature_names_out ({len(feature_names_out)}) | thresholds")
    except Exception as e:
        print(f"  ERROR saving artifact: {e}")
        return

    print("\n" + "=" * 55)
    print("  RETRAIN COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    train()