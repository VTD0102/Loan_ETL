"""
loan_suggestion_service.py

Binary-search approach: finds the maximum loan_amount where default_prob stays
below LOW_THRESHOLD (0.2), testing each valid term (12 / 36 / 60 months).

Returns suggested_amount, suggested_term, and whether the user's original
request is already a "perfect fit" (no improvement to suggest).
"""
from __future__ import annotations

from copy import copy
from decimal import Decimal
from typing import Any

import pandas as pd

_MIN_LOAN = 500.0
_MAX_LOAN = 150_000.0
_TERMS    = [12, 36, 60]
_SEARCH_ITERATIONS = 20      # precision ≈ $0.1 over 150k range
_PERFECT_FIT_TOLERANCE = 0.10  # within 10% of max safe = "perfect fit"


def compute_suggestion(
    payload,
    artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Returns:
        base_prob       — probability for original (loan_amount, term)
        suggested_amount — max safe loan at best term (rounded to $100)
        suggested_term   — term that maximises safe borrowing amount
        is_perfect_fit   — True if no better option exists
        risk_level       — 'Low' | 'Medium'
    """
    LOW  = float(artifact["thresholds"]["low"])
    HIGH = float(artifact["thresholds"]["high"])
    prev = list(previous_applications or [])

    requested_amount = float(payload.loan_amount)
    requested_term   = int(payload.term)

    base_prob = _predict(payload, artifact, requested_amount, requested_term, prev)

    # Find (term, max_amount) with best outcome under LOW threshold
    best_term    = requested_term
    best_amount  = _MIN_LOAN

    for term in _TERMS:
        p_min = _predict(payload, artifact, _MIN_LOAN, term, prev)
        if p_min >= LOW:
            continue  # even minimum loan exceeds threshold on this term
        max_amount = _binary_search(payload, artifact, term, LOW, prev)
        if max_amount > best_amount:
            best_amount = max_amount
            best_term   = term

    # Round to nearest $100 for clean UX
    suggested_amount = max(_MIN_LOAN, round(best_amount / 100) * 100)
    suggested_term   = best_term

    # Perfect fit: prob already LOW AND user's term optimal AND amount near max
    is_perfect_fit = (
        base_prob < LOW
        and requested_term == suggested_term
        and requested_amount >= suggested_amount * (1 - _PERFECT_FIT_TOLERANCE)
    )

    return {
        "base_prob":        round(base_prob, 4),
        "suggested_amount": suggested_amount,
        "suggested_term":   suggested_term,
        "is_perfect_fit":   is_perfect_fit,
        "risk_level":       "Low" if base_prob < LOW else "Medium",
    }


def validate_confirmed_values(
    payload,
    artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
) -> None:
    """
    Raises ValueError if (loan_amount, term) exceeds the max safe suggestion.
    Called in the confirm endpoint to prevent users from bypassing the frontend cap.
    """
    LOW  = float(artifact["thresholds"]["low"])
    prev = list(previous_applications or [])

    confirmed_amount = float(payload.loan_amount)
    confirmed_term   = int(payload.term)

    p_min = _predict(payload, artifact, _MIN_LOAN, confirmed_term, prev)
    if p_min >= LOW:
        raise ValueError(
            f"Với kỳ hạn {confirmed_term} tháng, không có khoản vay nào "
            f"dưới ngưỡng rủi ro thấp. Vui lòng chọn kỳ hạn khác."
        )

    max_safe = _binary_search(payload, artifact, confirmed_term, LOW, prev)
    if confirmed_amount > max_safe * 1.02:  # 2% buffer for rounding
        raise ValueError(
            f"Khoản vay ${confirmed_amount:,.0f} vượt mức an toàn "
            f"${max_safe:,.0f} cho kỳ hạn {confirmed_term} tháng."
        )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _binary_search(payload, artifact, term, threshold, prev) -> float:
    lo, hi = _MIN_LOAN, _MAX_LOAN
    for _ in range(_SEARCH_ITERATIONS):
        mid = (lo + hi) / 2
        prob = _predict(payload, artifact, mid, term, prev)
        if prob < threshold:
            lo = mid
        else:
            hi = mid
    return lo


def _predict(payload, artifact, loan_amount: float, term: int, prev: list) -> float:
    from services.model_feature_builder import build_model_input
    modified = payload.model_copy(update={
        "loan_amount": Decimal(str(round(loan_amount, 2))),
        "term":        int(term),
    })
    built    = build_model_input(modified, artifact, previous_applications=prev)
    pipeline = artifact["pipeline"]
    feature_cols = artifact["feature_cols"]
    row      = pd.DataFrame([built.features], columns=feature_cols)
    return float(pipeline.predict_proba(row)[0, 1])
