"""
Predict Engine Module
Loads the trained model artifact, generates a risk assessment for a given loan_number,
and upserts the result into core.risk_assessment.

Schema facts (from init_core.sql + transform_gold.sql):
- core.loans     PRIMARY KEY = listing_key (VARCHAR)
                 loan_number = VARCHAR e.g. "65928"
- gold.loan_features_v1  PRIMARY KEY = listing_key (VARCHAR)
                          loan_number = VARCHAR (same value)
- There is NO integer loan_id anywhere — input is loan_number as integer
  which matches loan_number VARCHAR via CAST
"""
import sys
import joblib
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text

from utils.db_connection import get_engine, load_config

# ── Resolve paths & config ───────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[1]
config     = load_config()

_ml_cfg    = config.get('ml', {})
MODEL_PATH = BASE_DIR / _ml_cfg.get('model_path', 'ml/models/loan_risk_model.pkl')


# ── Business rules ───────────────────────────────────────────────────────────

def get_risk_level(pd_val: float, thresholds: dict) -> str:
    """Map probability of default → risk label using thresholds from artifact."""
    if pd_val < thresholds['low']:
        return 'Low'
    elif pd_val <= thresholds['high']:
        return 'Medium'
    else:
        return 'High'


def recommend_loan(pd_val: float, thresholds: dict) -> dict:
    """Simulate loan recommendation (amount + term) based on risk level."""
    if pd_val < thresholds['low']:
        return {'recommended_amount': 15000, 'recommended_term': 36}
    elif pd_val <= thresholds['high']:
        return {'recommended_amount': 8000,  'recommended_term': 24}
    else:
        return {'recommended_amount': 3000,  'recommended_term': 12}


# ── Core prediction function ─────────────────────────────────────────────────

def predict_and_save(loan_number: int) -> dict | None:
    """
    Fetch features for a loan by loan_number, run the trained model,
    upsert result into core.risk_assessment, and return result dict.

    Args:
        loan_number: integer matching loan_number VARCHAR in core.loans
                     e.g. 65928 matches "65928" in the database

    Called by prediction_ui.py for real-time assessments.
    """
    print("=" * 55)
    print(f"  RISK ASSESSMENT  |  loan_number: {loan_number}")
    print("=" * 55)

    engine = get_engine()

    # ── 1. Validate loan_number exists in core.loans ─────
    # core.loans PRIMARY KEY = listing_key (VARCHAR)
    # loan_number is VARCHAR — cast input integer to text for comparison
    print("\n[1/5] Validating loan_number in core.loans...")
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT listing_key FROM core.loans "
                     "WHERE loan_number = CAST(:loan_number AS VARCHAR)"),
                {"loan_number": loan_number}
            ).fetchone()
        if row is None:
            print(f"  ERROR: loan_number {loan_number} not found in core.loans.")
            return None
        listing_key = row[0]
        print(f"  Confirmed. listing_key = {listing_key}")
    except Exception as e:
        print(f"  ERROR validating loan_number: {e}")
        raise

    # ── 2. Load model artifact ───────────────────────────
    print("\n[2/5] Loading model artifact...")
    if not MODEL_PATH.exists():
        print(f"  ERROR: Model not found at {MODEL_PATH}.")
        print("  Please run train_model.py first.")
        return None

    artifact = joblib.load(MODEL_PATH)

    if isinstance(artifact, dict) and 'pipeline' in artifact:
        pipeline     = artifact['pipeline']
        feature_cols = artifact['feature_cols']
        thresholds   = artifact.get('thresholds', {'low': 0.2, 'high': 0.4})
    else:
        print("  WARNING: Old model format — no feature_cols or thresholds saved.")
        print("  Re-run train_model.py to fix column alignment.")
        pipeline     = artifact
        feature_cols = None
        thresholds   = {'low': 0.2, 'high': 0.4}

    print(f"  Pipeline loaded. Features: {len(feature_cols) if feature_cols else 'unknown'} | "
          f"Thresholds: Low<{thresholds['low']} High>{thresholds['high']}")

    # ── 3. Fetch features from gold using listing_key ────
    # gold.loan_features_v1 PRIMARY KEY = listing_key (VARCHAR)
    # Use listing_key retrieved in step 1 for exact match
    print("\n[3/5] Fetching features from gold.loan_features_v1...")
    try:
        df = pd.read_sql(
            "SELECT * FROM gold.loan_features_v1 "
            "WHERE listing_key = %(listing_key)s",
            engine,
            params={'listing_key': listing_key}
        )
    except Exception as e:
        print(f"  ERROR fetching features: {e}")
        raise

    if df.empty:
        print(f"  ERROR: No features found for listing_key {listing_key}.")
        return None

    print(f"  Features fetched for listing_key: {listing_key}")

    # Drop all ID / key / target columns — not used in model
    drop_cols = [col for col in [
        'is_default', 'listing_key', 'member_key',
        'loan_number', 'loan_key'
    ] if col in df.columns]
    X = df.drop(columns=drop_cols)

    # Align columns exactly with training — prevents shape mismatch crash
    if feature_cols is not None:
        missing = [c for c in feature_cols if c not in X.columns]
        extra   = [c for c in X.columns    if c not in feature_cols]
        if missing:
            print(f"  WARNING: Missing columns (filling with 0): {missing}")
            for col in missing:
                X[col] = 0
        if extra:
            print(f"  Dropping unseen columns: {extra}")
        X = X[feature_cols]   # exact column order required by StandardScaler

    # Fill nulls — prevents NaN propagating through StandardScaler
    null_count = X.isnull().sum().sum()
    if null_count > 0:
        print(f"  Filling {null_count} null value(s) with column median.")
    X = X.fillna(X.median(numeric_only=True))

    # ── 4. Predict ───────────────────────────────────────
    print("\n[4/5] Running prediction...")
    probs  = pipeline.predict_proba(X)
    pd_val = float(probs[0, 1]) if probs.shape[1] > 1 else float(probs[0, 0])

    risk_level          = get_risk_level(pd_val, thresholds)
    risk_score_internal = int((1 - pd_val) * 100)
    recommendation      = recommend_loan(pd_val, thresholds)
    assessment_date     = datetime.now(timezone.utc)

    print(f"\n  Probability of Default : {pd_val:.4f}")
    print(f"  Risk Level             : {risk_level}")
    print(f"  Internal Risk Score    : {risk_score_internal}")
    print(f"  Recommended Amount     : ${recommendation['recommended_amount']:,}")
    print(f"  Recommended Term       : {recommendation['recommended_term']} months")

    # ── 5. Upsert into core.risk_assessment ──────────────
    # Uses listing_key (VARCHAR) as the unique identifier
    # loan_number stored as VARCHAR to match core.loans schema
    print("\n[5/5] Saving to core.risk_assessment...")

    try:
        with engine.begin() as conn:
            deleted = conn.execute(
                text("DELETE FROM core.risk_assessment "
                     "WHERE listing_key = :listing_key"),
                {"listing_key": listing_key}
            ).rowcount
        if deleted:
            print(f"  Replaced {deleted} existing record(s) for listing_key {listing_key}.")
    except Exception as e:
        print(f"  WARNING: Could not delete existing records: {e}")

    result_df = pd.DataFrame([{
        'listing_key'            : listing_key,
        'loan_number'            : str(loan_number),
        'probability_of_default' : pd_val,
        'risk_score_internal'    : risk_score_internal,
        'risk_level'             : risk_level,
        'recommended_amount'     : recommendation['recommended_amount'],
        'recommended_term'       : recommendation['recommended_term'],
        'assessment_date'        : assessment_date
    }])

    try:
        result_df.to_sql(
            name='risk_assessment',
            schema='core',
            con=engine,
            if_exists='append',
            index=False
        )
        print(f"  Saved successfully for listing_key: {listing_key}")
    except Exception as e:
        print(f"  ERROR saving assessment: {e}")
        raise

    print("\n" + "=" * 55)
    print("  ASSESSMENT COMPLETE")
    print("=" * 55)

    return {
        'listing_key'            : listing_key,
        'loan_number'            : loan_number,
        'probability_of_default' : pd_val,
        'risk_level'             : risk_level,
        'risk_score_internal'    : risk_score_internal,
        'recommended_amount'     : recommendation['recommended_amount'],
        'recommended_term'       : recommendation['recommended_term'],
        'assessment_date'        : assessment_date.isoformat()
    }


# ── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            input_loan_number = int(sys.argv[1])
            predict_and_save(input_loan_number)
        except ValueError:
            print("ERROR: Please provide a valid integer loan_number.")
            print("Usage: python predict_engine.py <loan_number>")
            print("Example: python predict_engine.py 65928")
    else:
        print("Usage: python predict_engine.py <loan_number>")
        print("Example: python predict_engine.py 65928")