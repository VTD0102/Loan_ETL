"""
Gold transformer — Home Credit dataset.

Source : silver.home_credit_cleansed
Target : gold.hc_features_v1  (DuckDB local)

Run: python -m machinelearning.etl.etl_gold
"""
import sys
from pathlib import Path

from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
SQL_PATH = BASE_DIR / "database" / "transform_gold_homecredit.sql"

sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.utils.db_connection import get_engine


def main():
    print("=" * 55)
    print("  HOME CREDIT — GOLD TRANSFORM")
    print("=" * 55)

    engine = get_engine()

    print(f"\n[1/2] Chạy {SQL_PATH.name}...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

    print("\n[2/2] Xác nhận...")
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM gold.hc_features_v1")
        ).scalar()
        default_rate = conn.execute(
            text("SELECT ROUND(AVG(is_default::numeric)::numeric, 4) FROM gold.hc_features_v1")
        ).scalar()
        avg_score = conn.execute(
            text("SELECT ROUND(AVG(credit_score_midpoint)::numeric, 1) FROM gold.hc_features_v1")
        ).scalar()

    print(f"  ✓ {count:,} rows trong gold.hc_features_v1")
    print(f"  ✓ Default rate     : {float(default_rate):.2%}")
    print(f"  ✓ Avg credit score : {avg_score}")
    print("=" * 55)


if __name__ == "__main__":
    main()
