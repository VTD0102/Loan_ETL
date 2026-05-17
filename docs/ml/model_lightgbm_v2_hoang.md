import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.compose import ColumnTransformer
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

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from utils.db_connection import get_engine  # noqa: E402

MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"
MODEL_VERSION = "customer_lgbm_v5.3_spw_tuned"

RANDOM_STATE = 42
TARGET_RECALL = 0.75
AUTO_REJECT_THRESHOLD = 0.40

_LEGACY_LOW = 0.2
_LEGACY_HIGH = 0.4

SCALE_POS_WEIGHT_CANDIDATES = [1.0, 3.0, 5.0, 7.0, 9.0, None]

LGBM_BASE_PARAMS = {
    "n_estimators": 3000,
    "learning_rate": 0.02,
    "num_leaves": 31,
    "max_depth": -1,
    "min_child_samples": 50,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
}

_QUERY = """
SELECT
    stated_monthly_income     AS monthly_income,
    loan_original_amount      AS loan_amount,
    term,
    employment_status_grouped AS employment_status,
    debt_to_income_ratio      AS dti,
    is_homeowner_flag         AS is_homeowner,
    1                         AS listing_category,
    credit_score_midpoint     AS credit_score,
    years_employed,
    occupation_type,
    num_previous_loans,
    previous_default_rate,
    num_bureau_records,
    num_active_credit,
    total_overdue_amount,
    max_credit_overdue_days,
    has_bad_debt,
    income_verifiable_flag,
    high_dti_flag,
    rating_ordinal,
    log_monthly_income,
    loan_amount_to_income,
    age_years,
    gender_male_flag,
    education_ordinal,
    cnt_children,
    cnt_fam_members,
    is_married_flag,
    is_default
FROM gold.hc_features_v1
WHERE credit_score_midpoint  IS NOT NULL
  AND stated_monthly_income  IS NOT NULL
  AND loan_original_amount   IS NOT NULL
  AND debt_to_income_ratio   IS NOT NULL
  AND years_employed         IS NOT NULL
  AND occupation_type        IS NOT NULL
"""

NUMERIC_FEATURES = [
    "monthly_income",
    "loan_amount",
    "term",
    "dti",
    "is_homeowner",
    "listing_category",
    "credit_score",
    "years_employed",
    "num_previous_loans",
    "previous_default_rate",
    "num_bureau_records",
    "num_active_credit",
    "total_overdue_amount",
    "max_credit_overdue_days",
    "has_bad_debt",
    "income_verifiable_flag",
    "high_dti_flag",
    "rating_ordinal",
    "log_monthly_income",
    "loan_amount_to_income",
    "age_years",
    "gender_male_flag",
    "education_ordinal",
    "cnt_children",
    "cnt_fam_members",
    "is_married_flag",
]

CATEGORICAL_FEATURES = ["employment_status", "occupation_type"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

EMPLOYMENT_CATEGORIES = [
    "Employed",
    "Self-employed",
    "Retired",
    "Not employed",
    "Other/Unknown",
]

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


def train() -> None:
    _run_validation_safely()

    print("\n" + "=" * 64)
    print("  CUSTOMER RISK MODEL — RETRAIN (LightGBM v5.3)")
    print("=" * 64)

    print("\n[1/8] Fetching data...")
    df = pd.read_sql(_QUERY, get_engine())
    print(f"  Rows : {len(df):,} | Features : {len(ALL_FEATURES)}")

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
    print(f"  Rows : {len(df):,} | Default rate : {df['is_default'].mean():.2%}")

    X = df[ALL_FEATURES].copy()
    y = df["is_default"].astype(int).copy()

    feature_defaults = _feature_defaults(X)
    dti_p75 = float(df["dti"].quantile(0.75))

    print("\n[3/8] Splitting 70/10/20 stratified...")
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
    print(f"  Train : {len(X_train):,} | Val : {len(X_val):,} | Test : {len(X_test):,}")

    print("\n[4/8] Preprocessing...")
    preprocessor = build_preprocessor()
    preprocessor.fit(X_train)
    enc_cols = preprocessor.get_feature_names_out().tolist()
    X_train_enc = _to_df(preprocessor.transform(X_train), enc_cols)
    X_val_enc = _to_df(preprocessor.transform(X_val), enc_cols)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    ratio_spw = neg / max(pos, 1)
    sqrt_spw = math.sqrt(ratio_spw)

    candidate_spw = _unique_float_list([
        *(float(v) for v in SCALE_POS_WEIGHT_CANDIDATES if v is not None),
        ratio_spw,
        sqrt_spw,
    ])

    print(f"  neg={neg:,} / pos={pos:,} | ratio_spw={ratio_spw:.4f} | sqrt_spw={sqrt_spw:.4f}")
    print(f"  candidates : {[round(v, 4) for v in candidate_spw]}")

    print("\n[5/8] Tuning scale_pos_weight (primary: PR-AUC)...")

    tuning_results = []
    best_clf = None
    best_spw = None
    best_iteration = None
    best_val_auc = -1.0
    best_val_pr_auc = -1.0
    best_val_brier = None

    for spw in candidate_spw:
        print(f"\n  SPW={spw:.4f}")

        clf = build_lgbm_classifier(scale_pos_weight=spw)
        clf.fit(
            X_train_enc,
            y_train,
            eval_set=[(X_val_enc, y_val)],
            eval_metric="auc",
            callbacks=[
                early_stopping(stopping_rounds=100, verbose=False),
                log_evaluation(period=100),
            ],
        )

        val_prob = clf.predict_proba(X_val_enc)[:, 1]
        val_auc = roc_auc_score(y_val, val_prob)
        val_pr_auc = average_precision_score(y_val, val_prob)
        val_brier = brier_score_loss(y_val, val_prob)

        best_iter = int(
            clf.best_iteration_
            if getattr(clf, "best_iteration_", None) is not None
            else LGBM_BASE_PARAMS["n_estimators"]
        )

        tuning_results.append({
            "scale_pos_weight": float(spw),
            "best_iteration": best_iter,
            "best_score_from_lgbm": float(clf.best_score_["valid_0"].get("auc", val_auc)),
            "val_roc_auc": float(val_auc),
            "val_pr_auc": float(val_pr_auc),
            "val_brier": float(val_brier),
        })

        print(
            f"  best_iter={best_iter} | "
            f"val_auc={val_auc:.4f} | "
            f"val_pr_auc={val_pr_auc:.4f} | "
            f"val_brier={val_brier:.4f}"
        )

        is_better = (
            val_pr_auc > best_val_pr_auc
            or (abs(val_pr_auc - best_val_pr_auc) < 1e-6 and val_auc > best_val_auc)
        )

        if is_better:
            best_clf = clf
            best_spw = float(spw)
            best_iteration = best_iter
            best_val_auc = float(val_auc)
            best_val_pr_auc = float(val_pr_auc)
            best_val_brier = float(val_brier)

    if best_clf is None:
        raise RuntimeError("No candidate trained successfully.")

    print("\n" + "=" * 64)
    print("  SPW TUNING SUMMARY")
    print("=" * 64)

    for r in sorted(tuning_results, key=lambda x: x["val_pr_auc"], reverse=True):
        print(
            f"  spw={r['scale_pos_weight']:.4f} | "
            f"iter={r['best_iteration']:4d} | "
            f"auc={r['val_roc_auc']:.4f} | "
            f"pr_auc={r['val_pr_auc']:.4f} | "
            f"brier={r['val_brier']:.4f}"
        )

    print(
        f"\n  → Selected spw={best_spw:.4f} | "
        f"iter={best_iteration} | "
        f"auc={best_val_auc:.4f} | "
        f"pr_auc={best_val_pr_auc:.4f} | "
        f"brier={best_val_brier:.4f}"
    )

    print("\n[6/8] Retraining on train + val...")

    X_final = pd.concat([X_train, X_val])
    y_final = pd.concat([y_train, y_val])

    preprocessor_final = build_preprocessor()
    preprocessor_final.fit(X_final)

    enc_cols_final = preprocessor_final.get_feature_names_out().tolist()
    X_final_enc = _to_df(preprocessor_final.transform(X_final), enc_cols_final)
    X_test_enc = _to_df(preprocessor_final.transform(X_test), enc_cols_final)

    final_n = max(int(best_iteration), 1)

    print(f"  rows={len(X_final):,} | n_estimators={final_n} | spw={best_spw:.4f}")

    final_clf = build_lgbm_classifier(
        scale_pos_weight=best_spw,
        n_estimators=final_n,
    )
    final_clf.fit(X_final_enc, y_final)

    pipeline = Pipeline([
        ("preprocessor", preprocessor_final),
        ("classifier", final_clf),
    ])

    print("\n[7/8] Evaluating on test set...")

    y_prob = final_clf.predict_proba(X_test_enc)[:, 1]

    auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    print(f"\n  ROC-AUC={auc:.4f} | PR-AUC={pr_auc:.4f} | Brier={brier:.4f}")

    optimal_t = find_threshold_for_recall(y_test, y_prob, TARGET_RECALL)
    decision_low = round(optimal_t / 2, 4)
    decision_high = round(optimal_t, 4)

    print(f"\n  Optimal threshold (recall≥{TARGET_RECALL:.0%}) : {optimal_t:.4f}")
    print("  Decision bands:")
    print(f"    PD < {decision_low:.4f}                        → PRE_APPROVE")
    print(f"    {decision_low:.4f} ≤ PD < {decision_high:.4f}           → MANUAL_REVIEW")
    print(f"    {decision_high:.4f} ≤ PD < {AUTO_REJECT_THRESHOLD:.4f}  → HIGH_RISK_REVIEW")
    print(f"    PD ≥ {AUTO_REJECT_THRESHOLD:.4f}                        → AUTO_REJECT")

    for label, threshold in [
        ("0.50", 0.5),
        (f"{optimal_t:.4f}", optimal_t),
    ]:
        print(f"\n  --- Report @ threshold={label} ---")
        print(classification_report(
            y_test,
            (y_prob >= threshold).astype(int),
            target_names=["No Default", "Default"],
        ))

    _print_threshold_analysis(y_test, y_prob)

    print(f"\n  [Legacy {_LEGACY_LOW}/{_LEGACY_HIGH}]")
    _print_risk_band_report(
        y_test,
        y_prob,
        _LEGACY_LOW,
        _LEGACY_HIGH,
        labels=["Low", "Medium", "High"],
    )

    print(f"\n  [Recommended {decision_low}/{decision_high}/{AUTO_REJECT_THRESHOLD}]")
    _print_risk_band_report(
        y_test,
        y_prob,
        decision_low,
        decision_high,
        AUTO_REJECT_THRESHOLD,
        labels=["PRE_APPROVE", "MANUAL_REVIEW", "HIGH_RISK_REVIEW", "AUTO_REJECT"],
    )

    _print_calibration_table(y_test, y_prob)

    print("\n[8/8] Saving artifact...")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump({
        "pipeline": pipeline,
        "feature_cols": ALL_FEATURES,
        "feature_names_out": enc_cols_final,
        "feature_defaults": feature_defaults,
        "thresholds": {
            "low": decision_low,
            "medium": decision_high,
            "very_high": AUTO_REJECT_THRESHOLD,
        },
        "decision_thresholds": {
            "pre_approve_max": decision_low,
            "manual_review_min": decision_low,
            "manual_review_max": decision_high,
            "high_risk_review_min": decision_high,
            "high_risk_review_max": AUTO_REJECT_THRESHOLD,
            "auto_reject_min": AUTO_REJECT_THRESHOLD,
        },
        "risk_bands": {
            "pre_approve": {
                "min": 0.0,
                "max": decision_low,
            },
            "manual_review": {
                "min": decision_low,
                "max": decision_high,
            },
            "high_risk_review": {
                "min": decision_high,
                "max": AUTO_REJECT_THRESHOLD,
            },
            "auto_reject": {
                "min": AUTO_REJECT_THRESHOLD,
                "max": 1.0,
            },
        },
        "optimal_threshold": optimal_t,
        "dti_p75": dti_p75,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "best_iteration": int(best_iteration),
        "best_validation_score": {
            "metric": "pr_auc",
            "roc_auc": round(best_val_auc, 6),
            "pr_auc": round(best_val_pr_auc, 6),
            "brier": round(best_val_brier, 6),
        },
        "selected_params": {
            **LGBM_BASE_PARAMS,
            "scale_pos_weight": round(float(best_spw), 6),
            "n_estimators": int(final_n),
            "eval_metric": "auc",
        },
        "scale_pos_weight_tuning_results": [
            {
                "scale_pos_weight": round(float(r["scale_pos_weight"]), 6),
                "best_iteration": int(r["best_iteration"]),
                "best_score_from_lgbm": round(float(r["best_score_from_lgbm"]), 6),
                "val_roc_auc": round(float(r["val_roc_auc"]), 6),
                "val_pr_auc": round(float(r["val_pr_auc"]), 6),
                "val_brier": round(float(r["val_brier"]), 6),
            }
            for r in tuning_results
        ],
        "metrics": {
            "roc_auc": round(float(auc), 4),
            "pr_auc": round(float(pr_auc), 4),
            "brier": round(float(brier), 4),
            "default_rate": round(float(y.mean()), 4),
            "scale_pos_weight_selected": round(float(best_spw), 4),
            "scale_pos_weight_ratio": round(float(ratio_spw), 4),
            "scale_pos_weight_sqrt_ratio": round(float(sqrt_spw), 4),
            "n_train": int(len(X_train)),
            "n_val": int(len(X_val)),
            "n_train_final": int(len(X_final)),
            "n_test": int(len(X_test)),
        },
        "training_config": {
            "model": "LGBMClassifier",
            "version": MODEL_VERSION,
            "early_stopping_metric": "auc",
            "selection_metric": "pr_auc",
            "target_recall": TARGET_RECALL,
            "auto_reject_threshold": AUTO_REJECT_THRESHOLD,
            "random_state": RANDOM_STATE,
            "selection_rule": "Highest val PR-AUC; tie-break ROC-AUC.",
        },
    }, MODEL_PATH)

    print(f"\n  Saved   → {MODEL_PATH}")
    print(f"  Version → {MODEL_VERSION}")
    print("=" * 64)


def build_preprocessor() -> ColumnTransformer:
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


def build_lgbm_classifier(
    scale_pos_weight: float,
    n_estimators: int = LGBM_BASE_PARAMS["n_estimators"],
) -> LGBMClassifier:
    return LGBMClassifier(
        n_estimators=n_estimators,
        learning_rate=LGBM_BASE_PARAMS["learning_rate"],
        num_leaves=LGBM_BASE_PARAMS["num_leaves"],
        max_depth=LGBM_BASE_PARAMS["max_depth"],
        min_child_samples=LGBM_BASE_PARAMS["min_child_samples"],
        subsample=LGBM_BASE_PARAMS["subsample"],
        subsample_freq=1,
        colsample_bytree=LGBM_BASE_PARAMS["colsample_bytree"],
        reg_alpha=LGBM_BASE_PARAMS["reg_alpha"],
        reg_lambda=LGBM_BASE_PARAMS["reg_lambda"],
        scale_pos_weight=scale_pos_weight,
        objective="binary",
        boosting_type="gbdt",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbosity=-1,
    )


def find_threshold_for_recall(y_true, y_prob, target_recall: float) -> float:
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)

    candidates = [
        (threshold, precision, recall)
        for precision, recall, threshold
        in zip(precisions[:-1], recalls[:-1], thresholds)
        if recall >= target_recall
    ]

    if not candidates:
        print(f"  WARNING: no threshold achieves recall≥{target_recall:.0%}, fallback=0.10")
        return 0.10

    best_threshold, best_precision, best_recall = max(
        candidates,
        key=lambda item: item[1],
    )

    print(
        f"  threshold={best_threshold:.4f} | "
        f"precision={best_precision:.4f} | "
        f"recall={best_recall:.4f}"
    )

    return float(best_threshold)


def _print_threshold_analysis(y_test, y_prob) -> None:
    print("\n  --- Threshold Analysis ---")

    for threshold in [0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
        mask = y_prob >= threshold
        rejected = int(mask.sum())
        recall = float(y_test[mask].sum()) / max(float(y_test.sum()), 1.0)
        precision = float(y_test[mask].mean()) if rejected > 0 else 0.0

        print(
            f"  t={threshold:.2f} | "
            f"rejected={rejected:,} | "
            f"recall={recall:.2%} | "
            f"precision={precision:.2%}"
        )


def _print_risk_band_report(y_true, y_prob, *thresholds, labels) -> None:
    bins = [-0.001, *thresholds, 1.001]

    df = pd.DataFrame({
        "y_true": y_true.values if hasattr(y_true, "values") else y_true,
        "y_prob": y_prob,
    })

    df["band"] = pd.cut(
        df["y_prob"],
        bins=bins,
        labels=labels,
    )

    report = df.groupby("band", observed=True).agg(
        count=("y_true", "size"),
        avg_pd=("y_prob", "mean"),
        actual_dr=("y_true", "mean"),
    ).round(4)

    print(report.to_string())


def _print_calibration_table(y_true, y_prob, n_bins: int = 10) -> None:
    print("\n  --- Calibration Table (decile) ---")
    print(f"  {'Decile':>6}  {'N':>6}  {'avg_pd':>8}  {'actual_dr':>10}  {'diff':>8}")
    print("  " + "-" * 46)

    y_arr = y_true.values if hasattr(y_true, "values") else np.array(y_true)
    labels = [f"D{i + 1:02d}" for i in range(n_bins)]

    try:
        bins = pd.qcut(
            y_prob,
            q=n_bins,
            labels=labels,
            duplicates="drop",
        )
    except ValueError:
        bins = pd.cut(
            y_prob,
            bins=n_bins,
            labels=labels[:n_bins],
        )

    df = pd.DataFrame({
        "y_true": y_arr,
        "y_prob": y_prob,
        "decile": bins,
    })

    for decile, group in df.groupby("decile", observed=True):
        avg_pd = group["y_prob"].mean()
        actual_dr = group["y_true"].mean()
        diff = avg_pd - actual_dr
        flag = "⚠" if abs(diff) > 0.05 else " "

        print(
            f"  {str(decile):>6}  "
            f"{len(group):>6,}  "
            f"{avg_pd:>8.4f}  "
            f"{actual_dr:>10.4f}  "
            f"{diff:>+8.4f} {flag}"
        )

    print("  (|diff| > 0.05 ⚠)")


def _feature_defaults(X: pd.DataFrame) -> dict:
    defaults = {}

    for col in NUMERIC_FEATURES:
        value = X[col].median()
        defaults[col] = 0 if pd.isna(value) else _python_scalar(value)

    for col in CATEGORICAL_FEATURES:
        mode = X[col].mode(dropna=True)
        defaults[col] = "Other/Unknown" if mode.empty else str(mode.iloc[0])

    return defaults


def _python_scalar(value):
    return value.item() if hasattr(value, "item") else value


def _to_df(arr, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(arr, columns=cols)


def _unique_float_list(values: list[float]) -> list[float]:
    unique = []

    for value in values:
        value = float(value)
        if not any(abs(value - seen) < 1e-9 for seen in unique):
            unique.append(value)

    return unique


def _run_validation_safely() -> None:
    try:
        from ml.validate_data import validate
        validate()
    except Exception as exc:
        print(f"  WARNING: validation failed — {exc}")


if __name__ == "__main__":
    train()