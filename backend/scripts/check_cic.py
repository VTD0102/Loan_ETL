import sys
import os

# Add backend to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from models.cic import CICRecord

def check():
    db = SessionLocal()
    try:
        records = db.query(CICRecord).order_by(CICRecord.created_at.desc()).limit(5).all()
        for r in records:
            print(f"Name: {r.full_name}, Outstanding: {r.total_outstanding_debt}, Installment: {r.total_monthly_installment}")
    finally:
        db.close()

if __name__ == "__main__":
    check()
