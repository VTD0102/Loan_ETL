-- 1. TẠO SCHEMA VÀ BẢNG TRÊN SUPABASE
CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.prosper_loans_cleansed;

CREATE TABLE silver.prosper_loans_cleansed (
    listing_key VARCHAR,
    member_key VARCHAR,         -- Cột bổ sung cho Core
    borrower_state VARCHAR,     -- Cột bổ sung cho Core
    loan_key VARCHAR,           -- Cột bổ sung cho Core
    loan_number VARCHAR,        -- Cột bổ sung cho Core
    listing_creation_date TIMESTAMP,
    loan_status VARCHAR,
    closed_date TIMESTAMP,
    borrower_apr NUMERIC(10, 5),
    borrower_rate NUMERIC(10, 5),
    prosper_rating_alpha VARCHAR,
    prosper_score INTEGER,
    listing_category_numeric INTEGER,
    occupation VARCHAR,
    employment_status VARCHAR,
    is_borrower_homeowner BOOLEAN,
    income_verifiable BOOLEAN,  -- Cột bổ sung cho Core
    date_credit_pulled TIMESTAMP, -- Cột bổ sung cho Core
    credit_score_range_lower INTEGER,
    credit_score_range_upper INTEGER,
    debt_to_income_ratio NUMERIC(10, 5),
    income_range VARCHAR,
    stated_monthly_income NUMERIC(15, 2),
    loan_original_amount NUMERIC(15, 2),
    loan_origination_date TIMESTAMP,
    term INTEGER,
    is_default INTEGER
);

-- 2. LÀM SẠCH BẢNG TRƯỚC KHI NẠP DỮ LIỆU MỚI
TRUNCATE TABLE silver.prosper_loans_cleansed;

-- 3. LOGIC XỬ LÝ DỮ LIỆU
WITH normalized_source AS (
    SELECT
        CASE WHEN lower(btrim(COALESCE("ListingKey", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("ListingKey") END AS listing_key_raw,
        CASE WHEN lower(btrim(COALESCE("MemberKey", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("MemberKey") END AS member_key_raw,
        CASE WHEN lower(btrim(COALESCE("BorrowerState", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE upper(btrim("BorrowerState")) END AS borrower_state_raw,
        CASE WHEN lower(btrim(COALESCE("LoanKey", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("LoanKey") END AS loan_key_raw,
        CASE WHEN lower(btrim(COALESCE("LoanNumber", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("LoanNumber") END AS loan_number_raw,
        CASE WHEN lower(btrim(COALESCE("ListingCreationDate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("ListingCreationDate") END AS listing_creation_date_raw,
        CASE WHEN lower(btrim(COALESCE("LoanStatus", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE initcap(lower(btrim("LoanStatus"))) END AS loan_status_raw,
        CASE WHEN lower(btrim(COALESCE("ClosedDate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("ClosedDate") END AS closed_date_raw,
        CASE WHEN lower(btrim(COALESCE("BorrowerAPR", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("BorrowerAPR") END AS borrower_apr_raw,
        CASE WHEN lower(btrim(COALESCE("BorrowerRate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("BorrowerRate") END AS borrower_rate_raw,
        CASE WHEN lower(btrim(COALESCE("ProsperRating (Alpha)", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE upper(btrim("ProsperRating (Alpha)")) END AS prosper_rating_alpha_raw,
        CASE WHEN lower(btrim(COALESCE("CreditGrade", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE upper(btrim("CreditGrade")) END AS credit_grade_raw,
        CASE WHEN lower(btrim(COALESCE("ProsperScore", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("ProsperScore") END AS prosper_score_raw,
        CASE WHEN lower(btrim(COALESCE("ListingCategory (numeric)", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("ListingCategory (numeric)") END AS listing_category_numeric_raw,
        CASE WHEN lower(btrim(COALESCE("Occupation", ''))) IN ('', 'null', 'n/a', 'na', 'none', 'other') THEN NULL ELSE initcap(lower(btrim("Occupation"))) END AS occupation_raw,
        CASE WHEN lower(btrim(COALESCE("EmploymentStatus", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE initcap(lower(btrim("EmploymentStatus"))) END AS employment_status_raw,
        CASE WHEN lower(btrim(COALESCE("IsBorrowerHomeowner", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE lower(btrim("IsBorrowerHomeowner")) END AS is_borrower_homeowner_raw,
        CASE WHEN lower(btrim(COALESCE("IncomeVerifiable", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE lower(btrim("IncomeVerifiable")) END AS income_verifiable_raw,
        CASE WHEN lower(btrim(COALESCE("DateCreditPulled", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("DateCreditPulled") END AS date_credit_pulled_raw,
        CASE WHEN lower(btrim(COALESCE("CreditScoreRangeLower", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("CreditScoreRangeLower") END AS credit_score_range_lower_raw,
        CASE WHEN lower(btrim(COALESCE("CreditScoreRangeUpper", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("CreditScoreRangeUpper") END AS credit_score_range_upper_raw,
        CASE WHEN lower(btrim(COALESCE("DebtToIncomeRatio", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("DebtToIncomeRatio") END AS debt_to_income_ratio_raw,
        CASE WHEN lower(btrim(COALESCE("IncomeRange", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("IncomeRange") END AS income_range_raw,
        CASE WHEN lower(btrim(COALESCE("StatedMonthlyIncome", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("StatedMonthlyIncome") END AS stated_monthly_income_raw,
        CASE WHEN lower(btrim(COALESCE("LoanOriginalAmount", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("LoanOriginalAmount") END AS loan_original_amount_raw,
        CASE WHEN lower(btrim(COALESCE("LoanOriginationDate", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("LoanOriginationDate") END AS loan_origination_date_raw,
        CASE WHEN lower(btrim(COALESCE("Term", ''))) IN ('', 'null', 'n/a', 'na', 'none') THEN NULL ELSE btrim("Term") END AS term_raw
    FROM bronze.prosper_loans_raw
),
typed_source AS (
    SELECT
        listing_key_raw AS listing_key,
        member_key_raw AS member_key,
        borrower_state_raw AS borrower_state,
        loan_key_raw AS loan_key,
        loan_number_raw AS loan_number,
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
        CASE WHEN is_borrower_homeowner_raw IN ('true', 't', '1', 'yes', 'y') THEN TRUE WHEN is_borrower_homeowner_raw IN ('false', 'f', '0', 'no', 'n') THEN FALSE ELSE NULL END AS is_borrower_homeowner,
        CASE WHEN income_verifiable_raw IN ('true', 't', '1', 'yes', 'y') THEN TRUE WHEN income_verifiable_raw IN ('false', 'f', '0', 'no', 'n') THEN FALSE ELSE NULL END AS income_verifiable,
        date_credit_pulled_raw::timestamp AS date_credit_pulled,
        credit_score_range_lower_raw::numeric::integer AS credit_score_range_lower,
        credit_score_range_upper_raw::numeric::integer AS credit_score_range_upper,
        debt_to_income_ratio_raw::numeric(10, 5) AS debt_to_income_ratio,
        income_range_raw AS income_range,
        stated_monthly_income_raw::numeric(15, 2) AS stated_monthly_income,
        loan_original_amount_raw::numeric(15, 2) AS loan_original_amount,
        loan_origination_date_raw::timestamp AS loan_origination_date,
        term_raw::numeric::integer AS term,
        CASE WHEN loan_status_raw IN ('Chargedoff', 'Defaulted') THEN 1 ELSE 0 END AS is_default
    FROM normalized_source
    WHERE listing_key_raw IS NOT NULL
),
ranked_source AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY listing_key
            ORDER BY listing_creation_date DESC NULLS LAST, loan_origination_date DESC NULLS LAST, closed_date DESC NULLS LAST
        ) AS row_num
    FROM typed_source
)
INSERT INTO silver.prosper_loans_cleansed (
    listing_key, member_key, borrower_state, loan_key, loan_number,
    listing_creation_date, loan_status, closed_date, borrower_apr, borrower_rate, 
    prosper_rating_alpha, prosper_score, listing_category_numeric, occupation, 
    employment_status, is_borrower_homeowner, income_verifiable, date_credit_pulled,
    credit_score_range_lower, credit_score_range_upper, debt_to_income_ratio, 
    income_range, stated_monthly_income, loan_original_amount, loan_origination_date, 
    term, is_default
)
SELECT
    listing_key, member_key, borrower_state, loan_key, loan_number,
    listing_creation_date, loan_status, closed_date, borrower_apr, borrower_rate, 
    prosper_rating_alpha, prosper_score, listing_category_numeric, occupation, 
    employment_status, is_borrower_homeowner, income_verifiable, date_credit_pulled,
    credit_score_range_lower, credit_score_range_upper, debt_to_income_ratio, 
    income_range, stated_monthly_income, loan_original_amount, loan_origination_date, 
    term, is_default
FROM ranked_source
WHERE row_num = 1;