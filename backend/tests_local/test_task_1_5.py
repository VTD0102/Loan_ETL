import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    from db.session import SessionLocal
    from models.application import LoanApplication
    
    client = TestClient(app)
    
    # 1. Register & Login
    client.post("/auth/register", json={"email": "user15@gmail.com", "username": "user15", "password": "123"})
    token = client.post("/auth/login", json={"email": "user15@gmail.com", "password": "123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Submit App
    payload = {"monthly_income": 5000, "loan_amount": 10000, "term": 24, "employment_status": "Employed", "dti": 0.3, "is_homeowner": True, "listing_category": 1, "credit_score": 700}
    app_id = client.post("/applications/submit", json=payload, headers=headers).json()["application_id"]
    print("Test App ID:", app_id)
    
    personal_payload = {
        "full_name": "Minh Phi 15",
        "id_card_number": "001234567890",
        "phone": "0901234567",
        "email": "user15@gmail.com",
        "date_of_birth": "1990-01-01",
        "address": "123 Test St, Vietnam"
    }

    # 3. Test submitting personal info early (Expect 400)
    resp_early = client.post(f"/applications/{app_id}/personal-info", json=personal_payload, headers=headers)
    print("Submit early:", resp_early.status_code, resp_early.text)
    
    # 4. Modify App Status manually using DB
    db = SessionLocal()
    loan_app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    loan_app.status = 'AWAITING_INFO'
    db.commit()
    db.close()
    print("Manually updated status to AWAITING_INFO")
    
    # 5. Test submitting personal info properly (Expect 201)
    resp_success = client.post(f"/applications/{app_id}/personal-info", json=personal_payload, headers=headers)
    print("Submit success:", resp_success.status_code)
    
    if resp_success.status_code == 201:
        # Check DB status
        db = SessionLocal()
        loan_app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
        print("Final application status in DB:", loan_app.status)
        db.close()

except Exception as e:
    traceback.print_exc()
