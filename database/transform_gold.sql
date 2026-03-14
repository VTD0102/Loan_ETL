CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.loan_features_v1;

CREATE TABLE gold.loan_features_v1 AS
WITH base AS (
    SELECT
        listing_key,
        listing_creation_date,
        borrower_apr,
        borrower_rate,
        prosper_rating_alpha,
        prosper_score,
        listing_category_numeric,
        occupation,
        employment_status,
        is_borrower_homeowner,
        credit_score_range_lower,
        credit_score_range_upper,
        debt_to_income_ratio,
        income_range,
        stated_monthly_income,
        loan_original_amount,
        loan_origination_date,
        term,
        is_default
    FROM silver.prosper_loans_cleansed
),
engineered AS (
    SELECT
        listing_key,
        listing_creation_date,
        borrower_apr,
        borrower_rate,
        prosper_rating_alpha,
        prosper_score,
        listing_category_numeric,

        COALESCE(occupation, 'Unknown') AS occupation,
        COALESCE(
            CASE
                WHEN lower(occupation) IN ('student', 'retired') THEN initcap(lower(occupation))
                ELSE occupation
            END,
            'Unknown'
        ) AS occupation_cleaned,

        COALESCE(employment_status, 'Unknown') AS employment_status,
        CASE
            WHEN employment_status IN ('Employed', 'Full-time', 'Part-time') THEN 'Employed'
            WHEN employment_status IN ('Self-employed') THEN 'Self-employed'
            WHEN employment_status IN ('Retired') THEN 'Retired'
            WHEN employment_status IN ('Not employed', 'Unemployed') THEN 'Not employed'
            ELSE 'Other/Unknown'
        END AS employment_status_grouped,

        is_borrower_homeowner,
        CASE WHEN is_borrower_homeowner IS TRUE THEN 1 ELSE 0 END AS is_homeowner_flag,

        credit_score_range_lower,
        credit_score_range_upper,
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

        debt_to_income_ratio,
        income_range,
        CASE
            WHEN income_range ILIKE '$0' THEN 0
            WHEN income_range ILIKE '$1-24,999' THEN 1
            WHEN income_range ILIKE '$25,000-49,999' THEN 2
            WHEN income_range ILIKE '$50,000-74,999' THEN 3
            WHEN income_range ILIKE '$75,000-99,999' THEN 4
            WHEN income_range ILIKE '$100,000+' THEN 5
            WHEN income_range ILIKE 'Not displayed' THEN NULL
            WHEN income_range ILIKE 'Not employed' THEN NULL
            ELSE NULL
        END AS income_range_ordinal,

        stated_monthly_income,
        CASE
            WHEN stated_monthly_income IS NOT NULL AND stated_monthly_income >= 0
            THEN LN(1 + stated_monthly_income)
            ELSE NULL
        END AS log_monthly_income,
        CASE
            WHEN stated_monthly_income IS NOT NULL
            THEN stated_monthly_income * 12
            ELSE NULL
        END AS annual_income_est,

        loan_original_amount,
        CASE
            WHEN loan_original_amount IS NOT NULL
             AND stated_monthly_income IS NOT NULL
             AND stated_monthly_income > 0
            THEN loan_original_amount / (stated_monthly_income * 12)
            ELSE NULL
        END AS loan_amount_to_income,

        loan_origination_date,

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

        term,
        CASE WHEN term = 12 THEN 1 ELSE 0 END AS term_12_flag,
        CASE WHEN term = 36 THEN 1 ELSE 0 END AS term_36_flag,
        CASE WHEN term = 60 THEN 1 ELSE 0 END AS term_60_flag,

        CASE
            WHEN borrower_apr IS NOT NULL AND borrower_rate IS NOT NULL
            THEN borrower_apr - borrower_rate
            ELSE NULL
        END AS rate_apr_spread,

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

        CASE WHEN prosper_score IS NULL THEN 1 ELSE 0 END AS prosper_score_missing_flag,
        CASE WHEN prosper_rating_alpha IS NULL THEN 1 ELSE 0 END AS rating_missing_flag,
        CASE WHEN debt_to_income_ratio IS NULL THEN 1 ELSE 0 END AS dti_missing_flag,
        CASE WHEN stated_monthly_income IS NULL THEN 1 ELSE 0 END AS income_missing_flag,
        CASE
            WHEN credit_score_range_lower IS NULL OR credit_score_range_upper IS NULL THEN 1
            ELSE 0
        END AS credit_score_missing_flag,

        is_default
    FROM base
)
SELECT *
FROM engineered;

ALTER TABLE gold.loan_features_v1
ADD PRIMARY KEY (listing_key);

COMMENT ON TABLE gold.loan_features_v1 IS 'Gold feature table for baseline default prediction using origination-safe features only';