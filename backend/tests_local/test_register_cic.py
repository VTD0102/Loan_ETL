from db.session import SessionLocal
from schemas.user import UserCreate
from services.auth_service import register
from services.cic_service import lookup_by_cccd
import random

db = SessionLocal()
try:
    for i in range(10):
        cccd = f"079099{random.randint(100000, 999999)}"
        payload = UserCreate(
            email=f"test{cccd}@example.com",
            username=f"test{cccd}",
            password="Password123!",
            cccd=cccd,
            full_name="Test User",
            phone="0901234567",
            address="123 Test St"
        )
        res = register(db, payload)
        
        cic = lookup_by_cccd(db, cccd)
        if cic:
            print(f"[{i}] CIC Profile found: Active: {cic.total_active_loans}, Score: {cic.cic_score}, Debt: {cic.total_outstanding_debt}, Installment: {cic.total_monthly_installment}")
        else:
            print(f"[{i}] ERROR: No CIC profile found for new user!")
finally:
    db.close()
