"""
Retrain model using only 8 features available from customer loan application form.
Replaces loan_risk_model.pkl (34 Prosper-internal features) with
customer_risk_model.pkl (8 customer-provided features).

Run: python ml/retrain_customer_model.py
"""
import joblib
import pandas as pd
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

from utils.db_connection import get_engine, load_config

BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"

# Thresholds — must stay in sync with ml_service.py
LOW_THRESHOLD  = 0.2
HIGH_THRESHOLD = 0.4

# Columns fetched from gold layer (Prosper names → customer form names)
SILVER_QUERY = """
SELECT
    stated_monthly_income            AS monthly_income,
    loan_original_amount             AS loan_amount,
    term,
    employment_status,
    debt_to_income_ratio             AS dti,
    CASE WHEN is_homeowner = 'Yes' THEN 1 ELSE 0 END AS is_homeowner,
    listing_category_id              AS listing_category,
    (credit_score_range_upper + credit_score_range_lower) / 2.0 AS credit_score,
    is_default
FROM silver.prosper_loans_cleansed
WHERE stated_monthly_income IS NOT NULL
  AND loan_original_amount  IS NOT NULL
  AND debt_to_income_ratio  IS NOT NULL
  AND credit_score_range_upper IS NOT NULL
"""

NUMERIC_FEATURES     = ["monthly_income", "loan_amount", "term", "dti",
                         "is_homeowner", "listing_category", "credit_score"]
CATEGORICAL_FEATURES = ["employment_status"]
ALL_FEATURES         = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def train():
    print("=" * 55)
    print("  CUSTOMER RISK MODEL — RETRAIN (8 features)")
    print("=" * 55)

    engine = get_engine()

    print("\n[1/6] Fetching data from silver layer...")
    df = pd.read_sql(SILVER_QUERY, engine)
    print(f"  Rows: {len(df)}")

    print("\n[2/6] Cleaning data...")
    df = df.dropna(subset=ALL_FEATURES + ["is_default"])
    df["employment_status"] = df["employment_status"].fillna("Other")
    print(f"  Rows after dropna: {len(df)}")
    print(f"  Default rate: {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES]
    y = df["is_default"]

    print("\n[3/6] Splitting 80/20 (stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\n[4/6] Building pipeline...")
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
         CATEGORICAL_FEATURES),
    ])

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            min_samples_split=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])

    print("\n[5/6] Training...")
    pipeline.fit(X_train, y_train)

    print("\n[6/6] Evaluating on test set...")
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    auc    = roc_auc_score(y_test, y_prob)

    print(f"  ROC-AUC : {auc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["No Default", "Default"]))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "pipeline"    : pipeline,
        "feature_cols": ALL_FEATURES,
        "thresholds"  : {"low": LOW_THRESHOLD, "high": HIGH_THRESHOLD},
    }
    joblib.dump(artifact, MODEL_PATH)
    print(f"\n  Saved → {MODEL_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    train()
