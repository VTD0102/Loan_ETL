"""
loan_suggestion_service.py

Minimize-burden suggestion strategy:

  Step 1 — Honour the requested amount when feasible.
    Build (term → max_safe_amount) for every approvable term.
    If one or more terms support requested_amount, pick the SHORTEST such term
    (minimises total interest paid while delivering exactly what the borrower asked).

  Step 2 — Fallback when the requested amount is out of reach at every term.
    Among all (term, max_safe) candidates, pick the one with the lowest
    monthly_payment = max_safe / term (minimises DTI and payment burden).
    Tiebreak: prefer higher max_safe, then shorter term.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd

_MIN_LOAN = 500.0
_MAX_LOAN = 150_000.0
_TERMS    = [12, 24, 36, 48, 60]
_SEARCH_ITERATIONS = 20      # precision ≈ $0.1 over 150k range
_PERFECT_FIT_TOLERANCE = 0.10  # within 10% of max safe = "perfect fit"


def compute_suggestion(
    payload,
    artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Returns:
        base_prob        — default probability for (requested_amount, requested_term)
        suggested_amount — recommended loan amount (rounded to nearest 100)
        suggested_term   — recommended term in months
        is_perfect_fit   — True when the original request is already optimal
        risk_level       — 'Low' | 'Medium'
    """
    LOW  = float(artifact["thresholds"]["low"])
    prev = list(previous_applications or [])

    requested_amount = float(payload.loan_amount)
    requested_term   = int(payload.term)

    base_prob = _predict(payload, artifact, requested_amount, requested_term, prev)

    # Build: {term: max_safe_amount} for every approvable term
    candidates: list[tuple[int, float]] = []
    for term in _TERMS:
        if _predict(payload, artifact, _MIN_LOAN, term, prev) >= LOW:
            continue  # even minimum loan is too risky on this term
        max_safe = _binary_search(payload, artifact, term, LOW, prev)
        candidates.append((term, max_safe))

    if not candidates:
        return {
            "base_prob":        round(base_prob, 4),
            "suggested_amount": _MIN_LOAN,
            "suggested_term":   requested_term,
            "is_perfect_fit":   False,
            "risk_level":       "Medium",
        }

    # Step 1: can we honour the requested amount?
    # Among all terms where max_safe >= requested_amount, pick the SHORTEST.
    feasible = [(t, ms) for t, ms in candidates if ms >= requested_amount]

    if feasible:
        best_term, best_max = min(feasible, key=lambda x: x[0])
        suggested_amount = max(_MIN_LOAN, round(requested_amount / 100) * 100)
        suggested_term   = best_term

        # Perfect fit: risk already Low AND user's term is already the shortest
        # feasible AND amount is within tolerance of max capacity at that term.
        is_perfect_fit = (
            base_prob < LOW
            and requested_term == best_term
            and requested_amount >= best_max * (1 - _PERFECT_FIT_TOLERANCE)
        )
    else:
        # Step 2: requested amount is out of reach everywhere.
        # Minimise monthly_payment = max_safe / term (proxy for DTI).
        # Tiebreak: higher amount, then shorter term.
        best_term, best_max = min(
            candidates,
            key=lambda x: (x[1] / x[0], -x[1], x[0]),
        )
        suggested_amount = max(_MIN_LOAN, round(best_max / 100) * 100)
        suggested_term   = best_term
        is_perfect_fit   = False

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
    from services.model_feature_builder import apply_dti_risk_floor, build_model_input
    modified = payload.model_copy(update={
        "loan_amount": Decimal(str(round(loan_amount, 2))),
        "term":        int(term),
        "dti":         None,
    })
    built    = build_model_input(modified, artifact, previous_applications=prev)
    pipeline = artifact["pipeline"]
    feature_cols = artifact["feature_cols"]
    row      = pd.DataFrame([built.features], columns=feature_cols)
    raw_prob = float(pipeline.predict_proba(row)[0, 1])
    thresholds = artifact["thresholds"]
    return apply_dti_risk_floor(
        raw_prob,
        built.features.get("dti", 0.0),
        low_threshold=float(thresholds["low"]),
        high_threshold=float(thresholds["high"]),
    )

