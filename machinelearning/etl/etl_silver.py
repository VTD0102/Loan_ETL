"""
Silver transformer — Home Credit Credit Risk Model Stability (v2).

Source : bronze.train_base + train_static_0 + train_static_cb_0
         + train_person_1 + train_credit_bureau_a_1 + train_applprev_1
Target : silver.hc_v2_cleansed  (DuckDB local)

Run: python -m machinelearning.etl.etl_silver
"""
import sys
from pathlib import Path

from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
SQL_PATH = BASE_DIR / "database" / "transform_silver_hcv2.sql"

sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.utils.db_connection import get_engine


def main():
    print("=" * 60)
    print("  HOME CREDIT v2 — SILVER TRANSFORM")
    print("=" * 60)

    engine = get_engine()

    print(f"\n[1/2] Chạy {SQL_PATH.name}...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

    print("\n[2/2] Xác nhận row count...")
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM silver.hc_v2_cleansed")
        ).scalar()
        default_rate = conn.execute(
            text("SELECT ROUND(AVG(is_default::numeric)::numeric, 4) "
                 "FROM silver.hc_v2_cleansed")
        ).scalar()
        null_income = conn.execute(
            text("SELECT ROUND(100.0 * AVG(CASE WHEN stated_monthly_income "
                 "IS NULL THEN 1 ELSE 0 END)::numeric, 2) "
                 "FROM silver.hc_v2_cleansed")
        ).scalar()
        null_age = conn.execute(
            text("SELECT ROUND(100.0 * AVG(CASE WHEN age_years "
                 "IS NULL THEN 1 ELSE 0 END)::numeric, 2) "
                 "FROM silver.hc_v2_cleansed")
        ).scalar()

    print(f"  ✓ {count:,} rows trong silver.hc_v2_cleansed")
    print(f"  ✓ Default rate       : {float(default_rate):.2%}")
    print(f"  ✓ Income null rate   : {float(null_income):.2f}%")
    print(f"  ✓ Age null rate      : {float(null_age):.2f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
