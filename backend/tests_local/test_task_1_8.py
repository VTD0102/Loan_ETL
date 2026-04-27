import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # Register/Login Admin
    admin_email = "admin1@gmail.com"
    token_admin = client.post("/auth/login", json={"email": admin_email, "password": "123"}).json()["access_token"]
    h_admin = {"Authorization": f"Bearer {token_admin}"}
    
    # User A (Approve)
    client.post("/auth/register", json={"email": "user18a@gmail.com", "username": "u18a", "password": "123"})
    t_a = client.post("/auth/login", json={"email": "user18a@gmail.com", "password": "123"}).json()["access_token"]
    h_a = {"Authorization": f"Bearer {t_a}"}
    
    # User B (Reject)
    client.post("/auth/register", json={"email": "user18b@gmail.com", "username": "u18b", "password": "123"})
    t_b = client.post("/auth/login", json={"email": "user18b@gmail.com", "password": "123"}).json()["access_token"]
    h_b = {"Authorization": f"Bearer {t_b}"}
    
    payload = {"monthly_income": 5000, "loan_amount": 10000, "term": 24, "employment_status": "Employed", "dti": 0.3, "is_homeowner": True, "listing_category": 1, "credit_score": 700}
    
    app_id_a = client.post("/applications/submit", json=payload, headers=h_a).json()["application_id"]
    app_id_b = client.post("/applications/submit", json=payload, headers=h_b).json()["application_id"]
    
    print("\n--- Testing GET /admin/applications/{id}/approve ---")
    resp_approve = client.post(f"/admin/applications/{app_id_a}/approve", headers=h_admin)
    print(resp_approve.status_code)
    print("Status:", resp_approve.json().get("status"), "| Reviewed:", resp_approve.json().get("reviewed_at") is not None)
    
    print("\n--- Testing GET /admin/applications/{id}/reject ---")
    resp_reject = client.post(f"/admin/applications/{app_id_b}/reject", json={"admin_note": "Score too low"}, headers=h_admin)
    print(resp_reject.status_code)
    print("Status:", resp_reject.json().get("status"), "| Note:", resp_reject.json().get("admin_note"))

except Exception as e:
    traceback.print_exc()

