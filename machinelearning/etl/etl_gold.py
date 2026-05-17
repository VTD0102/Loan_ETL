"""
Gold transformer — Home Credit Credit Risk Model Stability (v2).

Source : silver.hc_v2_cleansed
Target : gold.hc_features_v2  (DuckDB local)

Run: python -m machinelearning.etl.etl_gold
"""
import sys
from pathlib import Path

from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
SQL_PATH = BASE_DIR / "database" / "transform_gold_hcv2.sql"

sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.utils.db_connection import get_engine


def main():
    print("=" * 60)
    print("  HOME CREDIT v2 — GOLD TRANSFORM")
    print("=" * 60)

    engine = get_engine()

    print(f"\n[1/2] Chạy {SQL_PATH.name}...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

    print("\n[2/2] Xác nhận...")
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM gold.hc_features_v2")
        ).scalar()
        default_rate = conn.execute(
            text("SELECT ROUND(AVG(is_default::numeric)::numeric, 4) "
                 "FROM gold.hc_features_v2")
        ).scalar()
        num_features = conn.execute(
            text("SELECT COUNT(*) FROM information_schema.columns "
                 "WHERE table_schema='gold' AND table_name='hc_features_v2'")
        ).scalar()

    print(f"  ✓ {count:,} rows trong gold.hc_features_v2")
    print(f"  ✓ Default rate  : {float(default_rate):.2%}")
    print(f"  ✓ Num features  : {num_features}")
    print("=" * 60)


if __name__ == "__main__":
    main()
