from sqlalchemy import text

from utils.db_connection import get_engine


def run_silver_pipeline():
    """Transform data from Bronze to Silver layer.

    Vai trò:
    - Làm sạch dữ liệu từ bảng bronze.
    - Ép kiểu dữ liệu cho các cột quan trọng.
    - Khử trùng lặp theo ListingKey.
    - Tạo nhãn is_default cho bài toán ML.
    """
    try:
        engine = get_engine()

        etl_query = text(
            """
            TRUNCATE TABLE silver.prosper_loans_cleansed;

            INSERT INTO silver.prosper_loans_cleansed (
                listing_key, listing_creation_date, loan_status, closed_date,
                borrower_apr, borrower_rate, prosper_rating_alpha, prosper_score,
                listing_category_numeric, occupation, employment_status,
                is_borrower_homeowner, credit_score_range_lower, credit_score_range_upper,
                debt_to_income_ratio, income_range, stated_monthly_income,
                loan_original_amount, loan_origination_date, term, is_default
            )
            SELECT DISTINCT ON ("ListingKey")
                "ListingKey",
                "ListingCreationDate"::TIMESTAMP,
                "LoanStatus",
                NULLIF("ClosedDate", '')::TIMESTAMP,
                NULLIF("BorrowerAPR", '')::DECIMAL,
                NULLIF("BorrowerRate", '')::DECIMAL,
                COALESCE(NULLIF("ProsperRating (Alpha)", ''), NULLIF("CreditGrade", '')),
                NULLIF("ProsperScore", '')::FLOAT::INT,
                NULLIF("ListingCategory (numeric)", '')::FLOAT::INT,
                "Occupation",
                "EmploymentStatus",
                "IsBorrowerHomeowner"::BOOLEAN,
                NULLIF("CreditScoreRangeLower", '')::FLOAT::INT,
                NULLIF("CreditScoreRangeUpper", '')::FLOAT::INT,
                NULLIF("DebtToIncomeRatio", '')::DECIMAL,
                "IncomeRange",
                NULLIF("StatedMonthlyIncome", '')::DECIMAL,
                NULLIF("LoanOriginalAmount", '')::DECIMAL,
                "LoanOriginationDate"::TIMESTAMP,
                NULLIF("Term", '')::FLOAT::INT,
                CASE WHEN "LoanStatus" IN ('Chargedoff', 'Defaulted') THEN 1 ELSE 0 END
            FROM bronze.prosper_loans_raw
            ORDER BY "ListingKey", "ListingCreationDate" DESC;
            """
        )

        with engine.connect() as conn:
            print("⏳ Đang chạy Silver ETL từ Bronze...")
            conn.execute(etl_query)
            conn.commit()
            print("✅ Silver ETL hoàn tất.")

    except Exception as e:
        print(f"❌ Lỗi Silver ETL: {e}")


if __name__ == "__main__":
    run_silver_pipeline()
