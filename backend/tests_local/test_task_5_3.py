from main import app
from fastapi.testclient import TestClient

client = TestClient(app)
user_email = "user11_good@gmail.com"
token = client.post("/auth/login", json={"email": user_email, "password": "123"}).json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

for i in range(25):
    resp = client.post("/chat", json={"message": f"Spam {i}"}, headers=headers)
    print(i, resp.status_code)
    if resp.status_code == 429:
        print("Success 429!")
        break
