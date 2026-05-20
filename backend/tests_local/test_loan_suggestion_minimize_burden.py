"""
Unit tests for compute_suggestion() — max-reviewable strategy.

Strategy under test:
  Step 1 — Find all terms where max_reviewable_amount stays below the
    auto-reject threshold.
  Step 2 — If the requested amount is feasible, pick the SHORTEST feasible term
    and expose that term's maximum reviewable amount.
  Step 3 — If amount is infeasible everywhere, pick the highest reviewable
    amount. Tiebreak by shortest term, then lower monthly payment.
"""
from decimal import Decimal
from typing import Any
from unittest.mock import patch

from services.loan_suggestion_service import compute_suggestion, validate_confirmed_values

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_ARTIFACT: dict[str, Any] = {
    "pipeline":     None,          # not used; _predict is mocked
    "feature_cols": ["f"],
    "thresholds":   {"low": 0.20, "high": 0.40},
    "model_version": "test",
    "dti_p75":      0.50,
}


class _Payload:
    """Minimal payload stand-in for suggest / validate calls."""
    def __init__(self, loan_amount: float, term: int, monthly_income: float = 10_000.0):
        self.loan_amount     = Decimal(str(loan_amount))
        self.term            = term
        self.monthly_income  = Decimal(str(monthly_income))
        self.dti             = None
        self.employment_status      = "Employed"
        self.is_homeowner           = True
        self.occupation_type        = "OTHER"
        self.years_employed         = Decimal("3")
        self.num_bureau_records     = 1
        self.num_active_credit      = 1
        self.total_overdue_amount   = Decimal("0")
        self.max_credit_overdue_days = 0
        self.has_bad_debt           = False
        self.income_verifiable_flag = True
        self.age_years              = Decimal("30")
        self.gender_male_flag       = True
        self.education_ordinal      = 3
        self.cnt_children           = 0
        self.cnt_fam_members        = 2
        self.is_married_flag        = False
        self.num_previous_loans     = 0
        self.previous_default_rate  = 0.0
        self.listing_category       = None
        self.credit_score           = None

    def model_copy(self, *, update: dict):
        import copy
        clone = copy.copy(self)
        for k, v in update.items():
            setattr(clone, k, v)
        return clone


# ---------------------------------------------------------------------------
# Fake predict factories
#
# Each factory returns a callable (payload, artifact, loan_amount, term, prev)
# that emulates a realistic but deterministic probability function.
# ---------------------------------------------------------------------------

def _make_predictor(safe_caps: dict[int, float]) -> Any:
    """
    Return a fake _predict where:
      prob = 0.10  (<LOW=0.20)   when loan_amount <= safe_caps[term]
      prob = 0.45  (>HIGH=0.40)  when loan_amount >  safe_caps[term]

    Step-function ensures binary search converges to exactly safe_caps[term].
    Terms missing from safe_caps (or cap=0) always return 0.50 — never reviewable.
    """
    def fake(payload, artifact, loan_amount: float, term: int, prev):
        cap = safe_caps.get(term, 0.0)
        if cap == 0.0:
            return 0.50
        return 0.10 if loan_amount <= cap else 0.45
    return fake


# ---------------------------------------------------------------------------
# Test 1 — Pick shortest feasible term and expose its max amount
# ---------------------------------------------------------------------------

def test_honours_requested_amount_with_shortest_term():
    """
    Safe caps: 12m=0 (infeasible), 24m=25k, 36m=40k, 48m=55k, 60m=70k.
    User requests 20k / 24m.
    Shortest term where max_reviewable >= 20k is 24m.
    Suggested amount is the maximum reviewable amount for that term.
    """
    caps = {12: 0, 24: 25_000, 36: 40_000, 48: 55_000, 60: 70_000}
    payload = _Payload(loan_amount=20_000, term=24)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    assert result["suggested_term"]   == 24, "should pick shortest feasible term (24m)"
    assert result["suggested_amount"] == 25_000, "should expose max reviewable amount"


def test_shorter_term_wins_over_higher_amount():
    """
    Caps: 24m=30k, 36m=50k, 48m=70k.
    User requests 25k / 36m.
    24m has max_safe=30k >= 25k => feasible at 24m.
    36m also feasible.
    Shortest feasible term is 24m — even though 36m allows higher cap.
    """
    caps = {24: 30_000, 36: 50_000, 48: 70_000}
    payload = _Payload(loan_amount=25_000, term=36)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    assert result["suggested_term"]   == 24
    assert result["suggested_amount"] == 30_000


# ---------------------------------------------------------------------------
# Test 2 — Fallback: amount infeasible -> maximise reviewable amount
# ---------------------------------------------------------------------------

def test_fallback_picks_highest_reviewable_amount():
    """
    Caps: 12m=8k  (monthly=667), 24m=20k (monthly=833),
          36m=24k (monthly=667), 48m=24k (monthly=500), 60m=25k (monthly=417).
    User requests 50k — infeasible everywhere.
    Highest reviewable amount is 25k at 60m.
    """
    caps = {12: 8_000, 24: 20_000, 36: 24_000, 48: 24_000, 60: 25_000}
    payload = _Payload(loan_amount=50_000, term=12)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    assert result["suggested_term"] == 60, (
        f"expected term=60 (highest reviewable amount), got {result['suggested_term']}"
    )
    # suggested_amount must be max_reviewable for that term (~25k)
    assert result["suggested_amount"] > 0
    assert result["is_perfect_fit"] is False


def test_fallback_highest_amount_wins_over_lower_monthly_payment():
    """
    When a shorter term has a higher cap but a higher monthly payment,
    it still wins because the UI label is maximum reviewable amount.
    Caps: 24m=30_000 (monthly=1,250), 60m=25_000 (monthly=417).
    User requests 100k — infeasible everywhere.
    """
    caps = {24: 30_000, 60: 25_000}
    payload = _Payload(loan_amount=100_000, term=24)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    assert result["suggested_term"] == 24
    assert result["suggested_amount"] == 30_000


# ---------------------------------------------------------------------------
# Test 3 — All terms infeasible
# ---------------------------------------------------------------------------

def test_all_terms_infeasible_returns_minimum_loan():
    """No safe option at any term → return _MIN_LOAN without crashing."""
    caps = {}  # all terms return prob=0.50 (above HIGH)
    payload = _Payload(loan_amount=10_000, term=24)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    from services.loan_suggestion_service import _MIN_LOAN
    assert result["suggested_amount"] == _MIN_LOAN
    assert result["is_perfect_fit"] is False


# ---------------------------------------------------------------------------
# Test 4 — perfect_fit
# ---------------------------------------------------------------------------

def test_perfect_fit_when_requested_term_is_shortest_feasible():
    """
    Caps: 12m=0, 24m=22k.  User requests 20k / 24m.
    24m is the ONLY feasible term and user's term matches — perfect fit.
    """
    caps = {12: 0, 24: 22_000}
    payload = _Payload(loan_amount=20_000, term=24)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    assert result["suggested_term"]   == 24
    assert result["suggested_amount"] == 22_000
    assert result["is_perfect_fit"]   is True


def test_not_perfect_fit_when_shorter_term_is_available():
    """
    User requests 20k / 36m, but 24m can also support 20k.
    Suggested term = 24m (shorter) ≠ requested 36m → not perfect fit.
    """
    caps = {24: 25_000, 36: 40_000}
    payload = _Payload(loan_amount=20_000, term=36)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        result = compute_suggestion(payload, _BASE_ARTIFACT)

    assert result["suggested_term"]   == 24
    assert result["is_perfect_fit"]   is False


# ---------------------------------------------------------------------------
# Test 5 — validate_confirmed_values uses reviewable cap
# ---------------------------------------------------------------------------

def test_validate_confirmed_values_raises_when_exceeding_reviewable_cap():
    """validate_confirmed_values must reject amounts above max_reviewable."""
    caps = {24: 20_000}
    payload = _Payload(loan_amount=25_000, term=24)  # 25k > max_reviewable ~20k

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        try:
            validate_confirmed_values(payload, _BASE_ARTIFACT)
            raise AssertionError("Expected ValueError not raised")
        except ValueError as exc:
            assert "25" in str(exc) or "vượt" in str(exc).lower() or "mức" in str(exc).lower()


def test_validate_confirmed_values_passes_when_within_safe():
    """validate_confirmed_values must pass when amount <= max_reviewable."""
    caps = {24: 20_000}
    payload = _Payload(loan_amount=18_000, term=24)

    with patch("services.loan_suggestion_service._predict", _make_predictor(caps)):
        validate_confirmed_values(payload, _BASE_ARTIFACT)  # must not raise


if __name__ == "__main__":
    test_honours_requested_amount_with_shortest_term()
    test_shorter_term_wins_over_higher_amount()
    test_fallback_picks_highest_reviewable_amount()
    test_fallback_highest_amount_wins_over_lower_monthly_payment()
    test_all_terms_infeasible_returns_minimum_loan()
    test_perfect_fit_when_requested_term_is_shortest_feasible()
    test_not_perfect_fit_when_shorter_term_is_available()
    test_validate_confirmed_values_raises_when_exceeding_reviewable_cap()
    test_validate_confirmed_values_passes_when_within_safe()
    print("loan suggestion max-reviewable tests passed")
