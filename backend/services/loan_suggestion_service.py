"""
loan_suggestion_service.py

Suggestion strategy:

  Step 1 — Build (term -> max_reviewable_amount) for every term that can stay
    below the auto-reject threshold. This is the cap users may confirm for
    admin review, not only the stricter LOW-risk amount.

  Step 2 — If the requested amount is feasible, pick the shortest feasible term
    and expose that term's maximum reviewable amount.

  Step 3 — If the requested amount is not feasible, pick the term with the
    highest maximum reviewable amount. Tiebreak: shorter term, then lower
    monthly payment.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd

_MIN_LOAN = 500.0
_MAX_LOAN = 150_000.0
_TERMS    = [12, 24, 36, 48, 60]
_SEARCH_ITERATIONS = 20      # precision ≈ $0.1 over 150k range
_PERFECT_FIT_TOLERANCE = 0.10  # within 10% of max reviewable = "perfect fit"


def compute_suggestion(
    payload,
    artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
    bureau_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Returns:
        base_prob        — default probability for (requested_amount, requested_term)
        suggested_amount — maximum reviewable loan amount (rounded to nearest 100)
        suggested_term   — recommended term in months
        is_perfect_fit   — True when the original request is already optimal
        risk_level       — 'Low' | 'Medium' | 'High'
    """
    LOW  = float(artifact["thresholds"]["low"])
    HIGH = float(artifact["thresholds"]["high"])
    prev = list(previous_applications or [])

    requested_amount = float(payload.loan_amount)
    requested_term   = int(payload.term)

    base_prob = _predict(payload, artifact, requested_amount, requested_term, prev, bureau_features)

    # Với mỗi kỳ hạn (12/24/36/48/60 tháng): tìm số tiền tối đa giữ xác suất < 0.4
    # Kỳ hạn bị loại nếu ngay cả mức tối thiểu 500 cũng bị từ chối
    candidates: list[tuple[int, float]] = []
    for term in _TERMS:
        if _predict(payload, artifact, _MIN_LOAN, term, prev, bureau_features) >= HIGH:
            continue  # even minimum loan is auto-reject risk on this term
        max_reviewable = _binary_search(payload, artifact, term, HIGH, prev, bureau_features)
        candidates.append((term, max_reviewable))

    if not candidates:
        return {
            "base_prob":        round(base_prob, 4),
            "suggested_amount": _MIN_LOAN,
            "suggested_term":   requested_term,
            "is_perfect_fit":   False,
            "risk_level":       "High" if base_prob >= HIGH else "Medium",
        }

    # Chọn kỳ hạn: ưu tiên kỳ hạn ngắn nhất đạt được số tiền khách yêu cầu (giảm tổng lãi)
    feasible = [(t, ms) for t, ms in candidates if ms >= requested_amount]

    if feasible:
        best_term, best_max = min(feasible, key=lambda x: x[0])

        # Perfect fit: xác suất gốc đã < 0.2 (Low) VÀ kỳ hạn khách chọn là ngắn nhất khả thi
        # VÀ số tiền nằm trong dải 10% của hạn mức tối đa → hồ sơ lý tưởng, không cần gợi ý
        is_perfect_fit = (
            base_prob < LOW
            and requested_term == best_term
            and requested_amount >= best_max * (1 - _PERFECT_FIT_TOLERANCE)
        )
    else:
        # Số tiền yêu cầu vượt hạn mức ở mọi kỳ hạn → chọn kỳ hạn có hạn mức cao nhất
        # Tiebreak: kỳ hạn ngắn hơn, rồi khoản trả góp thấp hơn
        best_term, best_max = max(
            candidates,
            key=lambda x: (x[1], -x[0], -(x[1] / x[0])),
        )
        is_perfect_fit = False

    # Làm tròn xuống bội số 100
    suggested_amount = max(_MIN_LOAN, round(best_max / 100) * 100)
    suggested_term   = best_term

    return {
        "base_prob":        round(base_prob, 4),
        "suggested_amount": suggested_amount,
        "suggested_term":   suggested_term,
        "is_perfect_fit":   is_perfect_fit,
        "risk_level":       "Low" if base_prob < LOW else "High" if base_prob >= HIGH else "Medium",
    }


def validate_confirmed_values(
    payload,
    artifact: dict[str, Any],
    previous_applications: list[Any] | None = None,
    bureau_features: dict[str, Any] | None = None,
) -> None:
    """
    Raises ValueError if (loan_amount, term) exceeds the max reviewable amount.
    Called in the confirm endpoint to prevent users from bypassing the frontend cap.
    """
    HIGH = float(artifact["thresholds"]["high"])
    prev = list(previous_applications or [])

    confirmed_amount = float(payload.loan_amount)
    confirmed_term   = int(payload.term)

    p_min = _predict(payload, artifact, _MIN_LOAN, confirmed_term, prev, bureau_features)
    if p_min >= HIGH:
        raise ValueError(
            f"Với kỳ hạn {confirmed_term} tháng, không có khoản vay nào "
            f"dưới ngưỡng từ chối tự động. Vui lòng chọn kỳ hạn khác."
        )

    max_reviewable = _binary_search(payload, artifact, confirmed_term, HIGH, prev, bureau_features)
    if confirmed_amount > max_reviewable * 1.02:  # 2% buffer for rounding
        raise ValueError(
            f"Khoản vay ${confirmed_amount:,.0f} vượt hạn mức có thể gửi xét duyệt "
            f"${max_reviewable:,.0f} cho kỳ hạn {confirmed_term} tháng."
        )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _binary_search(payload, artifact, term, threshold, prev, bureau_features=None) -> float:
    # Tìm kiếm nhị phân 20 vòng trên khoảng [500, 150_000]
    # Độ chính xác ≈ 150_000 / 2^20 ≈ $0.14 — đủ cho mục đích làm tròn bội số 100
    lo, hi = _MIN_LOAN, _MAX_LOAN
    for _ in range(_SEARCH_ITERATIONS):
        mid = (lo + hi) / 2
        prob = _predict(payload, artifact, mid, term, prev, bureau_features)
        if prob < threshold:
            lo = mid
        else:
            hi = mid
    return lo


def _predict(payload, artifact, loan_amount: float, term: int, prev: list, bureau_features=None) -> float:
    # Mỗi lần thử trong vòng nhị phân đều chạy lại toàn bộ pipeline —
    # bao gồm cả sàn DTI (Lớp 1) — để gợi ý phản ánh đúng ngưỡng quyết định thực tế
    from services.model_feature_builder import apply_dti_risk_floor, build_model_input
    modified = payload.model_copy(update={
        "loan_amount": Decimal(str(round(loan_amount, 2))),
        "term":        int(term),
        "dti":         None,
    })
    built    = build_model_input(
        modified, artifact, previous_applications=prev, bureau_features=bureau_features,
    )
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

