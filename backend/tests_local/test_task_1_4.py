import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    # 1. Register Alice
    resp = client.post("/auth/register", json={"email": "alice@gmail.com", "username": "alice", "password": "123"})
    
    # 2. Login Alice
    token_alice = client.post("/auth/login", json={"email": "alice@gmail.com", "password": "123"}).json()["access_token"]
    headers_alice = {"Authorization": f"Bearer {token_alice}"}
    
    # 3. Submit App Alice
    payload = {"monthly_income": 5000, "loan_amount": 10000, "term": 24, "employment_status": "Employed", "dti": 0.3, "is_homeowner": True, "listing_category": 1, "credit_score": 700}
    app_id = client.post("/applications/submit", json=payload, headers=headers_alice).json()["application_id"]
    print("Alice App ID:", app_id)
    
    # 4. Get List Alice
    resp_me = client.get("/applications/me", headers=headers_alice)
    print("GET /applications/me:", resp_me.status_code)
    print(resp_me.text)
    
    # 5. Get Detail Alice
    resp_detail = client.get(f"/applications/{app_id}", headers=headers_alice)
    print("GET detail (owner):", resp_detail.status_code)
    
    # 6. Register Bob
    client.post("/auth/register", json={"email": "bob@gmail.com", "username": "bob", "password": "123"})
    token_bob = client.post("/auth/login", json={"email": "bob@gmail.com", "password": "123"}).json()["access_token"]
    headers_bob = {"Authorization": f"Bearer {token_bob}"}
    
    # 7. Get Detail Alice by Bob (Expect 403)
    resp_forbidden = client.get(f"/applications/{app_id}", headers=headers_bob)
    print("GET detail (non-owner):", resp_forbidden.status_code)
    print(resp_forbidden.text)

except Exception as e:
    traceback.print_exc()
