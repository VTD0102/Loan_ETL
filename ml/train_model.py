"""
Train Model Module
Trains a RandomForest loan default risk model using features from gold.loan_features_v1.
Saves the trained pipeline + feature columns to ml/models/loan_risk_model.pkl.
"""
import pandas as pd
import joblib
from pathlib import Path
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, classification_report

from utils.db_connection import get_engine, load_config

# ── Resolve paths & config ───────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[1]
config     = load_config()

# Model path from settings.yaml ml section — falls back to default if missing
_ml_cfg    = config.get('ml', {})
MODEL_PATH = BASE_DIR / _ml_cfg.get('model_path', 'ml/models/loan_risk_model.pkl')

# Risk thresholds from settings.yaml — centralised so predict_engine stays in sync
_thresholds    = _ml_cfg.get('risk_thresholds', {})
LOW_THRESHOLD  = float(_thresholds.get('low',  0.2))
HIGH_THRESHOLD = float(_thresholds.get('high', 0.4))


def train_model():
    print("=" * 55)
    print("  LOAN RISK MODEL — TRAINING")
    print("=" * 55)

    # ── 1. Connect & fetch ───────────────────────────────
    print("\n[1/6] Connecting to database...")
    # Uses shared cached engine from db_connection.py — no duplicate connection
    engine = get_engine()

    print("[2/6] Fetching data from gold.loan_features_v1...")
    try:
        df = pd.read_sql("SELECT * FROM gold.loan_features_v1", engine)
    except Exception as e:
        print(f"  ERROR fetching data: {e}")
        return

    if df.empty:
        print("  ERROR: No data found in gold.loan_features_v1.")
        return

    print(f"  Rows fetched: {len(df)}")

    # ── 2. Validate target column ────────────────────────
    target_col = 'is_default'
    if target_col not in df.columns:
        print(f"  ERROR: Target column '{target_col}' not found.")
        print(f"  Available columns: {df.columns.tolist()}")
        return

    # ── 3. Prepare features ──────────────────────────────
    print("\n[3/6] Preparing features...")

    # Drop target + ID columns before training
    drop_cols = [col for col in [target_col, 'loan_id'] if col in df.columns]
    X = df.drop(columns=drop_cols)

    # Keep only numeric columns — prevents StandardScaler crash on string cols
    non_numeric = X.select_dtypes(exclude=['number']).columns.tolist()
    if non_numeric:
        print(f"  Dropping non-numeric columns: {non_numeric}")
    X = X.select_dtypes(include=['number'])

    # Fill nulls with column median — prevents NaN propagation through scaler
    null_cols = X.columns[X.isnull().any()].tolist()
    if null_cols:
        print(f"  Filling nulls with median in: {null_cols}")
    X = X.fillna(X.median(numeric_only=True))

    y = df[target_col]

    print(f"  Features used ({len(X.columns)}): {X.columns.tolist()}")
    print(f"  Target distribution:\n"
          f"{y.value_counts(normalize=True).rename('ratio').to_string()}")

    # ── 4. Train / test split ────────────────────────────
    print("\n[4/6] Splitting data 80/20 (stratified)...")
    # CRITICAL: split BEFORE fitting — evaluating on training data inflates metrics
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y        # preserve default/non-default ratio in both sets
    )
    print(f"  Train: {len(X_train)} rows | Test: {len(X_test)} rows")

    # ── 5. Build & train pipeline ────────────────────────
    print("\n[5/6] Training pipeline (StandardScaler → RandomForest)...")
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(
            n_estimators=200,       # more trees = more stable predictions
            max_depth=15,           # prevents overfitting deep trees
            min_samples_leaf=5,     # each leaf needs at least 5 samples
            min_samples_split=10,   # need 10 samples to split a node
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        ))
    ])
    pipeline.fit(X_train, y_train)

    # ── 6. Evaluate on TEST set ──────────────────────────
    print("\n[6/6] Evaluating on test set...")
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_prob)
    f1  = f1_score(y_test, y_pred)

    print("\n  --- Model Evaluation (Test Set) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(f"  F1-Score: {f1:.4f}")
    print(f"\n  Risk thresholds — Low: <{LOW_THRESHOLD} | High: >{HIGH_THRESHOLD}")
    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred,target_names=['No Default', 'Default']))

    # ── 7. Save artifact ─────────────────────────────────
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Save pipeline + feature_cols + thresholds together
    # predict_engine.py loads ALL three to guarantee alignment
    artifact = {
        'pipeline'    : pipeline,
        'feature_cols': X.columns.tolist(),
        'thresholds'  : {
            'low' : LOW_THRESHOLD,
            'high': HIGH_THRESHOLD,
        }
    }

    try:
        joblib.dump(artifact, MODEL_PATH)
        print(f"\n  Artifact saved → {MODEL_PATH}")
        print(f"  Keys: pipeline | feature_cols ({len(X.columns)} cols) | thresholds")
    except Exception as e:
        print(f"  ERROR saving model: {e}")
        return

    print("\n" + "=" * 55)
    print("  TRAINING COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    train_model()