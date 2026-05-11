"""
tests/test_ml_predict.py
─────────────────────────
Unit tests for ml/predict.py

Run:
    pytest tests/test_ml_predict.py -v
    pytest tests/test_ml_predict.py -v --tb=short   # compact output
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from predict import (
    validate_input,
    predict_loan_risk,
    get_risk_level,
    get_risk_score,
    get_recommended_amount,
    get_recommended_term,
    get_auto_decision,
    VALID_TERMS,
    VALID_EMPLOYMENT,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_input():
    """Standard valid input — low risk profile."""
    return {
        "monthly_income"   : 5000.0,
        "loan_amount"      : 15000.0,
        "term"             : 36,
        "employment_status": "Employed",
        "dti"              : 0.25,
        "is_homeowner"     : True,
        "listing_category" : 1,
        "credit_score"     : 700.0,
    }


@pytest.fixture
def high_risk_input():
    """High risk profile — should return AUTO_REJECTED."""
    return {
        "monthly_income"   : 1500.0,
        "loan_amount"      : 25000.0,
        "term"             : 60,
        "employment_status": "Not Employed",
        "dti"              : 0.85,
        "is_homeowner"     : False,
        "listing_category" : 3,
        "credit_score"     : 350.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — validate_input()
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateInput:

    def test_valid_input_passes(self, valid_input):
        """Valid input should not raise."""
        validate_input(valid_input)   # no exception

    def test_missing_single_field(self, valid_input):
        """Missing one required field should raise ValueError."""
        del valid_input["credit_score"]
        with pytest.raises(ValueError, match="Missing required fields"):
            validate_input(valid_input)

    def test_missing_multiple_fields(self, valid_input):
        """Missing multiple fields should raise ValueError."""
        del valid_input["credit_score"]
        del valid_input["dti"]
        with pytest.raises(ValueError, match="Missing required fields"):
            validate_input(valid_input)

    def test_not_dict_raises_type_error(self):
        """Non-dict input should raise TypeError."""
        with pytest.raises(TypeError):
            validate_input("not a dict")

    # ── monthly_income ───────────────────────────────────

    def test_negative_income_raises(self, valid_input):
        valid_input["monthly_income"] = -100
        with pytest.raises(ValueError, match="monthly_income must be positive"):
            validate_input(valid_input)

    def test_zero_income_raises(self, valid_input):
        valid_input["monthly_income"] = 0
        with pytest.raises(ValueError, match="monthly_income must be positive"):
            validate_input(valid_input)

    def test_string_income_raises(self, valid_input):
        valid_input["monthly_income"] = "five thousand"
        with pytest.raises(ValueError, match="monthly_income must be a number"):
            validate_input(valid_input)

    def test_very_high_income_raises(self, valid_input):
        valid_input["monthly_income"] = 2_000_000
        with pytest.raises(ValueError, match="unreasonably high"):
            validate_input(valid_input)

    # ── loan_amount ──────────────────────────────────────

    def test_negative_loan_amount_raises(self, valid_input):
        valid_input["loan_amount"] = -5000
        with pytest.raises(ValueError, match="loan_amount must be positive"):
            validate_input(valid_input)

    def test_loan_amount_exceeds_max_raises(self, valid_input):
        valid_input["loan_amount"] = 600_000
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_input(valid_input)

    # ── term ─────────────────────────────────────────────

    def test_invalid_term_raises(self, valid_input):
        valid_input["term"] = 24   # not in [12, 36, 60]
        with pytest.raises(ValueError, match="term must be one of"):
            validate_input(valid_input)

    @pytest.mark.parametrize("term", VALID_TERMS)
    def test_all_valid_terms_pass(self, valid_input, term):
        valid_input["term"] = term
        validate_input(valid_input)   # no exception

    # ── employment_status ────────────────────────────────

    def test_invalid_employment_raises(self, valid_input):
        valid_input["employment_status"] = "Pirate"
        with pytest.raises(ValueError, match="employment_status"):
            validate_input(valid_input)

    def test_lowercase_employment_passes(self, valid_input):
        """Normalization should handle lowercase."""
        valid_input["employment_status"] = "employed"
        validate_input(valid_input)   # no exception

    def test_self_employed_lowercase_passes(self, valid_input):
        valid_input["employment_status"] = "self-employed"
        validate_input(valid_input)

    # ── dti ──────────────────────────────────────────────

    def test_negative_dti_raises(self, valid_input):
        valid_input["dti"] = -0.1
        with pytest.raises(ValueError, match="dti cannot be negative"):
            validate_input(valid_input)

    def test_very_high_dti_raises(self, valid_input):
        valid_input["dti"] = 11.0
        with pytest.raises(ValueError, match="unreasonably high"):
            validate_input(valid_input)

    def test_zero_dti_passes(self, valid_input):
        valid_input["dti"] = 0.0
        validate_input(valid_input)

    # ── credit_score ─────────────────────────────────────

    def test_credit_score_below_300_raises(self, valid_input):
        valid_input["credit_score"] = 299
        with pytest.raises(ValueError, match="credit_score must be between 300 and 850"):
            validate_input(valid_input)

    def test_credit_score_above_850_raises(self, valid_input):
        valid_input["credit_score"] = 851
        with pytest.raises(ValueError, match="credit_score must be between 300 and 850"):
            validate_input(valid_input)

    def test_boundary_credit_scores_pass(self, valid_input):
        for score in [300, 850]:
            valid_input["credit_score"] = score
            validate_input(valid_input)

    # ── listing_category ─────────────────────────────────

    def test_invalid_listing_category_raises(self, valid_input):
        valid_input["listing_category"] = 99
        with pytest.raises(ValueError, match="listing_category must be 0–20"):
            validate_input(valid_input)

    def test_boundary_listing_categories_pass(self, valid_input):
        for cat in [0, 20]:
            valid_input["listing_category"] = cat
            validate_input(valid_input)

    # ── is_homeowner ─────────────────────────────────────

    def test_is_homeowner_string_raises(self, valid_input):
        valid_input["is_homeowner"] = "yes"
        with pytest.raises(ValueError, match="is_homeowner must be True/False"):
            validate_input(valid_input)

    def test_is_homeowner_int_passes(self, valid_input):
        for val in [0, 1]:
            valid_input["is_homeowner"] = val
            validate_input(valid_input)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Business logic functions
# ══════════════════════════════════════════════════════════════════════════════

class TestGetRiskLevel:

    def test_low_risk(self):
        assert get_risk_level(0.10, {"low": 0.2, "high": 0.4}) == "Low"

    def test_medium_risk(self):
        assert get_risk_level(0.30, {"low": 0.2, "high": 0.4}) == "Medium"

    def test_high_risk(self):
        assert get_risk_level(0.55, {"low": 0.2, "high": 0.4}) == "High"

    def test_boundary_low_medium(self):
        # exactly at low threshold → Medium
        assert get_risk_level(0.20, {"low": 0.2, "high": 0.4}) == "Medium"

    def test_boundary_medium_high(self):
        # exactly at high threshold → Medium
        assert get_risk_level(0.40, {"low": 0.2, "high": 0.4}) == "Medium"

    def test_just_above_high_threshold(self):
        assert get_risk_level(0.401, {"low": 0.2, "high": 0.4}) == "High"


class TestGetRiskScore:

    def test_zero_probability(self):
        assert get_risk_score(0.0) == 100

    def test_full_probability(self):
        assert get_risk_score(1.0) == 0

    def test_half_probability(self):
        assert get_risk_score(0.5) == 50

    def test_low_probability(self):
        assert get_risk_score(0.10) == 90

    def test_returns_int(self):
        assert isinstance(get_risk_score(0.25), int)


class TestGetRecommendedAmount:

    def test_low_risk_full_amount(self):
        assert get_recommended_amount(10000, "Low") == 10000.0

    def test_medium_risk_reduce_20_percent(self):
        assert get_recommended_amount(10000, "Medium") == 8000.0

    def test_high_risk_reduce_40_percent(self):
        assert get_recommended_amount(10000, "High") == 6000.0

    def test_rounding_to_nearest_100(self):
        # 10050 * 0.8 = 8040 → rounds to 8000
        result = get_recommended_amount(10050, "Medium")
        assert result % 100 == 0

    def test_large_amount_low_risk(self):
        assert get_recommended_amount(50000, "Low") == 50000.0

    def test_large_amount_high_risk(self):
        assert get_recommended_amount(50000, "High") == 30000.0


class TestGetRecommendedTerm:

    def test_high_risk_short_term_extended(self):
        """HIGH risk + 12 months → suggest 36 months."""
        assert get_recommended_term(12, "High") == 36

    def test_low_risk_long_term_shortened(self):
        """LOW risk + 60 months → suggest 36 months."""
        assert get_recommended_term(60, "Low") == 36

    def test_medium_risk_keeps_term(self):
        for term in VALID_TERMS:
            assert get_recommended_term(term, "Medium") == term

    def test_high_risk_36_keeps_term(self):
        assert get_recommended_term(36, "High") == 36

    def test_high_risk_60_keeps_term(self):
        assert get_recommended_term(60, "High") == 60

    def test_low_risk_12_keeps_term(self):
        assert get_recommended_term(12, "Low") == 12

    def test_low_risk_36_keeps_term(self):
        assert get_recommended_term(36, "Low") == 36


class TestGetAutoDecision:

    def test_auto_rejected_high_probability(self):
        assert get_auto_decision(0.55, {"low": 0.2, "high": 0.4}) == "AUTO_REJECTED"

    def test_pending_review_medium_probability(self):
        assert get_auto_decision(0.30, {"low": 0.2, "high": 0.4}) == "PENDING_REVIEW"

    def test_pending_review_low_probability(self):
        assert get_auto_decision(0.10, {"low": 0.2, "high": 0.4}) == "PENDING_REVIEW"

    def test_boundary_exactly_at_threshold(self):
        # exactly 0.4 → PENDING_REVIEW (not > 0.4)
        assert get_auto_decision(0.40, {"low": 0.2, "high": 0.4}) == "PENDING_REVIEW"

    def test_just_above_threshold(self):
        assert get_auto_decision(0.401, {"low": 0.2, "high": 0.4}) == "AUTO_REJECTED"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — predict_loan_risk() integration tests
# Requires customer_risk_model.pkl to be present
# Skip gracefully if model not found
# ══════════════════════════════════════════════════════════════════════════════

MODEL_EXISTS = (
    Path(__file__).resolve().parents[1] /
    "ml" / "models" / "customer_risk_model.pkl"
).exists()


@pytest.mark.skipif(not MODEL_EXISTS, reason="customer_risk_model.pkl not found — run retrain first")
class TestPredictLoanRisk:

    def test_returns_all_required_keys(self, valid_input):
        result = predict_loan_risk(valid_input)
        expected_keys = {
            "default_probability", "risk_level", "risk_score",
            "auto_decision", "recommended_amount", "recommended_term",
            "category_label", "assessed_at",
        }
        assert expected_keys.issubset(result.keys())

    def test_probability_between_0_and_1(self, valid_input):
        result = predict_loan_risk(valid_input)
        assert 0.0 <= result["default_probability"] <= 1.0

    def test_risk_level_valid_values(self, valid_input):
        result = predict_loan_risk(valid_input)
        assert result["risk_level"] in ("Low", "Medium", "High")

    def test_risk_score_range(self, valid_input):
        result = predict_loan_risk(valid_input)
        assert 0 <= result["risk_score"] <= 100

    def test_auto_decision_valid_values(self, valid_input):
        result = predict_loan_risk(valid_input)
        assert result["auto_decision"] in ("AUTO_REJECTED", "PENDING_REVIEW")

    def test_low_risk_profile_pending_review(self, valid_input):
        """Good profile should NOT be auto rejected."""
        result = predict_loan_risk(valid_input)
        assert result["auto_decision"] == "PENDING_REVIEW"

    def test_high_risk_profile_auto_rejected(self, high_risk_input):
        """Very bad profile should be auto rejected."""
        result = predict_loan_risk(high_risk_input)
        assert result["auto_decision"] == "AUTO_REJECTED"

    def test_recommended_amount_not_exceed_requested(self, valid_input):
        """Recommended amount should never exceed requested."""
        result = predict_loan_risk(valid_input)
        assert result["recommended_amount"] <= valid_input["loan_amount"]

    def test_category_label_returned(self, valid_input):
        """Category 1 should return Debt Consolidation."""
        result = predict_loan_risk(valid_input)
        assert result["category_label"] == "Debt Consolidation"

    def test_lowercase_employment_normalized(self, valid_input):
        """Lowercase employment_status should be normalized and work."""
        valid_input["employment_status"] = "employed"
        result = predict_loan_risk(valid_input)
        assert result["risk_level"] in ("Low", "Medium", "High")

    def test_invalid_input_raises_before_model(self, valid_input):
        """Validation error should raise before touching the model."""
        valid_input["credit_score"] = 200   # invalid
        with pytest.raises(ValueError, match="credit_score"):
            predict_loan_risk(valid_input)

    def test_assessed_at_is_iso_string(self, valid_input):
        """assessed_at should be ISO 8601 string."""
        result = predict_loan_risk(valid_input)
        from datetime import datetime
        # Should parse without error
        datetime.fromisoformat(result["assessed_at"])

    def test_deterministic_output(self, valid_input):
        """Same input should produce same output."""
        result1 = predict_loan_risk(valid_input)
        result2 = predict_loan_risk(valid_input)
        assert result1["default_probability"] == result2["default_probability"]
        assert result1["risk_level"] == result2["risk_level"]