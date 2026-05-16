"""
Retrain customer risk model (Random Forest) — v6.0

Random Forest version for customer risk prediction.

Design:
  - Keep current 28 features.
  - Tune multiple RandomForest configurations.
  - Select best config by validation ROC-AUC.
  - Retrain final model on train + val.
  - Evaluate on untouched test set.
  - Save artifact as:
        {
            "pipeline": pipeline,
            "thresholds": {"low": 0.2, "high": 0.4},
            ...
        }

Why Random Forest:
  - Strong baseline for tabular data.
  - Less sensitive than boosting.
  - Useful benchmark against XGBoost / LightGBM.
  - Easier to explain with feature importance.

Source : gold.hc_features_v1
Output : ml/models/customer_risk_model_rf.pkl

Run from project root:
    python -m ml.retrain_customer_model
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


# ─────────────────────────────────────────────────────────────────────────────
# Paths & config
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from utils.db_connection import get_engine  # noqa: E402


# Để không ghi đè model chính XGBoost/LightGBM, bản Random Forest lưu riêng.
# Nếu muốn biến RF thành model chính, đổi thành:
# MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"
MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model_rf.pkl"

MODEL_VERSION = "customer_rf_v6.0_tuned"

LOW_THRESHOLD = 0.2
HIGH_THRESHOLD = 0.4

RANDOM_STATE = 42
TARGET_RECALL = 0.75


# ─────────────────────────────────────────────────────────────────────────────
# Random Forest candidates
# ─────────────────────────────────────────────────────────────────────────────

RF_CANDIDATES = [
    {
        "name": "rf_balanced_depth10_leaf50",
        "n_estimators": 500,
        "max_depth": 10,
        "min_samples_leaf": 50,
        "min_samples_split": 100,
        "max_features": "sqrt",
        "class_weight": "balanced",
    },
    {
        "name": "rf_balanced_depth14_leaf30",
        "n_estimators": 600,
        "max_depth": 14,
        "min_samples_leaf": 30,
        "min_samples_split": 60,
        "max_features": "sqrt",
        "class_weight": "balanced",
    },
    {
        "name": "rf_balanced_depth18_leaf20",
        "n_estimators": 700,
        "max_depth": 18,
        "min_samples_leaf": 20,
        "min_samples_split": 40,
        "max_features": "sqrt",
        "class_weight": "balanced",
    },
    {
        "name": "rf_subsample_depth14_leaf30",
        "n_estimators": 600,
        "max_depth": 14,
        "min_samples_leaf": 30,
        "min_samples_split": 60,
        "max_features": 0.7,
        "class_weight": "balanced_subsample",
    },
    {
        "name": "rf_subsample_depth18_leaf20",
        "n_estimators": 700,
        "max_depth": 18,
        "min_samples_leaf": 20,
        "min_samples_split": 40,
        "max_features": 0.7,
        "class_weight": "balanced_subsample",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# SQL query
# ─────────────────────────────────────────────────────────────────────────────

_QUERY = """
SELECT
    -- ── Core loan features (8) ────────────────────────────────────────────
    stated_monthly_income                                       AS monthly_income,
    loan_original_amount                                        AS loan_amount,
    term,
    employment_status_grouped                                   AS employment_status,
    debt_to_income_ratio                                        AS dti,
    is_homeowner_flag                                           AS is_homeowner,
    1                                                           AS listing_category,
    credit_score_midpoint                                       AS credit_score,

    -- ── Employment/profile ────────────────────────────────────────────────
    years_employed,
    occupation_type,

    -- ── Bureau / credit history features ─────────────────────────────────
    -- NOTE: verify these are available BEFORE loan approval (no leakage)
    num_previous_loans,
    previous_default_rate,
    num_bureau_records,
    num_active_credit,
    total_overdue_amount,
    max_credit_overdue_days,
    has_bad_debt,

    -- ── Derived flags/features ────────────────────────────────────────────
    income_verifiable_flag,
    high_dti_flag,
    rating_ordinal,
    log_monthly_income,
    loan_amount_to_income,

    -- ── Demographics ──────────────────────────────────────────────────────
    age_years,
    gender_male_flag,
    education_ordinal,
    cnt_children,
    cnt_fam_members,
    is_married_flag,

    is_default
FROM gold.hc_features_v1
WHERE credit_score_midpoint   IS NOT NULL
  AND stated_monthly_income   IS NOT NULL
  AND loan_original_amount    IS NOT NULL
  AND debt_to_income_ratio    IS NOT NULL
  AND years_employed          IS NOT NULL
  AND occupation_type         IS NOT NULL
"""


# ─────────────────────────────────────────────────────────────────────────────
# Feature definitions
# ─────────────────────────────────────────────────────────────────────────────

NUMERIC_FEATURES = [
    # Core
    "monthly_income",
    "loan_amount",
    "term",
    "dti",
    "is_homeowner",
    "listing_category",
    "credit_score",

    # Employment/profile
    "years_employed",

    # Bureau/history
    "num_previous_loans",
    "previous_default_rate",
    "num_bureau_records",
    "num_active_credit",
    "total_overdue_amount",
    "max_credit_overdue_days",
    "has_bad_debt",

    # Derived
    "income_verifiable_flag",
    "high_dti_flag",
    "rating_ordinal",
    "log_monthly_income",
    "loan_amount_to_income",

    # Demographics
    "age_years",
    "gender_male_flag",
    "education_ordinal",
    "cnt_children",
    "cnt_fam_members",
    "is_married_flag",
]

CATEGORICAL_FEATURES = [
    "employment_status",
    "occupation_type",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

OCCUPATION_CATEGORIES = [
    "Accountants",
    "Cleaning staff",
    "Cooking staff",
    "Core staff",
    "Drivers",
    "HR staff",
    "High skill tech staff",
    "IT staff",
    "Laborers",
    "Low-skill Laborers",
    "Managers",
    "Medicine staff",
    "Private service staff",
    "Realty agents",
    "Sales staff",
    "Secretaries",
    "Security staff",
    "Waiters/barmen staff",
    "Unknown",
]

EMPLOYMENT_CATEGORIES = [
    "Employed",
    "Self-employed",
    "Retired",
    "Not employed",
    "Other/Unknown",
]


# ─────────────────────────────────────────────────────────────────────────────
# Main training function
# ─────────────────────────────────────────────────────────────────────────────

def train() -> None:
    """
    Train Random Forest customer risk model and save artifact.

    Process:
      1. Validate data
      2. Load gold.hc_features_v1
      3. Split 70/10/20 train/val/test
      4. Fit preprocessor on train
      5. Tune Random Forest configs on validation ROC-AUC
      6. Retrain final model on train + val
      7. Evaluate on untouched test set
      8. Save artifact
    """

    _run_validation_safely()

    print("\n" + "=" * 64)
    print("  CUSTOMER RISK MODEL — RETRAIN (Random Forest v6.0)")
    print("=" * 64)

    # ── 1. Fetch data ────────────────────────────────────────────────────
    print("\n[1/8] Fetching data from gold.hc_features_v1...")
    engine = get_engine()
    df = pd.read_sql(_QUERY, engine)

    print(f"  Rows     : {len(df):,}")
    print(f"  Features : {len(ALL_FEATURES)}")

    # ── 2. Clean data ────────────────────────────────────────────────────
    print("\n[2/8] Cleaning data...")

    df["employment_status"] = df["employment_status"].fillna("Other/Unknown")
    df["occupation_type"] = df["occupation_type"].fillna("Unknown")

    df = df.dropna(
        subset=[
            "is_default",
            "monthly_income",
            "loan_amount",
            "credit_score",
        ]
    )

    print(f"  Rows after dropna : {len(df):,}")
    print(f"  Default rate      : {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES].copy()
    y = df["is_default"].astype(int).copy()

    feature_defaults = _feature_defaults(X)
    dti_p75 = float(df["dti"].quantile(0.75))

    # ── 3. Split train / val / test ──────────────────────────────────────
    print("\n[3/8] Splitting 70/10/20 (train/val/test, stratified)...")

    X_temp, X_test, y_temp, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X_temp,
        y_temp,
        test_size=0.125,
        random_state=RANDOM_STATE,
        stratify=y_temp,
    )

    print(f"  Train : {len(X_train):,}")
    print(f"  Val   : {len(X_val):,}")
    print(f"  Test  : {len(X_test):,}")

    # ── 4. Preprocess train/val/test ─────────────────────────────────────
    print("\n[4/8] Building and fitting preprocessor...")

    preprocessor = build_preprocessor()
    preprocessor.fit(X_train)

    X_train_enc = preprocessor.transform(X_train)
    X_val_enc = preprocessor.transform(X_val)

    print(f"  Encoded train shape : {X_train_enc.shape}")
    print(f"  Encoded val shape   : {X_val_enc.shape}")

    # ── 5. Tune Random Forest configs ────────────────────────────────────
    print("\n[5/8] Tuning Random Forest candidates...")

    tuning_results = []

    best_config = None
    best_val_auc = -1.0
    best_val_pr_auc = -1.0
    best_val_brier = None

    for candidate in RF_CANDIDATES:
        print("\n" + "-" * 64)
        print(f"  Training candidate: {candidate['name']}")

        clf = build_rf_classifier(candidate)

        clf.fit(X_train_enc, y_train)

        val_prob = clf.predict_proba(X_val_enc)[:, 1]

        val_auc = roc_auc_score(y_val, val_prob)
        val_pr_auc = average_precision_score(y_val, val_prob)
        val_brier = brier_score_loss(y_val, val_prob)

        result = {
            "name": candidate["name"],
            "params": _rf_params_for_artifact(candidate),
            "val_roc_auc": float(val_auc),
            "val_pr_auc": float(val_pr_auc),
            "val_brier": float(val_brier),
        }

        tuning_results.append(result)

        print(
            f"  Candidate result | "
            f"val_auc={val_auc:.4f} | "
            f"val_pr_auc={val_pr_auc:.4f} | "
            f"val_brier={val_brier:.4f}"
        )

        is_better = (
            val_auc > best_val_auc
            or (
                abs(val_auc - best_val_auc) < 1e-6
                and val_pr_auc > best_val_pr_auc
            )
        )

        if is_better:
            best_config = candidate
            best_val_auc = float(val_auc)
            best_val_pr_auc = float(val_pr_auc)
            best_val_brier = float(val_brier)

    if best_config is None:
        raise RuntimeError("No Random Forest candidate was successfully trained.")

    print("\n" + "=" * 64)
    print("  RANDOM FOREST TUNING SUMMARY")
    print("=" * 64)

    for result in sorted(tuning_results, key=lambda x: x["val_roc_auc"], reverse=True):
        print(
            f"  {result['name']:<32} | "
            f"val_auc={result['val_roc_auc']:.4f} | "
            f"val_pr_auc={result['val_pr_auc']:.4f} | "
            f"val_brier={result['val_brier']:.4f}"
        )

    print("\n  Selected candidate:")
    print(f"  name       : {best_config['name']}")
    print(f"  val ROC-AUC: {best_val_auc:.4f}")
    print(f"  val PR-AUC : {best_val_pr_auc:.4f}")
    print(f"  val Brier  : {best_val_brier:.4f}")

    # ── 6. Retrain final model on train + val ────────────────────────────
    print("\n[6/8] Retraining final Random Forest model on train + val...")

    X_final = pd.concat([X_train, X_val], axis=0)
    y_final = pd.concat([y_train, y_val], axis=0)

    preprocessor_final = build_preprocessor()
    preprocessor_final.fit(X_final)

    X_final_enc = preprocessor_final.transform(X_final)
    X_test_enc = preprocessor_final.transform(X_test)

    final_clf = build_rf_classifier(best_config)

    print(f"  Final train rows : {len(X_final):,}")
    print(f"  Final candidate  : {best_config['name']}")

    final_clf.fit(X_final_enc, y_final)

    pipeline = Pipeline([
        ("preprocessor", preprocessor_final),
        ("classifier", final_clf),
    ])

    # ── 7. Evaluate on untouched test set ────────────────────────────────
    print("\n[7/8] Evaluating final model on test set...")

    y_prob = final_clf.predict_proba(X_test_enc)[:, 1]
    y_pred = (y_prob >= HIGH_THRESHOLD).astype(int)

    auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    print(f"\n  --- Model Evaluation (Test Set, threshold={HIGH_THRESHOLD}) ---")
    print(f"  ROC-AUC : {auc:.4f}")
    print(f"  PR-AUC  : {pr_auc:.4f}")
    print(f"  Brier   : {brier:.4f}")

    print(classification_report(
        y_test,
        y_pred,
        target_names=["No Default", "Default"],
    ))

    _print_threshold_analysis(y_test, y_prob)
    _print_risk_band_report(y_test, y_prob, LOW_THRESHOLD, HIGH_THRESHOLD)

    best_high_threshold = find_threshold_for_recall(
        y_test,
        y_prob,
        target_recall=TARGET_RECALL,
    )

    print(f"\n  Optimal HIGH threshold (recall≥{TARGET_RECALL:.0%}): "
          f"{best_high_threshold:.4f}")
    print(f"  Current HIGH threshold                         : "
          f"{HIGH_THRESHOLD:.4f}")

    # Feature importance
    feature_names_out = preprocessor_final.get_feature_names_out().tolist()
    feature_importance = _extract_feature_importance(
        feature_names_out=feature_names_out,
        classifier=final_clf,
        top_n=20,
    )

    print("\n  --- Top 20 Feature Importance ---")
    for item in feature_importance:
        print(f"  {item['feature']:<45} {item['importance']:.6f}")

    # ── 8. Save artifact ────────────────────────────────────────────────
    print("\n[8/8] Saving artifact...")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "pipeline": pipeline,
        "feature_cols": ALL_FEATURES,
        "feature_names_out": feature_names_out,
        "feature_defaults": feature_defaults,
        "thresholds": {
            "low": LOW_THRESHOLD,
            "high": HIGH_THRESHOLD,
        },
        "optimal_threshold": best_high_threshold,
        "dti_p75": dti_p75,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "best_validation_score": {
            "metric": "roc_auc",
            "roc_auc": round(best_val_auc, 6),
            "pr_auc": round(best_val_pr_auc, 6),
            "brier": round(best_val_brier, 6),
        },
        "selected_params": _rf_params_for_artifact(best_config),
        "rf_tuning_results": [
            {
                "name": result["name"],
                "params": result["params"],
                "val_roc_auc": round(float(result["val_roc_auc"]), 6),
                "val_pr_auc": round(float(result["val_pr_auc"]), 6),
                "val_brier": round(float(result["val_brier"]), 6),
            }
            for result in tuning_results
        ],
        "feature_importance_top20": feature_importance,
        "metrics": {
            "roc_auc": round(float(auc), 4),
            "pr_auc": round(float(pr_auc), 4),
            "brier": round(float(brier), 4),
            "default_rate": round(float(y.mean()), 4),
            "n_train": int(len(X_train)),
            "n_val": int(len(X_val)),
            "n_train_final": int(len(X_final)),
            "n_test": int(len(X_test)),
        },
        "training_config": {
            "model": "RandomForestClassifier",
            "version": MODEL_VERSION,
            "low_threshold": LOW_THRESHOLD,
            "high_threshold": HIGH_THRESHOLD,
            "target_recall": TARGET_RECALL,
            "random_state": RANDOM_STATE,
            "selection_rule": (
                "Select highest validation ROC-AUC; tie-break by PR-AUC."
            ),
            "note": (
                "Random Forest benchmark version. "
                "This model is mainly for comparison against XGBoost/LightGBM."
            ),
        },
    }

    joblib.dump(artifact, MODEL_PATH)

    print(f"\n  Saved   → {MODEL_PATH}")
    print(f"  Version → {MODEL_VERSION}")
    print("=" * 64)


# ─────────────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────────────

def build_preprocessor() -> ColumnTransformer:
    """
    Build preprocessing transformer.

    Numeric features are passed through.
    Categorical features are ordinal-encoded with safe handling for unknowns.
    """
    return ColumnTransformer([
        ("num", "passthrough", NUMERIC_FEATURES),
        ("cat", OrdinalEncoder(
            categories=[
                EMPLOYMENT_CATEGORIES,
                OCCUPATION_CATEGORIES,
            ],
            handle_unknown="use_encoded_value",
            unknown_value=-1,
        ), CATEGORICAL_FEATURES),
    ])


def build_rf_classifier(config: dict) -> RandomForestClassifier:
    """
    Build RandomForestClassifier from a config dictionary.
    """
    return RandomForestClassifier(
        n_estimators=config["n_estimators"],
        max_depth=config["max_depth"],
        min_samples_leaf=config["min_samples_leaf"],
        min_samples_split=config["min_samples_split"],
        max_features=config["max_features"],
        class_weight=config["class_weight"],
        bootstrap=True,
        oob_score=False,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbose=0,
    )


def _rf_params_for_artifact(config: dict) -> dict:
    """
    Keep only serializable RF params for artifact metadata.
    """
    return {
        "name": config["name"],
        "n_estimators": config["n_estimators"],
        "max_depth": config["max_depth"],
        "min_samples_leaf": config["min_samples_leaf"],
        "min_samples_split": config["min_samples_split"],
        "max_features": config["max_features"],
        "class_weight": config["class_weight"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Analysis helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_threshold_analysis(y_test, y_prob) -> None:
    """
    Print rejection rate, recall and precision at common thresholds.
    """
    print("\n  --- Threshold Analysis ---")

    for threshold in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
        mask = y_prob >= threshold

        rejected = int(mask.sum())
        recall = float(y_test[mask].sum()) / max(float(y_test.sum()), 1.0)
        precision = float(y_test[mask].mean()) if rejected > 0 else 0.0

        print(
            f"  threshold={threshold:.2f} | "
            f"rejected={rejected:,} | "
            f"recall(default)={recall:.2%} | "
            f"precision={precision:.2%}"
        )


def _print_risk_band_report(
    y_true,
    y_prob,
    low: float = 0.2,
    high: float = 0.4,
) -> None:
    """
    Verify Low/Medium/High bands are meaningful.
    """
    report_df = pd.DataFrame({
        "y_true": y_true.values if hasattr(y_true, "values") else y_true,
        "y_prob": y_prob,
    })

    report_df["risk_band"] = pd.cut(
        report_df["y_prob"],
        bins=[-0.001, low, high, 1.001],
        labels=["Low", "Medium", "High"],
    )

    report = report_df.groupby("risk_band", observed=True).agg(
        count=("y_true", "size"),
        avg_pd=("y_prob", "mean"),
        actual_default_rate=("y_true", "mean"),
    ).round(4)

    print("\n  --- Risk Band Report ---")
    print(report.to_string())
    print("  (actual_default_rate should increase Low → Medium → High)")


def find_threshold_for_recall(
    y_true,
    y_prob,
    target_recall: float = 0.75,
) -> float:
    """
    Find the highest-precision threshold that achieves target_recall
    for the default class.
    """
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)

    candidates = [
        (threshold, precision, recall)
        for precision, recall, threshold
        in zip(precisions[:-1], recalls[:-1], thresholds)
        if recall >= target_recall
    ]

    if not candidates:
        print(
            f"  WARNING: no threshold achieves recall≥{target_recall:.0%}. "
            f"Falling back to {HIGH_THRESHOLD:.4f}"
        )
        return HIGH_THRESHOLD

    best_threshold, best_precision, best_recall = max(
        candidates,
        key=lambda item: item[1],
    )

    print(
        f"  find_threshold_for_recall: "
        f"t={best_threshold:.4f} | "
        f"precision={best_precision:.4f} | "
        f"recall={best_recall:.4f}"
    )

    return float(best_threshold)


def _extract_feature_importance(
    *,
    feature_names_out: list[str],
    classifier: RandomForestClassifier,
    top_n: int = 20,
) -> list[dict]:
    """
    Extract top feature importances from Random Forest.
    """
    importances = classifier.feature_importances_

    pairs = sorted(
        zip(feature_names_out, importances),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        {
            "feature": str(feature),
            "importance": float(importance),
        }
        for feature, importance in pairs[:top_n]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _feature_defaults(X: pd.DataFrame) -> dict:
    """
    Compute per-column defaults for inference-time fallback.
    """
    defaults = {}

    for col in NUMERIC_FEATURES:
        value = X[col].median()
        defaults[col] = 0 if pd.isna(value) else _python_scalar(value)

    for col in CATEGORICAL_FEATURES:
        mode = X[col].mode(dropna=True)
        defaults[col] = "Other/Unknown" if mode.empty else str(mode.iloc[0])

    return defaults


def _python_scalar(value):
    """
    Convert numpy scalar to native Python type.
    """
    if hasattr(value, "item"):
        return value.item()
    return value


def _run_validation_safely() -> None:
    """
    Run data validation if available.
    """
    try:
        from ml.validate_data import validate
        validate()
    except Exception as exc:
        print(f"  WARNING: data validation failed — {exc}")
        print("  Continuing training anyway...")


if __name__ == "__main__":
    train()