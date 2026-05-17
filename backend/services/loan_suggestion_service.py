"""
loan_suggestion_service.py — v4 (two-stage pipeline)

Binary-search approach: finds the maximum loan_amount where P(default) from Stage 2
stays below LOW_THRESHOLD (0.2), testing each valid term (12 / 36 / 60 months).

Each binary search step runs the full two-stage pipeline: Stage 1 recomputes
credit_score_computed (since DTI changes with loan_amount), then Stage 2 predicts risk.
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
_PERFECT_FIT_TOLERANCE = 0.10


def compute_suggestion(
    payload,
    stage1_artifact: dict[str, Any],
    stage2_artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Returns:
        base_prob        — P(default) for original (loan_amount, term)
        suggested_amount — max safe loan at best term (rounded to $100)
        suggested_term   — term that maximises safe borrowing amount
        is_perfect_fit   — True if no better option exists
        risk_level       — 'Low' | 'Medium'
    """
    LOW  = float(stage2_artifact["thresholds"]["low"])
    HIGH = float(stage2_artifact["thresholds"]["high"])
    prev = list(previous_applications or [])

    requested_amount = float(payload.loan_amount)
    requested_term   = int(payload.term)

    base_prob = _predict(payload, stage1_artifact, stage2_artifact, requested_amount, requested_term, prev)

    best_term   = requested_term
    best_amount = _MIN_LOAN

    for term in _TERMS:
        p_min = _predict(payload, stage1_artifact, stage2_artifact, _MIN_LOAN, term, prev)
        if p_min >= LOW:
            continue
        max_amount = _binary_search(payload, stage1_artifact, stage2_artifact, term, LOW, prev)
        if max_amount > best_amount:
            best_amount = max_amount
            best_term   = term

    suggested_amount = max(_MIN_LOAN, round(best_amount / 100) * 100)
    suggested_term   = best_term

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
    stage1_artifact: dict[str, Any],
    stage2_artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
) -> None:
    """
    Raises ValueError if (loan_amount, term) exceeds the max safe suggestion.
    Called in the confirm endpoint to prevent users from bypassing the frontend cap.
    """
    LOW  = float(stage2_artifact["thresholds"]["low"])
    prev = list(previous_applications or [])

    confirmed_amount = float(payload.loan_amount)
    confirmed_term   = int(payload.term)

    p_min = _predict(payload, stage1_artifact, stage2_artifact, _MIN_LOAN, confirmed_term, prev)
    if p_min >= LOW:
        raise ValueError(
            f"Với kỳ hạn {confirmed_term} tháng, không có khoản vay nào "
            f"dưới ngưỡng rủi ro thấp. Vui lòng chọn kỳ hạn khác."
        )

    max_safe = _binary_search(payload, stage1_artifact, stage2_artifact, confirmed_term, LOW, prev)
    if confirmed_amount > max_safe * 1.02:  # 2% buffer for rounding
        raise ValueError(
            f"Khoản vay ${confirmed_amount:,.0f} vượt mức an toàn "
            f"${max_safe:,.0f} cho kỳ hạn {confirmed_term} tháng."
        )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _binary_search(payload, stage1, stage2, term, threshold, prev) -> float:
    lo, hi = _MIN_LOAN, _MAX_LOAN
    for _ in range(_SEARCH_ITERATIONS):
        mid  = (lo + hi) / 2
        prob = _predict(payload, stage1, stage2, mid, term, prev)
        if prob < threshold:
            lo = mid
        else:
            hi = mid
    return lo


def _predict(
    payload,
    stage1_artifact: dict[str, Any],
    stage2_artifact: dict[str, Any],
    loan_amount: float,
    term: int,
    prev: list,
) -> float:
    from services.model_feature_builder import build_stage1_input, build_model_input
    from services.ml_service import _run_stage1

    modified = payload.model_copy(update={
        "loan_amount": Decimal(str(round(loan_amount, 2))),
        "term":        int(term),
    })

    # Stage 1: recompute credit_score_computed for modified loan params
    credit_score_computed, _ = _run_stage1(modified, stage1_artifact, prev)

    # Stage 2: predict with updated credit_score_computed
    built    = build_model_input(
        modified, stage2_artifact,
        credit_score_computed=credit_score_computed,
        previous_applications=prev,
    )
    pipeline  = stage2_artifact["pipeline"]
    feat_cols = stage2_artifact["feature_cols"]
    row       = pd.DataFrame([built.features], columns=feat_cols)
    return float(pipeline.predict_proba(row)[0, 1])
