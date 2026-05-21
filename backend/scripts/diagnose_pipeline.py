#!/usr/bin/env python3
"""
Diagnostic script — Tests the ML pipeline to find logic issues.
Checks: term sensitivity, DTI floor behavior, suggestion consistency.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from services import ml_service
from services.model_feature_builder import build_model_input, apply_dti_risk_floor, compute_combined_dti
from schemas.application import ApplicationCreate

def make_payload(**overrides):
    defaults = dict(
        monthly_income=Decimal("5000"),
        loan_amount=Decimal("15000"),
        term=36,
        dti=None,
        employment_status="Employed",
        occupation_type="EMPLOYED",
        years_employed=5.0,
        is_homeowner=True,
        listing_category="Personal Loan",
        age_years=35,
        education_ordinal=3,
        is_married_flag=True,
        income_verifiable_flag=True,
        num_bureau_records=3,
        num_active_credit=1,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        cic_monthly_installment=Decimal("200"),
    )
    defaults.update(overrides)
    return ApplicationCreate(**defaults)

def test_term_sensitivity():
    """Test how different terms affect probability for the same loan."""
    print("=" * 70)
    print("TEST 1: Term Sensitivity (same loan $15,000, income $5,000, CIC debt $200/mo)")
    print("=" * 70)
    artifact = ml_service._load()
    thresholds = artifact["thresholds"]
    LOW = float(thresholds["low"])
    HIGH = float(thresholds["high"])
    print(f"Thresholds: LOW={LOW}, HIGH={HIGH}")
    print()

    for term in [12, 24, 36, 48, 60]:
        payload = make_payload(term=term)
        built = build_model_input(payload, artifact)
        import pandas as pd
        row = pd.DataFrame([built.features], columns=artifact["feature_cols"])
        raw_prob = float(artifact["pipeline"].predict_proba(row)[0, 1])
        dti = built.features.get("dti", 0)
        adjusted = apply_dti_risk_floor(raw_prob, dti, low_threshold=LOW, high_threshold=HIGH)
        monthly = 15000 / term
        status = "OK" if adjusted < HIGH else "REJECTED"
        print(f"  Term={term:2d}mo | Monthly=${monthly:>7.0f} | DTI={dti:.3f} | "
              f"Raw={raw_prob:.4f} | Adjusted={adjusted:.4f} | {status}")

    print()

def test_dti_floor_impact():
    """Test DTI floor behavior across different DTI levels."""
    print("=" * 70)
    print("TEST 2: DTI Risk Floor Behavior")
    print("=" * 70)
    artifact = ml_service._load()
    thresholds = artifact["thresholds"]
    LOW = float(thresholds["low"])
    HIGH = float(thresholds["high"])

    for dti_pct in [10, 20, 30, 35, 38, 40, 43, 50, 60, 70, 80]:
        dti = dti_pct / 100
        # Simulate raw_prob of 0.15 (low risk)
        floor = apply_dti_risk_floor(0.15, dti, low_threshold=LOW, high_threshold=HIGH)
        status = "OK" if floor < HIGH else "FLOOR-REJECTED"
        print(f"  DTI={dti_pct:3d}% | Raw=0.15 | After Floor={floor:.4f} | {status}")
    print()

def test_binary_search_per_term():
    """Test max reviewable amount per term."""
    print("=" * 70)
    print("TEST 3: Max Reviewable Amount per Term (income $5000, CIC $200/mo)")
    print("=" * 70)
    from services.loan_suggestion_service import _binary_search, _predict, _MIN_LOAN
    artifact = ml_service._load()
    HIGH = float(artifact["thresholds"]["high"])
    payload = make_payload(loan_amount=Decimal("10000"))

    for term in [12, 24, 36, 48, 60]:
        p_min = _predict(payload, artifact, _MIN_LOAN, term, [])
        if p_min >= HIGH:
            print(f"  Term={term:2d}mo | ENTIRELY BLOCKED (even $500 gives prob={p_min:.4f} >= {HIGH})")
        else:
            max_amt = _binary_search(payload, artifact, term, HIGH, [])
            print(f"  Term={term:2d}mo | Max Reviewable=${max_amt:>10,.0f} | min_prob={p_min:.4f}")
    print()

def test_varying_cic_debt():
    """Test how CIC debt levels affect results."""
    print("=" * 70)
    print("TEST 4: CIC Monthly Debt Impact (income $5000, loan $10000, term=36)")
    print("=" * 70)
    artifact = ml_service._load()
    thresholds = artifact["thresholds"]
    LOW = float(thresholds["low"])
    HIGH = float(thresholds["high"])

    for cic in [0, 100, 300, 500, 800, 1000, 1500, 2000]:
        payload = make_payload(
            loan_amount=Decimal("10000"), term=36,
            cic_monthly_installment=Decimal(str(cic))
        )
        built = build_model_input(payload, artifact)
        import pandas as pd
        row = pd.DataFrame([built.features], columns=artifact["feature_cols"])
        raw_prob = float(artifact["pipeline"].predict_proba(row)[0, 1])
        dti = built.features.get("dti", 0)
        adjusted = apply_dti_risk_floor(raw_prob, dti, low_threshold=LOW, high_threshold=HIGH)
        status = "OK" if adjusted < HIGH else "REJECTED"
        print(f"  CIC=${cic:>5}/mo | DTI={dti:.3f} | Raw={raw_prob:.4f} | "
              f"Adjusted={adjusted:.4f} | {status}")
    print()

def test_synthetic_consistency():
    """Check if synthetic data is logically consistent."""
    print("=" * 70)
    print("TEST 5: Synthetic Data Consistency Check")
    print("=" * 70)
    from services.synthetic_service import _generate_good_profile, _generate_risky_profile, _generate_defaulter_profile
    
    issues = []
    for name, gen in [("good", _generate_good_profile), ("risky", _generate_risky_profile), ("defaulter", _generate_defaulter_profile)]:
        for trial in range(20):
            p = gen()
            cic = p["_cic"]
            
            # Check: outstanding debt > 0 but active loans = 0
            if cic["total_outstanding_debt"] > 0 and cic["total_active_loans"] == 0:
                issues.append(f"  [{name}] Dư nợ ${cic['total_outstanding_debt']:.0f} nhưng active_loans=0")
            
            # Check: loan_history doesn't have active entries but total_active_loans > 0
            active_in_history = sum(1 for h in cic.get("loan_history", []) if h.get("status") == "active")
            if cic["total_active_loans"] > 0 and active_in_history == 0 and name == "good":
                issues.append(f"  [{name}] active_loans={cic['total_active_loans']} nhưng loan_history toàn closed")
            
            # Check: monthly installment > outstanding debt (impossible)
            if cic["total_monthly_installment"] > cic["total_outstanding_debt"] and cic["total_outstanding_debt"] > 0:
                issues.append(f"  [{name}] Trả hàng tháng ${cic['total_monthly_installment']:.0f} > Tổng dư nợ ${cic['total_outstanding_debt']:.0f}")
            
            # Check: CIC score high but bad_debt = True
            if cic.get("cic_score", 0) >= 650 and cic.get("bad_debt_flag"):
                issues.append(f"  [{name}] CIC={cic['cic_score']} nhưng bad_debt=True")

    if issues:
        # Deduplicate similar issues
        seen = set()
        for issue in issues:
            key = issue[:60]
            if key not in seen:
                seen.add(key)
                print(issue)
        print(f"\n  Tổng: {len(issues)} vi phạm logic trong 60 mẫu thử")
    else:
        print("  ✅ Tất cả 60 mẫu thử đều hợp lệ")
    print()


if __name__ == "__main__":
    test_term_sensitivity()
    test_dti_floor_impact()
    test_binary_search_per_term()
    test_varying_cic_debt()
    test_synthetic_consistency()
