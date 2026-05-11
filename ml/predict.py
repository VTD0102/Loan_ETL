"""
ml/predict.py
─────────────
Central prediction module for CreditIntel Web Application.
Called by FastAPI endpoint: POST /predict

Public API:
    predict_loan_risk(input_dict)  → prediction result dict
    validate_input(input_dict)     → raises ValueError if invalid

Example:
    >>> from ml.predict import predict_loan_risk
    >>> result = predict_loan_risk({
    ...     "monthly_income"   : 5000,
    ...     "loan_amount"      : 15000,
    ...     "term"             : 36,
    ...     "employment_status": "Employed",
    ...     "dti"              : 0.25,
    ...     "is_homeowner"     : True,
    ...     "listing_category" : 1,
    ...     "credit_score"     : 700,
    ... })
    >>> print(result["risk_level"])
    'Low'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
from datetime import datetime, timezone

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "ml" / "models" / "customer_risk_model.pkl"

# ── Feature definitions ───────────────────────────────────────────────────────
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

# ── Valid values ─────────────────────────────────────────────────────────────
VALID_TERMS = [12, 36, 60]

VALID_EMPLOYMENT = [
    "Employed",
    "Full-Time",
    "Part-Time",
    "Self-Employed",
    "Not Employed",
    "Retired",
    "Other",
    "Not Available",
]

# Normalize customer form values → silver layer values
EMPLOYMENT_NORMALIZE_MAP = {
    "employed"      : "Employed",
    "full-time"     : "Full-Time",
    "full time"     : "Full-Time",
    "part-time"     : "Part-Time",
    "part time"     : "Part-Time",
    "self-employed" : "Self-Employed",
    "selfemployed"  : "Self-Employed",
    "not employed"  : "Not Employed",
    "unemployed"    : "Not Employed",
    "retired"       : "Retired",
    "other"         : "Other",
    "not available" : "Not Available",
    "n/a"           : "Not Available",
}

VALID_LISTING_CATEGORY = list(range(0, 21))   # 0–20

LISTING_CATEGORY_MAP = {
    0: "Not Available",       1: "Debt Consolidation",
    2: "Home Improvement",    3: "Business",
    4: "Personal Loan",       5: "Student Use",
    6: "Auto",                7: "Other",
    8: "Baby & Adoption",     9: "Boat",
    10: "Cosmetic Procedures", 11: "Engagement Ring",
    12: "Green Loans",         13: "Household Expenses",
    14: "Large Purchases",     15: "Medical / Dental",
    16: "Motorcycle",          17: "RV",
    18: "Taxes",               19: "Vacation",
    20: "Wedding Loans",
}

# ── Thresholds (fallback if not in artifact) ─────────────────────────────────
DEFAULT_THRESHOLDS = {"low": 0.2, "high": 0.4}


# ── Input validation ─────────────────────────────────────────────────────────

def validate_input(input_dict: dict) -> None:
    """
    Validate all 8 required fields before prediction.
    Raises ValueError with descriptive message on first failure.

    Args:
        input_dict: raw input from customer form or API request

    Raises:
        ValueError: if any field is missing or invalid
        TypeError : if input_dict is not a dict

    Example:
        >>> validate_input({"monthly_income": -100, ...})
        ValueError: monthly_income must be positive. Got: -100
    """
    if not isinstance(input_dict, dict):
        raise TypeError(f"Input must be a dict. Got: {type(input_dict).__name__}")

    # ── Check required keys ──────────────────────────────
    missing = [f for f in ALL_FEATURES if f not in input_dict]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # ── monthly_income ───────────────────────────────────
    try:
        income = float(input_dict["monthly_income"])
    except (ValueError, TypeError):
        raise ValueError(f"monthly_income must be a number. Got: {input_dict['monthly_income']!r}")
    if income <= 0:
        raise ValueError(f"monthly_income must be positive. Got: {income}")
    if income > 1_000_000:
        raise ValueError(f"monthly_income seems unreasonably high: {income}. Max allowed: 1,000,000")

    # ── loan_amount ──────────────────────────────────────
    try:
        amount = float(input_dict["loan_amount"])
    except (ValueError, TypeError):
        raise ValueError(f"loan_amount must be a number. Got: {input_dict['loan_amount']!r}")
    if amount <= 0:
        raise ValueError(f"loan_amount must be positive. Got: {amount}")
    if amount > 500_000:
        raise ValueError(f"loan_amount exceeds maximum allowed (500,000). Got: {amount}")

    # ── term ─────────────────────────────────────────────
    try:
        term = int(input_dict["term"])
    except (ValueError, TypeError):
        raise ValueError(f"term must be an integer. Got: {input_dict['term']!r}")
    if term not in VALID_TERMS:
        raise ValueError(f"term must be one of {VALID_TERMS}. Got: {term}")

    # ── employment_status ────────────────────────────────
    emp = str(input_dict["employment_status"]).strip()
    normalized = EMPLOYMENT_NORMALIZE_MAP.get(emp.lower(), emp)
    if normalized not in VALID_EMPLOYMENT:
        raise ValueError(
            f"employment_status '{emp}' is not recognized. "
            f"Valid values: {VALID_EMPLOYMENT}"
        )

    # ── dti ──────────────────────────────────────────────
    try:
        dti = float(input_dict["dti"])
    except (ValueError, TypeError):
        raise ValueError(f"dti must be a number. Got: {input_dict['dti']!r}")
    if dti < 0:
        raise ValueError(f"dti cannot be negative. Got: {dti}")
    if dti > 10:
        raise ValueError(f"dti seems unreasonably high: {dti}. Max allowed: 10")

    # ── is_homeowner ─────────────────────────────────────
    if not isinstance(input_dict["is_homeowner"], (bool, int)):
        raise ValueError(
            f"is_homeowner must be True/False or 0/1. "
            f"Got: {input_dict['is_homeowner']!r}"
        )

    # ── listing_category ─────────────────────────────────
    try:
        cat = int(input_dict["listing_category"])
    except (ValueError, TypeError):
        raise ValueError(
            f"listing_category must be an integer. "
            f"Got: {input_dict['listing_category']!r}"
        )
    if cat not in VALID_LISTING_CATEGORY:
        raise ValueError(
            f"listing_category must be 0–20. Got: {cat}"
        )

    # ── credit_score ─────────────────────────────────────
    try:
        score = float(input_dict["credit_score"])
    except (ValueError, TypeError):
        raise ValueError(f"credit_score must be a number. Got: {input_dict['credit_score']!r}")
    if not (300 <= score <= 850):
        raise ValueError(f"credit_score must be between 300 and 850. Got: {score}")


# ── Business logic ────────────────────────────────────────────────────────────

def get_risk_level(pd_val: float, thresholds: dict) -> str:
    """
    Map probability of default → risk label.

    Args:
        pd_val     : float between 0 and 1
        thresholds : dict with 'low' and 'high' keys

    Returns:
        'Low' | 'Medium' | 'High'

    Example:
        >>> get_risk_level(0.15, {"low": 0.2, "high": 0.4})
        'Low'
        >>> get_risk_level(0.30, {"low": 0.2, "high": 0.4})
        'Medium'
        >>> get_risk_level(0.55, {"low": 0.2, "high": 0.4})
        'High'
    """
    if pd_val < thresholds["low"]:
        return "Low"
    elif pd_val <= thresholds["high"]:
        return "Medium"
    else:
        return "High"


def get_risk_score(pd_val: float) -> int:
    """
    Map probability of default → internal risk score (0–100).
    Higher score = safer borrower.

    Formula: score = (1 - pd_val) * 100

    Args:
        pd_val: float between 0 and 1

    Returns:
        int between 0 (worst) and 100 (best)

    Example:
        >>> get_risk_score(0.10)
        90
        >>> get_risk_score(0.50)
        50
    """
    return int((1 - pd_val) * 100)


def get_recommended_amount(
    requested_amount: float,
    risk_level      : str,
) -> float:
    """
    Calculate recommended loan amount based on risk level.

    Business rules (from APP_DEVELOPMENT_PLAN.md):
        LOW    → approve full requested amount
        MEDIUM → reduce by 20%
        HIGH   → reduce by 40%

    Args:
        requested_amount : original loan amount from customer form
        risk_level       : 'Low' | 'Medium' | 'High'

    Returns:
        float — recommended amount (rounded to nearest 100)

    Example:
        >>> get_recommended_amount(10000, "Low")
        10000.0
        >>> get_recommended_amount(10000, "Medium")
        8000.0
        >>> get_recommended_amount(10000, "High")
        6000.0
    """
    if risk_level == "Low":
        factor = 1.0
    elif risk_level == "Medium":
        factor = 0.8    # reduce by 20%
    else:
        factor = 0.6    # reduce by 40%

    raw = requested_amount * factor
    # Round to nearest 100 for cleaner UX
    return round(raw / 100) * 100


def get_recommended_term(
    requested_term: int,
    risk_level    : str,
) -> int:
    """
    Suggest optimal loan term based on risk level and requested term.

    Business rules:
        HIGH  risk + short term (12)  → suggest medium term (36)
            Reason: monthly burden too high for risky borrower
        LOW   risk + long  term (60)  → suggest shorter term (36)
            Reason: unnecessary interest cost for safe borrower
        All other combinations        → keep requested term

    Args:
        requested_term : 12 | 36 | 60
        risk_level     : 'Low' | 'Medium' | 'High'

    Returns:
        int — recommended term in months

    Example:
        >>> get_recommended_term(12, "High")
        36
        >>> get_recommended_term(60, "Low")
        36
        >>> get_recommended_term(36, "Medium")
        36
    """
    if risk_level == "High" and requested_term == 12:
        return 36   # short term too risky for high-risk borrower → extend
    if risk_level == "Low" and requested_term == 60:
        return 36   # unnecessary long term for safe borrower → shorten
    return requested_term


def get_auto_decision(pd_val: float, thresholds: dict) -> str:
    """
    Determine automatic application status from ML result.
    Matches APP_DEVELOPMENT_PLAN.md §5 status flow.

    Args:
        pd_val     : probability of default
        thresholds : dict with 'high' key

    Returns:
        'AUTO_REJECTED'  if P(default) > high threshold
        'PENDING_REVIEW' otherwise

    Example:
        >>> get_auto_decision(0.55, {"low": 0.2, "high": 0.4})
        'AUTO_REJECTED'
        >>> get_auto_decision(0.30, {"low": 0.2, "high": 0.4})
        'PENDING_REVIEW'
    """
    if pd_val > thresholds["high"]:
        return "AUTO_REJECTED"
    return "PENDING_REVIEW"


# ── Main prediction function ──────────────────────────────────────────────────

def predict_loan_risk(input_dict: dict) -> dict:
    """
    Main prediction function. Validates input, runs model, applies
    business rules, and returns full risk assessment result.

    Called by:
        - FastAPI POST /predict endpoint
        - predict_and_save() for DB persistence

    Args:
        input_dict: dict with exactly these 8 keys:
            monthly_income    (float)  : monthly income in USD
            loan_amount       (float)  : requested loan amount in USD
            term              (int)    : 12, 36, or 60 months
            employment_status (str)    : see VALID_EMPLOYMENT
            dti               (float)  : debt-to-income ratio (e.g. 0.25)
            is_homeowner      (bool)   : True or False
            listing_category  (int)    : 0–20 (see LISTING_CATEGORY_MAP)
            credit_score      (float)  : 300–850

    Returns:
        dict with keys:
            default_probability  (float) : 0.0000 – 1.0000
            risk_level           (str)   : 'Low' | 'Medium' | 'High'
            risk_score           (int)   : 0 (worst) – 100 (best)
            auto_decision        (str)   : 'AUTO_REJECTED' | 'PENDING_REVIEW'
            recommended_amount   (float) : adjusted loan amount
            recommended_term     (int)   : adjusted term in months
            category_label       (str)   : human-readable listing category
            assessed_at          (str)   : ISO 8601 UTC timestamp

    Raises:
        ValueError      : if input validation fails
        FileNotFoundError: if model artifact not found
        RuntimeError    : if prediction fails unexpectedly

    Example:
        >>> result = predict_loan_risk({
        ...     "monthly_income"   : 5000,
        ...     "loan_amount"      : 15000,
        ...     "term"             : 36,
        ...     "employment_status": "Employed",
        ...     "dti"              : 0.25,
        ...     "is_homeowner"     : True,
        ...     "listing_category" : 1,
        ...     "credit_score"     : 700,
        ... })
        >>> result["risk_level"]
        'Low'
        >>> result["auto_decision"]
        'PENDING_REVIEW'
        >>> result["recommended_amount"]
        15000.0
    """
    # ── Step 1: Validate ─────────────────────────────────
    validate_input(input_dict)

    # ── Step 2: Load model ───────────────────────────────
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. "
            "Run: python -m ml.retrain_customer_model"
        )

    try:
        artifact = joblib.load(MODEL_PATH)
    except Exception as e:
        raise RuntimeError(f"Failed to load model artifact: {e}") from e

    pipeline   = artifact["pipeline"]
    thresholds = artifact.get("thresholds", DEFAULT_THRESHOLDS)

    # ── Step 3: Normalize employment_status ──────────────
    emp_raw    = str(input_dict["employment_status"]).strip()
    emp_norm   = EMPLOYMENT_NORMALIZE_MAP.get(emp_raw.lower(), emp_raw)

    # ── Step 4: Build input DataFrame ────────────────────
    # Column order MUST match ALL_FEATURES (numeric first, categorical last)
    input_df = pd.DataFrame([{
        "monthly_income"   : float(input_dict["monthly_income"]),
        "loan_amount"      : float(input_dict["loan_amount"]),
        "term"             : int(input_dict["term"]),
        "dti"              : float(input_dict["dti"]),
        "is_homeowner"     : int(bool(input_dict["is_homeowner"])),
        "listing_category" : int(input_dict["listing_category"]),
        "credit_score"     : float(input_dict["credit_score"]),
        "employment_status": emp_norm,
    }])

    # Explicit column ordering to match training
    input_df = input_df[ALL_FEATURES]

    # ── Step 5: Predict ──────────────────────────────────
    try:
        probs  = pipeline.predict_proba(input_df)
        pd_val = float(probs[0, 1]) if probs.shape[1] > 1 else float(probs[0, 0])
    except Exception as e:
        raise RuntimeError(f"Prediction failed: {e}") from e

    # ── Step 6: Apply business rules ─────────────────────
    risk_level   = get_risk_level(pd_val, thresholds)
    risk_score   = get_risk_score(pd_val)
    auto_decision = get_auto_decision(pd_val, thresholds)

    requested_amount = float(input_dict["loan_amount"])
    requested_term   = int(input_dict["term"])

    rec_amount = get_recommended_amount(requested_amount, risk_level)
    rec_term   = get_recommended_term(requested_term, risk_level)

    category_id    = int(input_dict["listing_category"])
    category_label = LISTING_CATEGORY_MAP.get(category_id, "Unknown")

    return {
        "default_probability": round(pd_val, 4),
        "risk_level"         : risk_level,
        "risk_score"         : risk_score,
        "auto_decision"      : auto_decision,
        "recommended_amount" : rec_amount,
        "recommended_term"   : rec_term,
        "category_label"     : category_label,
        "assessed_at"        : datetime.now(timezone.utc).isoformat(),
    }