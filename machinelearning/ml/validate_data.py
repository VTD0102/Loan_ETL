"""
Data Validation — chạy trước khi train (v2).
Kiểm tra silver.hc_v2_cleansed có đủ chuẩn để train model không.

Run: python -m machinelearning.ml.validate_data
"""
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from machinelearning.utils.db_connection import get_engine

REQUIRED_COLUMNS = {
    "stated_monthly_income", "loan_original_amount", "term", "employment_status",
    "debt_to_income_ratio", "is_homeowner", "is_default",
    "age_years", "num_active_credits",
}

MIN_ROWS              = 100_000
MIN_DEFAULT_RATE      = 0.01
MAX_DEFAULT_RATE      = 0.50
MAX_NULL_RATE_PCT     = 40.0     # v2 income has ~33% nulls
EXPECTED_EMPLOYMENTS  = {"Employed", "Self-employed", "Retired",
                         "Not employed", "Other/Unknown"}


class ValidationError(Exception):
    pass


def _scalar(engine, sql: str):
    return pd.read_sql(sql, engine).iloc[0, 0]


def validate():
    print("=" * 60)
    print("  DATA VALIDATION — silver.hc_v2_cleansed")
    print("=" * 60)

    engine = get_engine()

    # 1. Row count
    print("\n[1/5] Row count...")
    n_rows = int(_scalar(engine, "SELECT COUNT(*) FROM silver.hc_v2_cleansed"))
    print(f"  Rows: {n_rows:,}")
    if n_rows < MIN_ROWS:
        raise ValidationError(f"Quá ít rows: {n_rows:,} < {MIN_ROWS:,}")
    print("  ✓ PASS")

    # 2. Schema — required columns
    print("\n[2/5] Schema (required columns)...")
    cols = set(pd.read_sql("SELECT * FROM silver.hc_v2_cleansed LIMIT 1", engine).columns)
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise ValidationError(f"Thiếu cột: {missing}")
    print(f"  ✓ PASS ({len(REQUIRED_COLUMNS)} cột bắt buộc đều có)")

    # 3. Null rates
    print("\n[3/5] Null rates (critical columns)...")
    null_df = pd.read_sql("""
        SELECT
            ROUND(100.0 * AVG(CASE WHEN stated_monthly_income IS NULL THEN 1 ELSE 0 END), 2) AS income,
            ROUND(100.0 * AVG(CASE WHEN loan_original_amount   IS NULL THEN 1 ELSE 0 END), 2) AS loan,
            ROUND(100.0 * AVG(CASE WHEN debt_to_income_ratio   IS NULL THEN 1 ELSE 0 END), 2) AS dti,
            ROUND(100.0 * AVG(CASE WHEN is_default             IS NULL THEN 1 ELSE 0 END), 2) AS target
        FROM silver.hc_v2_cleansed
    """, engine).iloc[0]
    for col, pct in null_df.items():
        pct = float(pct)
        flag = "✓" if pct <= MAX_NULL_RATE_PCT else "✗"
        print(f"  {flag} {col:<7} null = {pct:.2f}%")
        if col == "target" and pct > 0:
            raise ValidationError(f"target ({col}) có {pct}% null — không được phép")
        if pct > MAX_NULL_RATE_PCT:
            raise ValidationError(f"{col} null rate {pct}% > {MAX_NULL_RATE_PCT}%")
    print("  ✓ PASS")

    # 4. Default rate (class balance)
    print("\n[4/5] Default rate (class balance)...")
    rate = float(_scalar(engine,
        "SELECT AVG(is_default::DOUBLE) FROM silver.hc_v2_cleansed"))
    print(f"  Default rate: {rate:.2%}")
    if not (MIN_DEFAULT_RATE <= rate <= MAX_DEFAULT_RATE):
        raise ValidationError(
            f"Default rate bất thường: {rate:.2%} "
            f"(kỳ vọng {MIN_DEFAULT_RATE:.0%}–{MAX_DEFAULT_RATE:.0%})"
        )
    print("  ✓ PASS")

    # 5. employment_status — chỉ chấp nhận các giá trị đã định nghĩa
    print("\n[5/5] employment_status values...")
    emp = set(
        pd.read_sql(
            "SELECT DISTINCT employment_status FROM silver.hc_v2_cleansed", engine
        )["employment_status"].dropna()
    )
    unexpected = emp - EXPECTED_EMPLOYMENTS
    if unexpected:
        raise ValidationError(f"employment_status lạ: {unexpected}")
    print(f"  Found: {sorted(emp)}")
    print("  ✓ PASS")

    print("\n" + "=" * 60)
    print("  ✅ ALL VALIDATION CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    try:
        validate()
    except ValidationError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(1)
