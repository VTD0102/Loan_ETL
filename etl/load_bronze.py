"""
Bronze loader — Home Credit Default Risk dataset.

Source : data/home_credit/application_train.csv  (download từ Kaggle)
Target : bronze.home_credit_raw  (DuckDB local)

Run: python -m etl.load_bronze
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR        = Path(__file__).resolve().parents[1]
CSV_PATH        = BASE_DIR / "data" / "home_credit" / "application_train.csv"
PREV_CSV_PATH   = BASE_DIR / "data" / "home_credit" / "previous_application.csv"
BUREAU_CSV_PATH = BASE_DIR / "data" / "home_credit" / "bureau.csv"

sys.path.insert(0, str(BASE_DIR))
from utils.db_connection import _ETL_ENV_FILE, _read_file

COLS = [
    "SK_ID_CURR", "TARGET",
    "AMT_CREDIT", "AMT_ANNUITY", "AMT_INCOME_TOTAL",
    "NAME_CONTRACT_TYPE", "NAME_INCOME_TYPE",
    "FLAG_OWN_REALTY",
    "DAYS_EMPLOYED",
    "EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3",
    "FLAG_EMP_PHONE",
    # ── Demographic features (Phase: thêm để boost AUC) ────────────────────
    "DAYS_BIRTH",            # tuổi (đếm ngày ngược, âm)
    "CODE_GENDER",           # M / F / XNA
    "NAME_EDUCATION_TYPE",   # Higher / Secondary / Lower secondary / ...
    "NAME_FAMILY_STATUS",    # Married / Single / Widow / Separated / ...
    "CNT_CHILDREN",          # số con
    "CNT_FAM_MEMBERS",       # tổng người trong gia đình
]

# Subset cần cho aggregate num_previous_loans + previous_default_rate trong Gold
PREV_COLS = ["SK_ID_CURR", "SK_ID_PREV", "NAME_CONTRACT_STATUS"]

# Subset cho bureau aggregates (credit bureau history) trong Gold
BUREAU_COLS = ["SK_ID_CURR", "CREDIT_ACTIVE", "AMT_CREDIT_SUM_OVERDUE", "CREDIT_DAY_OVERDUE"]


def _get_duckdb_path() -> Path:
    etl = _read_file(_ETL_ENV_FILE)
    db_path = BASE_DIR / etl.get("etl_db_path", "data/etl.duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def main():
    if not CSV_PATH.exists():
        print(f"[ERROR] File không tìm thấy: {CSV_PATH}")
        print("  → Download từ Kaggle: kaggle competitions download -c home-credit-default-risk")
        print("  → Giải nén application_train.csv vào data/home_credit/")
        sys.exit(1)

    db_path = _get_duckdb_path()
    print("=" * 55)
    print("  HOME CREDIT — BRONZE LOAD")
    print("=" * 55)
    print(f"  [db] DuckDB → {db_path}")

    print(f"\n[1/5] Đọc {CSV_PATH.name} (có thể mất vài giây)...")
    df = pd.read_csv(CSV_PATH, usecols=COLS, low_memory=False)
    print(f"  Rows: {len(df):,}  |  Columns: {len(df.columns)}")

    print("\n[2/5] Load vào bronze.home_credit_raw...")
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("CREATE OR REPLACE TABLE bronze.home_credit_raw AS SELECT * FROM df")

    if PREV_CSV_PATH.exists():
        print(f"\n[3/5] Đọc {PREV_CSV_PATH.name} (1.67M rows, vài giây)...")
        df_prev = pd.read_csv(PREV_CSV_PATH, usecols=PREV_COLS, low_memory=False)
        print(f"  Rows: {len(df_prev):,}  |  Unique customers: {df_prev['SK_ID_CURR'].nunique():,}")
        con.execute("CREATE OR REPLACE TABLE bronze.previous_application_raw AS SELECT * FROM df_prev")
    else:
        print(f"\n[3/5] BỎ QUA: {PREV_CSV_PATH.name} không tồn tại")

    if BUREAU_CSV_PATH.exists():
        print(f"\n[4/5] Đọc {BUREAU_CSV_PATH.name} (1.72M rows, vài giây)...")
        df_bureau = pd.read_csv(BUREAU_CSV_PATH, usecols=BUREAU_COLS, low_memory=False)
        print(f"  Rows: {len(df_bureau):,}  |  Unique customers: {df_bureau['SK_ID_CURR'].nunique():,}")
        con.execute("CREATE OR REPLACE TABLE bronze.bureau_raw AS SELECT * FROM df_bureau")
    else:
        print(f"\n[4/5] BỎ QUA: {BUREAU_CSV_PATH.name} không tồn tại")

    con.close()

    print("\n[5/5] Xác nhận row count...")
    con = duckdb.connect(str(db_path), read_only=True)
    count = con.execute("SELECT COUNT(*) FROM bronze.home_credit_raw").fetchone()[0]

    def _has_table(name: str) -> bool:
        return con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema='bronze' AND table_name='{name}'"
        ).fetchone()[0] == 1

    print(f"  ✓ {count:,} rows trong bronze.home_credit_raw")
    if _has_table("previous_application_raw"):
        n = con.execute("SELECT COUNT(*) FROM bronze.previous_application_raw").fetchone()[0]
        print(f"  ✓ {n:,} rows trong bronze.previous_application_raw")
    if _has_table("bureau_raw"):
        n = con.execute("SELECT COUNT(*) FROM bronze.bureau_raw").fetchone()[0]
        print(f"  ✓ {n:,} rows trong bronze.bureau_raw")
    con.close()
    print("=" * 55)


if __name__ == "__main__":
    main()
