"""
Silver transformer — Home Credit dataset.

Source : bronze.home_credit_raw
Target : silver.home_credit_cleansed  (DuckDB local)

Run: python -m etl.etl_silver
"""
import sys
from pathlib import Path

from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
SQL_PATH = BASE_DIR / "database" / "transform_silver_homecredit.sql"

sys.path.insert(0, str(BASE_DIR))
from utils.db_connection import get_engine


def main():
    print("=" * 55)
    print("  HOME CREDIT — SILVER TRANSFORM")
    print("=" * 55)

    engine = get_engine()

    print(f"\n[1/2] Chạy {SQL_PATH.name}...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

    print("\n[2/2] Xác nhận row count...")
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM silver.home_credit_cleansed")
        ).scalar()
        default_rate = conn.execute(
            text("SELECT ROUND(AVG(is_default::numeric)::numeric, 4) FROM silver.home_credit_cleansed")
        ).scalar()

    print(f"  ✓ {count:,} rows trong silver.home_credit_cleansed")
    print(f"  ✓ Default rate: {float(default_rate):.2%}")
    print("=" * 55)


if __name__ == "__main__":
    main()
