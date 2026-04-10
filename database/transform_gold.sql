-- GOLD LAYER
-- Nguồn:
--   - core.loans
--   - core.borrowers
--   - core.credit_profiles
--   - core.dim_*
--   - silver.prosper_loans_cleansed (để lấy is_default)
--
-- Mục tiêu:
--   1. Tạo bảng feature cho ML: gold.loan_features_v1
--   2. Tạo các analytical views cho dashboard

CREATE SCHEMA IF NOT EXISTS gold;

-- 1. DROP VIEW CŨ TRƯỚC (nếu có)
DROP VIEW IF EXISTS gold.vw_default_rate_by_term;
DROP VIEW IF EXISTS gold.vw_default_rate_by_income;
DROP VIEW IF EXISTS gold.vw_risk_by_employment;
DROP VIEW IF EXISTS gold.vw_category_summary;
DROP VIEW IF EXISTS gold.vw_state_summary;

-- 2. DROP TABLE FEATURE CŨ
DROP TABLE IF EXISTS gold.loan_features_v1;

-- 3. TẠO FEATURE TABLE CHÍNH
-- Grain: 1 row = 1 listing_key = 1 loan
CREATE TABLE gold.loan_features_v1 AS
WITH base AS (
    SELECT
        l.listing_key,
        l.member_key,
        l.loan_number,
        l.loan_original_amount,
        l.term,
        l.borrower_apr,
        l.borrower_rate,
        l.listing_creation_date,
        l.loan_origination_date,

        b.borrower_state,
        b.is_homeowner,
        b.income_verifiable,

        cp.credit_score_range_lower,
        cp.credit_score_range_upper,
        cp.debt_to_income_ratio,
        cp.stated_monthly_income,
        cp.prosper_rating_alpha,
        cp.prosper_score,

        es.employment_status_name,
        occ.occupation_name,
        ir.income_range_label,
        lc.category_name,

        s.is_default
    FROM core.loans l
    LEFT JOIN core.borrowers b
        ON l.member_key = b.member_key
    LEFT JOIN core.credit_profiles cp
        ON l.listing_key = cp.listing_key
    LEFT JOIN core.dim_employment_status es
        ON l.employment_status_id = es.employment_status_id
    LEFT JOIN core.dim_occupation occ
        ON l.occupation_id = occ.occupation_id
    LEFT JOIN core.dim_income_range ir
        ON l.income_range_id = ir.income_range_id
    LEFT JOIN core.dim_listing_category lc
        ON l.category_id = lc.category_id
    LEFT JOIN silver.prosper_loans_cleansed s
        ON l.listing_key = s.listing_key
),
engineered AS (
    SELECT
        listing_key,
        member_key,
        loan_number,

        -- Target
        is_default,

        -- Raw loan features
        loan_original_amount,
        term,
        borrower_apr,
        borrower_rate,
        listing_creation_date,
        loan_origination_date,

        -- Raw borrower features
        borrower_state,
        is_homeowner,
        income_verifiable,

        -- Raw credit features
        credit_score_range_lower,
        credit_score_range_upper,
        debt_to_income_ratio,
        stated_monthly_income,
        prosper_rating_alpha,
        prosper_score,

        -- Raw joined dimensions
        COALESCE(employment_status_name, 'Unknown') AS employment_status_name,
        COALESCE(occupation_name, 'Unknown') AS occupation_name,
        COALESCE(income_range_label, 'Unknown') AS income_range_label,
        COALESCE(category_name, 'Unknown') AS category_name,

        -- Engineered: Credit
        CASE
            WHEN credit_score_range_lower IS NOT NULL
             AND credit_score_range_upper IS NOT NULL
            THEN (credit_score_range_lower + credit_score_range_upper) / 2.0
            ELSE NULL
        END AS credit_score_midpoint,

        CASE
            WHEN credit_score_range_lower IS NULL OR credit_score_range_upper IS NULL THEN 'Unknown'
            WHEN (credit_score_range_lower + credit_score_range_upper) / 2.0 < 600 THEN '<600'
            WHEN (credit_score_range_lower + credit_score_range_upper) / 2.0 < 640 THEN '600-639'
            WHEN (credit_score_range_lower + credit_score_range_upper) / 2.0 < 680 THEN '640-679'
            WHEN (credit_score_range_lower + credit_score_range_upper) / 2.0 < 720 THEN '680-719'
            ELSE '720+'
        END AS credit_score_band,

        CASE
            WHEN prosper_rating_alpha = 'HR' THEN 1
            WHEN prosper_rating_alpha = 'E' THEN 2
            WHEN prosper_rating_alpha = 'D' THEN 3
            WHEN prosper_rating_alpha = 'C' THEN 4
            WHEN prosper_rating_alpha = 'B' THEN 5
            WHEN prosper_rating_alpha = 'A' THEN 6
            WHEN prosper_rating_alpha = 'AA' THEN 7
            ELSE NULL
        END AS rating_ordinal,

        -- Engineered: Income
        CASE
            WHEN stated_monthly_income IS NOT NULL
            THEN stated_monthly_income * 12
            ELSE NULL
        END AS annual_income_est,

        CASE
            WHEN stated_monthly_income IS NOT NULL AND stated_monthly_income >= 0
            THEN LN(1 + stated_monthly_income)
            ELSE NULL
        END AS log_monthly_income,

        CASE
            WHEN income_range_label = '$0' THEN 0
            WHEN income_range_label = '$1-24,999' THEN 1
            WHEN income_range_label = '$25,000-49,999' THEN 2
            WHEN income_range_label = '$50,000-74,999' THEN 3
            WHEN income_range_label = '$75,000-99,999' THEN 4
            WHEN income_range_label = '$100,000+' THEN 5
            WHEN income_range_label = 'Not displayed' THEN NULL
            WHEN income_range_label = 'Not employed' THEN NULL
            ELSE NULL
        END AS income_range_ordinal,

        -- Engineered: Burden / pricing
        CASE
            WHEN loan_original_amount IS NOT NULL
             AND stated_monthly_income IS NOT NULL
             AND stated_monthly_income > 0
            THEN loan_original_amount / (stated_monthly_income * 12)
            ELSE NULL
        END AS loan_amount_to_income,

        CASE
            WHEN borrower_apr IS NOT NULL
             AND borrower_rate IS NOT NULL
            THEN borrower_apr - borrower_rate
            ELSE NULL
        END AS rate_apr_spread,

        CASE
            WHEN debt_to_income_ratio IS NOT NULL AND debt_to_income_ratio > 0.35 THEN 1
            ELSE 0
        END AS high_dti_flag,

        -- Engineered: Time
        EXTRACT(YEAR FROM loan_origination_date)::INT AS origination_year,
        EXTRACT(MONTH FROM loan_origination_date)::INT AS origination_month,
        EXTRACT(QUARTER FROM loan_origination_date)::INT AS origination_quarter,

        EXTRACT(YEAR FROM listing_creation_date)::INT AS listing_year,
        EXTRACT(MONTH FROM listing_creation_date)::INT AS listing_month,
        EXTRACT(QUARTER FROM listing_creation_date)::INT AS listing_quarter,

        CASE
            WHEN loan_origination_date >= TIMESTAMP '2009-01-01' THEN 1
            ELSE 0
        END AS post_2009_flag,

        -- Engineered: Term flags
        CASE WHEN term = 12 THEN 1 ELSE 0 END AS term_12_flag,
        CASE WHEN term = 36 THEN 1 ELSE 0 END AS term_36_flag,
        CASE WHEN term = 60 THEN 1 ELSE 0 END AS term_60_flag,

        -- Engineered: Boolean flags
        CASE WHEN is_homeowner IS TRUE THEN 1 ELSE 0 END AS is_homeowner_flag,
        CASE WHEN income_verifiable IS TRUE THEN 1 ELSE 0 END AS income_verifiable_flag,

        -- Engineered: Grouped categoricals
        CASE
            WHEN employment_status_name IN ('Employed', 'Full-time', 'Part-time') THEN 'Employed'
            WHEN employment_status_name IN ('Self-employed') THEN 'Self-employed'
            WHEN employment_status_name IN ('Retired') THEN 'Retired'
            WHEN employment_status_name IN ('Not employed', 'Unemployed') THEN 'Not employed'
            ELSE 'Other/Unknown'
        END AS employment_status_grouped,

        COALESCE(occupation_name, 'Unknown') AS occupation_cleaned,

        -- Missing flags
        CASE WHEN prosper_score IS NULL THEN 1 ELSE 0 END AS prosper_score_missing_flag,
        CASE WHEN prosper_rating_alpha IS NULL THEN 1 ELSE 0 END AS rating_missing_flag,
        CASE WHEN stated_monthly_income IS NULL THEN 1 ELSE 0 END AS income_missing_flag,
        CASE WHEN debt_to_income_ratio IS NULL THEN 1 ELSE 0 END AS dti_missing_flag,
        CASE
            WHEN credit_score_range_lower IS NULL OR credit_score_range_upper IS NULL THEN 1
            ELSE 0
        END AS credit_score_missing_flag

    FROM base
)
SELECT *
FROM engineered;

ALTER TABLE gold.loan_features_v1
ADD PRIMARY KEY (listing_key);

COMMENT ON TABLE gold.loan_features_v1 IS
'Gold feature table for ML and risk analytics. Grain = 1 row per loan/listing_key.';


-- 4. INDEX PHỤC VỤ QUERY / DASHBOARD / ML
CREATE INDEX IF NOT EXISTS idx_gold_features_is_default
    ON gold.loan_features_v1(is_default);

CREATE INDEX IF NOT EXISTS idx_gold_features_origination_year
    ON gold.loan_features_v1(origination_year);

CREATE INDEX IF NOT EXISTS idx_gold_features_term
    ON gold.loan_features_v1(term);

CREATE INDEX IF NOT EXISTS idx_gold_features_category_name
    ON gold.loan_features_v1(category_name);

CREATE INDEX IF NOT EXISTS idx_gold_features_employment_group
    ON gold.loan_features_v1(employment_status_grouped);


-- 5. ANALYTICAL VIEWS CHO DASHBOARD

-- 5.1. Default rate theo term
CREATE VIEW gold.vw_default_rate_by_term AS
SELECT
    term,
    COUNT(*) AS total_loans,
    SUM(is_default) AS default_loans,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct
FROM gold.loan_features_v1
GROUP BY term
ORDER BY term;

-- 5.2. Default rate theo income range
CREATE VIEW gold.vw_default_rate_by_income AS
SELECT
    income_range_label,
    COUNT(*) AS total_loans,
    SUM(is_default) AS default_loans,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct
FROM gold.loan_features_v1
GROUP BY income_range_label
ORDER BY default_rate_pct DESC, total_loans DESC;

-- 5.3. Rủi ro theo nhóm việc làm
CREATE VIEW gold.vw_risk_by_employment AS
SELECT
    employment_status_grouped,
    COUNT(*) AS total_loans,
    SUM(is_default) AS default_loans,
    ROUND(AVG(COALESCE(loan_amount_to_income, 0))::numeric, 4) AS avg_loan_amount_to_income,
    ROUND(AVG(COALESCE(debt_to_income_ratio, 0))::numeric, 4) AS avg_dti,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct
FROM gold.loan_features_v1
GROUP BY employment_status_grouped
ORDER BY default_rate_pct DESC, total_loans DESC;

-- 5.4. Tóm tắt theo mục đích vay
CREATE VIEW gold.vw_category_summary AS
SELECT
    category_name,
    COUNT(*) AS total_loans,
    ROUND(AVG(loan_original_amount)::numeric, 2) AS avg_loan_amount,
    ROUND(AVG(borrower_rate)::numeric, 4) AS avg_borrower_rate,
    SUM(is_default) AS default_loans,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct
FROM gold.loan_features_v1
GROUP BY category_name
ORDER BY total_loans DESC;

-- 5.5. Tóm tắt theo bang / khu vực
CREATE VIEW gold.vw_state_summary AS
SELECT
    borrower_state,
    COUNT(*) AS total_loans,
    SUM(is_default) AS default_loans,
    ROUND(100.0 * SUM(is_default)::numeric / NULLIF(COUNT(*), 0), 2) AS default_rate_pct,
    ROUND(AVG(loan_original_amount)::numeric, 2) AS avg_loan_amount
FROM gold.loan_features_v1
WHERE borrower_state IS NOT NULL
GROUP BY borrower_state
ORDER BY total_loans DESC, default_rate_pct DESC;