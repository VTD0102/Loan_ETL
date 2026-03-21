from sqlalchemy import text

from utils.db_connection import get_engine


def run_silver_pipeline():
    """Transform data from Bronze to Silver layer.

    Vai trò:
    - Làm sạch dữ liệu từ bảng bronze.
    - Bổ sung các cột PK/FK để phục vụ hệ thống Core (MemberKey, LoanKey...).
    - Khử trùng lặp và ép kiểu dữ liệu chuẩn.
    """
    try:
        engine = get_engine()

<<<<<<< HEAD
        etl_query = text(
            """
            WITH normalized_source AS (
                SELECT
                    CASE
                        WHEN lower(btrim(COALESCE("ListingKey", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("ListingKey")
                    END AS listing_key_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("ListingCreationDate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("ListingCreationDate")
                    END AS listing_creation_date_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("LoanStatus", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE initcap(lower(btrim("LoanStatus")))
                    END AS loan_status_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("ClosedDate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("ClosedDate")
                    END AS closed_date_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("BorrowerAPR", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("BorrowerAPR")
                    END AS borrower_apr_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("BorrowerRate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("BorrowerRate")
                    END AS borrower_rate_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("ProsperRating (Alpha)", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE upper(btrim("ProsperRating (Alpha)"))
                    END AS prosper_rating_alpha_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("CreditGrade", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE upper(btrim("CreditGrade"))
                    END AS credit_grade_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("ProsperScore", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("ProsperScore")
                    END AS prosper_score_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("ListingCategory (numeric)", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("ListingCategory (numeric)")
                    END AS listing_category_numeric_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("Occupation", ''))) IN ('', 'null', 'n/a', 'na', 'none', 'other') THEN NULL
                        ELSE initcap(lower(btrim("Occupation")))
                    END AS occupation_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("EmploymentStatus", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE initcap(lower(btrim("EmploymentStatus")))
                    END AS employment_status_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("IsBorrowerHomeowner", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE lower(btrim("IsBorrowerHomeowner"))
                    END AS is_borrower_homeowner_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("CreditScoreRangeLower", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("CreditScoreRangeLower")
                    END AS credit_score_range_lower_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("CreditScoreRangeUpper", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("CreditScoreRangeUpper")
                    END AS credit_score_range_upper_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("DebtToIncomeRatio", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("DebtToIncomeRatio")
                    END AS debt_to_income_ratio_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("IncomeRange", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("IncomeRange")
                    END AS income_range_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("StatedMonthlyIncome", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("StatedMonthlyIncome")
                    END AS stated_monthly_income_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("LoanOriginalAmount", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("LoanOriginalAmount")
                    END AS loan_original_amount_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("LoanOriginationDate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("LoanOriginationDate")
                    END AS loan_origination_date_raw,
                    CASE
                        WHEN lower(btrim(COALESCE("Term", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL
                        ELSE btrim("Term")
                    END AS term_raw
                FROM bronze.prosper_loans_raw
            ),
            typed_source AS (
                SELECT
                    listing_key_raw AS listing_key,
                    listing_creation_date_raw::timestamp AS listing_creation_date,
                    loan_status_raw AS loan_status,
                    closed_date_raw::timestamp AS closed_date,
                    borrower_apr_raw::numeric(10, 5) AS borrower_apr,
                    borrower_rate_raw::numeric(10, 5) AS borrower_rate,
                    COALESCE(prosper_rating_alpha_raw, credit_grade_raw) AS prosper_rating_alpha,
                    prosper_score_raw::numeric::integer AS prosper_score,
                    listing_category_numeric_raw::numeric::integer AS listing_category_numeric,
                    occupation_raw AS occupation,
                    employment_status_raw AS employment_status,
                    CASE
                        WHEN is_borrower_homeowner_raw IN ('true', 't', '1', 'yes', 'y') THEN TRUE
                        WHEN is_borrower_homeowner_raw IN ('false', 'f', '0', 'no', 'n') THEN FALSE
                        ELSE NULL
                    END AS is_borrower_homeowner,
                    credit_score_range_lower_raw::numeric::integer AS credit_score_range_lower,
                    credit_score_range_upper_raw::numeric::integer AS credit_score_range_upper,
                    debt_to_income_ratio_raw::numeric(10, 5) AS debt_to_income_ratio,
                    income_range_raw AS income_range,
                    stated_monthly_income_raw::numeric(15, 2) AS stated_monthly_income,
                    loan_original_amount_raw::numeric(15, 2) AS loan_original_amount,
                    loan_origination_date_raw::timestamp AS loan_origination_date,
                    term_raw::numeric::integer AS term,
                    CASE
                        WHEN loan_status_raw IN ('Chargedoff', 'Defaulted') THEN 1
                        ELSE 0
                    END AS is_default
                FROM normalized_source
                WHERE listing_key_raw IS NOT NULL
            ),
            ranked_source AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY listing_key
                        ORDER BY
                            listing_creation_date DESC NULLS LAST,
                            loan_origination_date DESC NULLS LAST,
                            closed_date DESC NULLS LAST
                    ) AS row_num
                FROM typed_source
            )
            INSERT INTO silver.prosper_loans_cleansed (
                listing_key, listing_creation_date, loan_status, closed_date,
                borrower_apr, borrower_rate, prosper_rating_alpha, prosper_score,
                listing_category_numeric, occupation, employment_status,
                is_borrower_homeowner, credit_score_range_lower, credit_score_range_upper,
                debt_to_income_ratio, income_range, stated_monthly_income,
                loan_original_amount, loan_origination_date, term, is_default
            )
            SELECT
                listing_key, listing_creation_date, loan_status, closed_date,
                borrower_apr, borrower_rate, prosper_rating_alpha, prosper_score,
                listing_category_numeric, occupation, employment_status,
                is_borrower_homeowner, credit_score_range_lower, credit_score_range_upper,
                debt_to_income_ratio, income_range, stated_monthly_income,
                loan_original_amount, loan_origination_date, term, is_default
            FROM ranked_source
            WHERE row_num = 1
            ON CONFLICT (listing_key) DO UPDATE SET
                listing_creation_date = EXCLUDED.listing_creation_date,
                loan_status = EXCLUDED.loan_status,
                closed_date = EXCLUDED.closed_date,
                borrower_apr = EXCLUDED.borrower_apr,
                borrower_rate = EXCLUDED.borrower_rate,
                prosper_rating_alpha = EXCLUDED.prosper_rating_alpha,
                prosper_score = EXCLUDED.prosper_score,
                listing_category_numeric = EXCLUDED.listing_category_numeric,
                occupation = EXCLUDED.occupation,
                employment_status = EXCLUDED.employment_status,
                is_borrower_homeowner = EXCLUDED.is_borrower_homeowner,
                credit_score_range_lower = EXCLUDED.credit_score_range_lower,
                credit_score_range_upper = EXCLUDED.credit_score_range_upper,
                debt_to_income_ratio = EXCLUDED.debt_to_income_ratio,
                income_range = EXCLUDED.income_range,
                stated_monthly_income = EXCLUDED.stated_monthly_income,
                loan_original_amount = EXCLUDED.loan_original_amount,
                loan_origination_date = EXCLUDED.loan_origination_date,
                term = EXCLUDED.term,
                is_default = EXCLUDED.is_default;
            """
        )
=======
        with open("database/transform_silver.sql", "r", encoding="utf-8") as file:
            etl_query = text(file.read())
>>>>>>> origin/phi

        with engine.connect() as conn:
            print("⏳ Đang chạy Silver ETL từ Bronze...")
            conn.execute(etl_query)
            conn.commit()
            print("✅ Silver ETL hoàn tất.")

    except Exception as e:
        print(f"❌ Lỗi Silver ETL: {e}")


if __name__ == "__main__":
    run_silver_pipeline()