import traceback
from datetime import datetime, timedelta
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    from db.session import SessionLocal
    from models.user import User
    from models.application import LoanApplication
    
    client = TestClient(app)
    
    # 1. Login Admin
    email = "admin1@gmail.com"
    token = client.post("/auth/login", json={"email": email, "password": "123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Plant some test data
    db = SessionLocal()
    admin_user = db.query(User).filter(User.email == email).first()
    
    # delete all pending reviews to have a clean slate for testing sort
    db.query(LoanApplication).filter(LoanApplication.status == 'PENDING_REVIEW').delete()
    db.commit()

    base_time = datetime.now() - timedelta(days=1)
    for i in range(5):
        new_app = LoanApplication(
            user_id=admin_user.id,
            status="PENDING_REVIEW",
            monthly_income=5000 + i*100,
            loan_amount=10000 + i*1000,
            term=24,
            employment_status="Employed",
            dti=0.3,
            is_homeowner=True,
            listing_category=1,
            credit_score=700 + i,
            submitted_at=base_time + timedelta(hours=i)
        )
        db.add(new_app)
    db.commit()
    db.close()
    
    # 3. Test Pagination page=1 limit=2
    print("\n--- Testing GET /admin/applications/pending?page=1&limit=2 ---")
    resp_p1 = client.get("/admin/applications/pending?page=1&limit=2", headers=headers)
    print(resp_p1.status_code, resp_p1.text)
    
    # 4. Test page 2
    print("\n--- Testing GET /admin/applications/pending?page=2&limit=2 ---")
    resp_p2 = client.get("/admin/applications/pending?page=2&limit=2", headers=headers)
    print(resp_p2.status_code, resp_p2.text)

except Exception as e:
    traceback.print_exc()

