import sys
import os
from sqlalchemy import text

# Add backend to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal

def upgrade():
    db = SessionLocal()
    try:
        # PostgreSQL syntax to add column if it doesn't exist.
        # We can just try to add it and catch the error if it exists.
        print("Adding total_monthly_installment column...")
        db.execute(text("ALTER TABLE cic_credit_records ADD COLUMN total_monthly_installment NUMERIC(15, 2) DEFAULT 0;"))
        db.commit()
        print("Column added successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error (maybe column already exists): {e}")
    finally:
        db.close()

if __name__ == "__main__":
    upgrade()
