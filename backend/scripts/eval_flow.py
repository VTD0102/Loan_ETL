import sys
import os
import random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal, BureauSessionLocal
from services import auth_service, application_service, cic_service
from schemas.user import UserCreate
from schemas.application import ApplicationCreate, ApplicationConfirm

def main():
    db = SessionLocal()
    bureau_db = BureauSessionLocal()
    
    # 1. Register a new user
    email = f"test.eval.{random.randint(1000, 9999)}@example.com"
    cccd = f"0123{random.randint(10000000, 99999999)}"
    
    payload = UserCreate(
        email=email,
        username="Test Eval",
        password="Password123!",
        cccd=cccd,
        full_name="Nguyễn Văn Test",
        phone="0912345678",
        address="123 ABC"
    )
    
    print("--- 1. REGISTER ---")
    user_res = auth_service.register(db, bureau_db, payload)
    print(f"User created: {user_res['user'].email}")
    
    # Check CIC in bureau_db
    cic = cic_service.lookup_by_cccd(bureau_db, cccd)
    print(f"CIC Generated: Score={cic.cic_score}, Loans={cic.total_active_loans}, Debt={cic.total_outstanding_debt}, Installment={cic.total_monthly_installment}")
    
    # 2. Evaluate Loan Application
    app_payload = ApplicationCreate(
        loan_amount=5000,
        term=12,
        monthly_income=2500,
        employment_status="Employed",
        occupation_type="IT",
        years_employed=5,
        is_homeowner=True,
        listing_category="Personal",
        age_years=30,
        gender_male_flag=True,
        education_ordinal=4,
        cnt_children=0,
        cnt_fam_members=1,
        is_married_flag=False,
        num_bureau_records=0, # User self-reports 0
        num_active_credit=0,
        total_overdue_amount=0,
        max_credit_overdue_days=0,
        has_bad_debt=False
    )
    print("\n--- 2. EVALUATE ---")
    eval_res = application_service.evaluate(db, bureau_db, email, app_payload)
    print(f"Status: {eval_res['status']}")
    print(f"Prob: {eval_res['default_probability']:.2f}")
    print(f"Risk Level: {eval_res['risk_level']}")
    print(f"Suggested Amount: {eval_res['suggested_amount']}")
    print(f"Computed DTI: {eval_res['computed_dti']:.2f}")
    print(f"CIC Summary Found: {eval_res['cic_summary']['found']}")
    
    # 3. Confirm Loan Application
    print("\n--- 3. CONFIRM ---")
    confirm_payload = ApplicationConfirm(
        **app_payload.model_dump(),
        dti=eval_res['computed_dti'],
        cic_monthly_installment=eval_res['cic_summary'].get('total_monthly_installment', 0)
    )
    
    try:
        confirm_res = application_service.confirm(db, bureau_db, email, confirm_payload)
        print(f"Confirmed App ID: {confirm_res['application_id']}, Status: {confirm_res['status']}")
    except Exception as e:
        print(f"Confirm Error: {e}")

if __name__ == '__main__':
    main()
