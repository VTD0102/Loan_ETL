import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # User for Good Credit
    client.post("/auth/register", json={"email": "user11_good@gmail.com", "username": "u11_good", "password": "123"})
    t_good = client.post("/auth/login", json={"email": "user11_good@gmail.com", "password": "123"}).json()["access_token"]
    h_good = {"Authorization": f"Bearer {t_good}"}
    
    # User for Bad Credit
    client.post("/auth/register", json={"email": "user11_bad@gmail.com", "username": "u11_bad", "password": "123"})
    t_bad = client.post("/auth/login", json={"email": "user11_bad@gmail.com", "password": "123"}).json()["access_token"]
    h_bad = {"Authorization": f"Bearer {t_bad}"}
    
    # Test Good Credit (Score 700) -> Low Risk -> PENDING_REVIEW
    payload_good = {"monthly_income": 8000, "loan_amount": 10000, "term": 24, "employment_status": "Employed", "dti": 0.2, "is_homeowner": True, "listing_category": 1, "credit_score": 750}
    
    print("\n--- Testing Good Credit Profile ---")
    resp_good = client.post("/applications/submit", json=payload_good, headers=h_good)
    print("Status Code:", resp_good.status_code)
    print("Response Body:", resp_good.text)
    
    # Test Bad Credit (Score 500) -> High Risk -> AUTO_REJECTED
    payload_bad = {"monthly_income": 3000, "loan_amount": 10000, "term": 24, "employment_status": "Unemployed", "dti": 0.5, "is_homeowner": False, "listing_category": 1, "credit_score": 500}
    
    print("\n--- Testing Bad Credit Profile ---")
    resp_bad = client.post("/applications/submit", json=payload_bad, headers=h_bad)
    print("Status Code:", resp_bad.status_code)
    print("Response Body:", resp_bad.text)

except Exception as e:
    traceback.print_exc()

