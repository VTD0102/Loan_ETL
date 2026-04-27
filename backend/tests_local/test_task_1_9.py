import traceback
from datetime import date, timedelta
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # 1. Login Admin
    admin_email = "admin1@gmail.com"
    token = client.post("/auth/login", json={"email": admin_email, "password": "123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Test Get All
    print("\n--- Test No Filters ---")
    resp_all = client.get("/admin/applications?limit=2", headers=headers)
    print("Status:", resp_all.status_code, "Count:", len(resp_all.json()))
    
    # 3. Test Filter by Status
    print("\n--- Test Filter Status=PENDING_REVIEW ---")
    resp_status = client.get("/admin/applications?status=PENDING_REVIEW&limit=5", headers=headers)
    print("Status:", resp_status.status_code, "Count:", len(resp_status.json()))
    for j in resp_status.json():
        if j.get("status") != "PENDING_REVIEW":
            print("ERROR: Mismatch Status", j)

    # 4. Test Filter by Date
    today_str = date.today().isoformat()
    print(f"\n--- Test Filter from_date={today_str} ---")
    resp_date = client.get(f"/admin/applications?from_date={today_str}&limit=5", headers=headers)
    print("Status:", resp_date.status_code, "Count:", len(resp_date.json()))
    print("Top item submitted:", resp_date.json()[0].get('submitted_at') if len(resp_date.json()) > 0 else "Empty")

except Exception as e:
    traceback.print_exc()

