"""
Bronze loader — Home Credit Credit Risk Model Stability dataset (v2).

Loads Parquet files from the new Kaggle competition dataset into DuckDB
bronze tables.  DuckDB reads Parquet natively via `read_parquet()` glob
patterns — no pandas intermediate needed.

Tables loaded (priority order):
  1. bronze.train_base          ← train_base.parquet         (1.53M rows)
  2. bronze.train_static_0      ← train_static_0_*.parquet   (1.53M, depth=0)
  3. bronze.train_static_cb_0   ← train_static_cb_0.parquet  (1.50M, depth=0, CB)
  4. bronze.train_person_1      ← train_person_1.parquet     (2.97M, depth=1)
  5. bronze.train_credit_bureau_a_1 ← train_credit_bureau_a_1_*.parquet (15.9M, depth=1)
  6. bronze.train_applprev_1    ← train_applprev_1_*.parquet  (6.5M, depth=1)

Run: python -m machinelearning.etl.load_bronze
"""
import sys
import time
from pathlib import Path

import duckdb

BASE_DIR     = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
PARQUET_DIR  = BASE_DIR / "data" / "home-credit-credit-risk-model-stability" / "parquet_files" / "train"

sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.utils.db_connection import _ETL_ENV_FILE, _read_file

# ── Table definitions: (bronze_table_name, parquet_glob_pattern) ──────────────
TABLES = [
    ("train_base",              "train_base.parquet"),
    ("train_static_0",          "train_static_0_*.parquet"),
    ("train_static_cb_0",       "train_static_cb_0.parquet"),
    ("train_person_1",          "train_person_1.parquet"),
    ("train_credit_bureau_a_1", "train_credit_bureau_a_1_*.parquet"),
    ("train_applprev_1",        "train_applprev_1_*.parquet"),
]


def _get_duckdb_path() -> Path:
    etl = _read_file(_ETL_ENV_FILE)
    db_path = BASE_DIR / etl.get("etl_db_path", "data/etl.duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def main():
    if not PARQUET_DIR.exists():
        print(f"[ERROR] Parquet directory không tìm thấy: {PARQUET_DIR}")
        print("  → Download từ Kaggle: kaggle competitions download "
              "-c home-credit-credit-risk-model-stability")
        print("  → Giải nén vào data/home-credit-credit-risk-model-stability/")
        sys.exit(1)

    db_path = _get_duckdb_path()
    print("=" * 60)
    print("  HOME CREDIT v2 — BRONZE LOAD (Parquet → DuckDB)")
    print("=" * 60)
    print(f"  [db]      DuckDB → {db_path}")
    print(f"  [source]  {PARQUET_DIR}")

    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    total_tables = len(TABLES)
    for idx, (table_name, glob_pattern) in enumerate(TABLES, 1):
        parquet_path = str(PARQUET_DIR / glob_pattern)

        # Verify at least one file matches
        matched = list(PARQUET_DIR.glob(glob_pattern))
        if not matched:
            print(f"\n[{idx}/{total_tables}] ⚠ SKIP: {glob_pattern} — "
                  f"no matching files")
            continue

        print(f"\n[{idx}/{total_tables}] Loading {glob_pattern} "
              f"→ bronze.{table_name}...")
        print(f"  Files matched: {len(matched)}")

        t0 = time.time()
        con.execute(f"""
            CREATE OR REPLACE TABLE bronze.{table_name} AS
            SELECT * FROM read_parquet('{parquet_path}')
        """)
        elapsed = time.time() - t0

        row_count = con.execute(
            f"SELECT COUNT(*) FROM bronze.{table_name}"
        ).fetchone()[0]
        col_count = con.execute(
            f"SELECT COUNT(*) FROM information_schema.columns "
            f"WHERE table_schema='bronze' AND table_name='{table_name}'"
        ).fetchone()[0]

        print(f"  ✓ {row_count:,} rows × {col_count} cols  ({elapsed:.1f}s)")

    con.close()

    # ── Verification ──────────────────────────────────────────────────────────
    print("\n" + "-" * 60)
    print("  VERIFICATION")
    print("-" * 60)

    con = duckdb.connect(str(db_path), read_only=True)
    for table_name, _ in TABLES:
        try:
            n = con.execute(
                f"SELECT COUNT(*) FROM bronze.{table_name}"
            ).fetchone()[0]
            print(f"  ✓ bronze.{table_name:<30s}  {n:>12,} rows")
        except Exception:
            print(f"  ✗ bronze.{table_name:<30s}  NOT LOADED")

    # Quick sanity: base table target distribution
    try:
        stats = con.execute("""
            SELECT COUNT(*) AS n,
                   SUM(target) AS defaults,
                   ROUND(AVG(target) * 100, 2) AS default_pct
            FROM bronze.train_base
        """).fetchone()
        print(f"\n  Base stats: {stats[0]:,} total, {int(stats[1]):,} defaults "
              f"({stats[2]}%)")
    except Exception:
        pass

    con.close()
    print("=" * 60)


if __name__ == "__main__":
    main()
