import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    from db.session import SessionLocal
    from models.user import User
    
    client = TestClient(app)
    
    # Register Admin
    email = "admin1@gmail.com"
    client.post("/auth/register", json={"email": email, "username": "admin1", "password": "123"})
    
    # Escalate to admin in DB
    db = SessionLocal()
    admin_user = db.query(User).filter(User.email == email).first()
    if admin_user:
        admin_user.role = 'admin'
        db.commit()
    db.close()
    print("User updated to admin role.")

    # Login Admin
    token = client.post("/auth/login", json={"email": email, "password": "123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test Dashboard Summary
    print("\n--- Testing GET /admin/dashboard/summary ---")
    resp_sum = client.get("/admin/dashboard/summary", headers=headers)
    print(resp_sum.status_code, resp_sum.text)

    # Test Dashboard Risk Distribution
    print("\n--- Testing GET /admin/dashboard/risk-distribution ---")
    resp_risk = client.get("/admin/dashboard/risk-distribution", headers=headers)
    print(resp_risk.status_code, resp_risk.text)
    
except Exception as e:
    traceback.print_exc()

