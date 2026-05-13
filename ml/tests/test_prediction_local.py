"""
scripts/test_prediction_local.py
──────────────────────────────────
Example script to test predict_loan_risk() locally with multiple scenarios.
Useful for quick manual verification before FastAPI integration.

Run from project root:
    python scripts/test_prediction_local.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from predict import predict_loan_risk, validate_input

# ── Test scenarios ────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "name": "✅ Low Risk — Stable borrower",
        "input": {
            "monthly_income"   : 8000,
            "loan_amount"      : 10000,
            "term"             : 36,
            "employment_status": "Employed",
            "dti"              : 0.15,
            "is_homeowner"     : True,
            "listing_category" : 1,    # Debt Consolidation
            "credit_score"     : 750,
        },
        "expected_decision": "PENDING_REVIEW",
    },
    {
        "name": "🟡 Medium Risk — Average borrower",
        "input": {
            "monthly_income"   : 4000,
            "loan_amount"      : 12000,
            "term"             : 36,
            "employment_status": "Self-Employed",
            "dti"              : 0.32,
            "is_homeowner"     : False,
            "listing_category" : 2,    # Home Improvement
            "credit_score"     : 620,
        },
        "expected_decision": None,     # could go either way
    },
    {
        "name": "🔴 High Risk — Risky borrower",
        "input": {
            "monthly_income"   : 1500,
            "loan_amount"      : 25000,
            "term"             : 60,
            "employment_status": "Not Employed",
            "dti"              : 0.85,
            "is_homeowner"     : False,
            "listing_category" : 3,    # Business
            "credit_score"     : 350,
        },
        "expected_decision": "AUTO_REJECTED",
    },
    {
        "name": "🏠 Homeowner with short term + high risk",
        "input": {
            "monthly_income"   : 2000,
            "loan_amount"      : 8000,
            "term"             : 12,   # short term
            "employment_status": "Part-Time",
            "dti"              : 0.50,
            "is_homeowner"     : True,
            "listing_category" : 13,   # Household Expenses
            "credit_score"     : 480,
        },
        "expected_decision": None,
    },
    {
        "name": "💰 High income + low risk + long term",
        "input": {
            "monthly_income"   : 15000,
            "loan_amount"      : 20000,
            "term"             : 60,   # long term — should be shortened for Low risk
            "employment_status": "Employed",
            "dti"              : 0.10,
            "is_homeowner"     : True,
            "listing_category" : 1,
            "credit_score"     : 820,
        },
        "expected_decision": "PENDING_REVIEW",
    },
    {
        "name": "🔤 Lowercase employment_status (normalization test)",
        "input": {
            "monthly_income"   : 5000,
            "loan_amount"      : 10000,
            "term"             : 36,
            "employment_status": "self-employed",   # lowercase
            "dti"              : 0.20,
            "is_homeowner"     : False,
            "listing_category" : 7,    # Other
            "credit_score"     : 650,
        },
        "expected_decision": None,
    },
]

ERROR_SCENARIOS = [
    {
        "name": "❌ Missing credit_score",
        "input": {
            "monthly_income"   : 5000,
            "loan_amount"      : 10000,
            "term"             : 36,
            "employment_status": "Employed",
            "dti"              : 0.25,
            "is_homeowner"     : True,
            "listing_category" : 1,
            # credit_score missing
        },
        "expected_error": "Missing required fields",
    },
    {
        "name": "❌ Invalid term (24 months)",
        "input": {
            "monthly_income"   : 5000,
            "loan_amount"      : 10000,
            "term"             : 24,   # invalid
            "employment_status": "Employed",
            "dti"              : 0.25,
            "is_homeowner"     : True,
            "listing_category" : 1,
            "credit_score"     : 700,
        },
        "expected_error": "term must be one of",
    },
    {
        "name": "❌ Credit score out of range (200)",
        "input": {
            "monthly_income"   : 5000,
            "loan_amount"      : 10000,
            "term"             : 36,
            "employment_status": "Employed",
            "dti"              : 0.25,
            "is_homeowner"     : True,
            "listing_category" : 1,
            "credit_score"     : 200,  # invalid
        },
        "expected_error": "credit_score must be between 300 and 850",
    },
    {
        "name": "❌ Negative income",
        "input": {
            "monthly_income"   : -500,  # invalid
            "loan_amount"      : 10000,
            "term"             : 36,
            "employment_status": "Employed",
            "dti"              : 0.25,
            "is_homeowner"     : True,
            "listing_category" : 1,
            "credit_score"     : 700,
        },
        "expected_error": "monthly_income must be positive",
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_success_scenarios():
    print("\n" + "=" * 65)
    print("  PREDICTION SCENARIOS")
    print("=" * 65)

    passed = 0
    failed = 0

    for scenario in SCENARIOS:
        print(f"\n{scenario['name']}")
        print("-" * 55)

        try:
            result = predict_loan_risk(scenario["input"])

            print(f"  Probability of Default : {result['default_probability']:.4f}")
            print(f"  Risk Level             : {result['risk_level']}")
            print(f"  Risk Score             : {result['risk_score']} / 100")
            print(f"  Auto Decision          : {result['auto_decision']}")
            print(f"  Recommended Amount     : ${result['recommended_amount']:,.0f}")
            print(f"  Recommended Term       : {result['recommended_term']} months")
            print(f"  Category               : {result['category_label']}")

            # Check term recommendation logic
            req_term  = scenario["input"]["term"]
            rec_term  = result["recommended_term"]
            risk      = result["risk_level"]
            if req_term != rec_term:
                print(f"  ⚠ Term adjusted: {req_term}m → {rec_term}m (risk={risk})")

            # Check expected decision
            expected = scenario.get("expected_decision")
            if expected and result["auto_decision"] != expected:
                print(f"  ⚠ Expected {expected}, got {result['auto_decision']}")
                failed += 1
            else:
                print(f"  ✓ Pass")
                passed += 1

        except Exception as e:
            print(f"  ✗ UNEXPECTED ERROR: {e}")
            failed += 1

    return passed, failed


def run_error_scenarios():
    print("\n" + "=" * 65)
    print("  ERROR HANDLING SCENARIOS")
    print("=" * 65)

    passed = 0
    failed = 0

    for scenario in ERROR_SCENARIOS:
        print(f"\n{scenario['name']}")
        print("-" * 55)

        try:
            predict_loan_risk(scenario["input"])
            # Should have raised — if we get here it's a failure
            print(f"  ✗ FAIL — Expected ValueError but no error raised")
            failed += 1

        except ValueError as e:
            expected_msg = scenario["expected_error"]
            if expected_msg in str(e):
                print(f"  ✓ Correctly raised ValueError: {e}")
                passed += 1
            else:
                print(f"  ✗ Wrong error message.")
                print(f"    Expected: '{expected_msg}'")
                print(f"    Got     : '{e}'")
                failed += 1

        except FileNotFoundError as e:
            print(f"  ✗ Model not found: {e}")
            failed += 1

        except Exception as e:
            print(f"  ✗ Wrong error type {type(e).__name__}: {e}")
            failed += 1

    return passed, failed


def main():
    print("\nCreditIntel — Local Prediction Test")
    print("Running ml/predict.py with sample scenarios...\n")

    s_passed, s_failed = run_success_scenarios()
    e_passed, e_failed = run_error_scenarios()

    total_passed = s_passed + e_passed
    total_failed = s_failed + e_failed
    total        = total_passed + total_failed

    print("\n" + "=" * 65)
    print(f"  RESULTS: {total_passed}/{total} passed")
    if total_failed > 0:
        print(f"  ✗ {total_failed} scenario(s) failed — check output above")
    else:
        print("  ✓ All scenarios passed")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()