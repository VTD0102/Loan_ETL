import traceback
print("Attempting to load app...")
try:
    from main import app
    from fastapi.testclient import TestClient
    from db.session import SessionLocal
    from models.personal_info import PersonalInfo
    from models.application import LoanApplication
    
    client = TestClient(app)
    
    # Login Admin
    admin_email = "admin1@gmail.com"
    token = client.post("/auth/login", json={"email": admin_email, "password": "123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    db = SessionLocal()
    
    # Find an app WITH personal info
    info = db.query(PersonalInfo).first()
    app_with_info_id = info.application_id if info else None
    
    # Find an app WITHOUT personal info
    app_without = db.query(LoanApplication).filter(LoanApplication.id != app_with_info_id).first()
    app_without_info_id = app_without.id if app_without else None
    
    db.close()
    
    print("\n--- Test App WITH Personal Info ---")
    if app_with_info_id:
        resp_with = client.get(f"/admin/applications/{app_with_info_id}/personal-info", headers=headers)
        print("Status:", resp_with.status_code)
        if resp_with.status_code == 200:
            print("Full Name:", resp_with.json().get("full_name"))
    else:
        print("No DB records to test WITH info.")

    print("\n--- Test App WITHOUT Personal Info ---")
    if app_without_info_id:
        resp_without = client.get(f"/admin/applications/{app_without_info_id}/personal-info", headers=headers)
        print("Status:", resp_without.status_code)
        print("Detail:", resp_without.json().get("detail"))
    else:
        print("No DB records to test WITHOUT info.")

except Exception as e:
    traceback.print_exc()

