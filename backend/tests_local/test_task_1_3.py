import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    print("App loaded successfully. Testing /health...")
    resp = client.get("/health")
    print("Health response:", resp.status_code, resp.text)
    
    import random
    cccd = f"079099{random.randint(100000, 999999)}"
    # 1. Register
    print("\n--- Registering User ---")
    resp = client.post("/auth/register", json={
        "email": "user13@gmail.com",
        "username": "user13",
        "password": "123",
        "cccd": cccd,
        "full_name": "User Thirteen",
        "phone": "0901234567",
        "address": "123 Test St"
    })
    print(resp.status_code, resp.text)
    if resp.status_code not in (201, 400): exit(1)
    
    # 2. Login
    print("\n--- Logging in ---")
    resp = client.post("/auth/login", json={
        "email": "user13@gmail.com",
        "password": "123"
    })
    print(resp.status_code, resp.text)
    if resp.status_code != 200: exit(1)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Submit application
    print("\n--- Submitting Application ---")
    payload = {
        "monthly_income": 5000,
        "loan_amount": 10000,
        "term": 24,
        "employment_status": "Employed",
        "dti": 0.3,
        "is_homeowner": True,
        "listing_category": 1,
        "credit_score": 700
    }
    resp = client.post("/applications/submit", json=payload, headers=headers)
    print(resp.status_code, resp.text)
    
    # 4. Submit again -> expect 400
    print("\n--- Submitting Application Again (Expect 400) ---")
    resp = client.post("/applications/submit", json=payload, headers=headers)
    print(resp.status_code, resp.text)
    
except Exception as e:
    traceback.print_exc()

