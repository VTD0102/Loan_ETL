-- GOLD LAYER — Home Credit v2 Features
-- Source : silver.hc_v2_cleansed
-- Target : gold.hc_features_v2
--
-- Feature engineering for ML models.
-- NO credit_score_midpoint, NO rating_ordinal.
-- All features are verifiable/behavioral — not user self-reported.

CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.hc_features_v2;

CREATE TABLE gold.hc_features_v2 AS
WITH
-- DTI threshold (75th percentile) for high_dti_flag
dti_threshold AS (
    SELECT quantile_cont(debt_to_income_ratio, 0.75) AS p75
    FROM silver.hc_v2_cleansed
    WHERE debt_to_income_ratio IS NOT NULL
)
SELECT
    s.listing_key,
    s.member_key,
    s.is_default,
    s.date_decision,
    s.WEEK_NUM,

    -- ══════════════════════════════════════════════════════════════════════
    -- NUMERIC FEATURES
    -- ══════════════════════════════════════════════════════════════════════

    -- ── Income & Loan ─────────────────────────────────────────────────────
    s.loan_original_amount,
    s.term,
    s.stated_monthly_income,
    s.debt_to_income_ratio,

    -- loan_amount_to_income (annual ratio)
    CASE
        WHEN s.stated_monthly_income > 0
        THEN ROUND(
            (s.loan_original_amount / NULLIF(s.stated_monthly_income * 12, 0))::NUMERIC,
            5
        )
        ELSE NULL
    END                                                         AS loan_amount_to_income,

    -- log_monthly_income
    CASE
        WHEN s.stated_monthly_income IS NOT NULL AND s.stated_monthly_income > 0
        THEN LN(1 + s.stated_monthly_income)
        ELSE NULL
    END                                                         AS log_monthly_income,

    -- payment_to_income (= DTI)
    s.debt_to_income_ratio                                      AS payment_to_income,

    -- high_dti_flag
    CASE
        WHEN s.debt_to_income_ratio > d.p75 THEN 1
        ELSE 0
    END                                                         AS high_dti_flag,

    -- ── Debt burden features ──────────────────────────────────────────────
    -- current_debt_ratio: current_debt / loan_amount
    CASE
        WHEN s.loan_original_amount > 0
        THEN ROUND((COALESCE(s.current_debt, 0) / s.loan_original_amount)::NUMERIC, 5)
        ELSE 0
    END                                                         AS current_debt_ratio,

    -- total_debt_to_income: total_debt / annual_income
    CASE
        WHEN s.stated_monthly_income > 0
        THEN ROUND((COALESCE(s.total_debt, 0) / NULLIF(s.stated_monthly_income * 12, 0))::NUMERIC, 5)
        ELSE NULL
    END                                                         AS total_debt_to_income,

    -- ── DPD features (days past due) ──────────────────────────────────────
    s.max_dpd_24m,
    s.max_dpd_12m,
    s.max_dpd_3m,
    s.avg_dpd_24m,
    s.avg_dpd_3m                                                AS avg_dpd_recent,
    s.num_active_credits                                        AS num_active_credit,
    s.num_installs_dpd10,
    s.num_installs_dpd5,

    -- ── Payment behavior ──────────────────────────────────────────────────
    s.avg_payment_12m,
    s.num_payments_24m,
    s.num_incoming_payments_9m,
    s.num_apps_30d,

    -- ── Bureau aggregates ─────────────────────────────────────────────────
    s.num_bureau_records,
    s.num_active_credit_bureau,
    s.total_outstanding_debt,
    s.total_overdue_amount,
    GREATEST(s.max_dpd_bureau_active, s.max_dpd_bureau_closed)  AS max_credit_overdue_days,
    s.max_overdue_amount,
    s.max_overdue_instls,
    s.total_prolongations,
    CASE WHEN s.total_overdue_amount > 0 THEN 1 ELSE 0 END     AS has_bad_debt,

    -- ── Previous application features ─────────────────────────────────────
    s.num_previous_loans,
    s.previous_default_rate,
    s.max_prev_app_dpd,
    s.avg_prev_app_dpd,

    -- ── CB query features (credit hunger signal) ──────────────────────────
    s.cb_queries_30d,
    s.cb_queries_90d,
    s.num_cb_queries,

    -- ══════════════════════════════════════════════════════════════════════
    -- DEMOGRAPHIC FEATURES
    -- ══════════════════════════════════════════════════════════════════════

    s.age_years,
    COALESCE(s.employment_length, 0)::NUMERIC                   AS years_employed,

    -- Education ordinal (masked values → ordinal mapping)
    -- Based on education_927M masked values from profiling:
    --   a55475b1 (798K), P97_36_170 (409K), P33_146_175 (259K),
    --   P106_81_188 (55K), P17_36_170 (5K), P157_18_172 (631)
    -- Map by frequency → assumed lower education = more frequent
    CASE s.education_level
        WHEN 'a55475b1'     THEN 2   -- most common, likely secondary
        WHEN 'P97_36_170'   THEN 3   -- second common
        WHEN 'P33_146_175'  THEN 4   -- higher education
        WHEN 'P106_81_188'  THEN 5   -- academic
        WHEN 'P17_36_170'   THEN 1   -- lower
        WHEN 'P157_18_172'  THEN 1   -- lowest frequency
        ELSE 2
    END                                                         AS education_ordinal,

    -- is_homeowner_flag
    CASE WHEN s.is_homeowner THEN 1 ELSE 0 END                 AS is_homeowner_flag,

    -- income_verifiable_flag
    CASE WHEN s.income_verifiable THEN 1 ELSE 0 END            AS income_verifiable_flag,

    -- is_married_flag
    CASE WHEN s.is_married THEN 1 ELSE 0 END                   AS is_married_flag,

    -- ══════════════════════════════════════════════════════════════════════
    -- CATEGORICAL FEATURES
    -- ══════════════════════════════════════════════════════════════════════

    COALESCE(s.employment_status, 'Other/Unknown')              AS employment_status_grouped,
    COALESCE(s.income_type, 'OTHER')                            AS occupation_type,

    -- ══════════════════════════════════════════════════════════════════════
    -- MISSING FLAGS (for features with significant null rates)
    -- ══════════════════════════════════════════════════════════════════════
    CASE WHEN s.stated_monthly_income IS NULL THEN 1 ELSE 0 END AS income_missing_flag,
    CASE WHEN s.debt_to_income_ratio  IS NULL THEN 1 ELSE 0 END AS dti_missing_flag

FROM silver.hc_v2_cleansed s
CROSS JOIN dti_threshold d
WHERE s.loan_original_amount > 0;

-- ── Primary key & indexes ─────────────────────────────────────────────────
ALTER TABLE gold.hc_features_v2
ADD PRIMARY KEY (listing_key);

CREATE INDEX IF NOT EXISTS idx_hcv2_gold_default
    ON gold.hc_features_v2(is_default);

CREATE INDEX IF NOT EXISTS idx_hcv2_gold_week
    ON gold.hc_features_v2(WEEK_NUM);


-- ══════════════════════════════════════════════════════════════════════════
-- ANALYTICAL VIEWS (for admin dashboard)
-- ══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW gold.vw_v2_dti_vs_default AS
SELECT
    CASE
        WHEN payment_to_income < 0.2  THEN 'Low (<0.2)'
        WHEN payment_to_income < 0.5  THEN 'Medium (0.2-0.5)'
        WHEN payment_to_income < 1.0  THEN 'High (0.5-1.0)'
        ELSE 'Very High (1.0+)'
    END                                                          AS dti_band,
    COUNT(*)::INT                                                AS loan_count,
    ROUND(100.0 * SUM(is_default) / NULLIF(COUNT(*), 0), 2)     AS default_rate_pct
FROM gold.hc_features_v2
WHERE payment_to_income IS NOT NULL
GROUP BY dti_band
ORDER BY dti_band;

CREATE OR REPLACE VIEW gold.vw_v2_employment_vs_default AS
SELECT
    employment_status_grouped                                    AS employment,
    COUNT(*)::INT                                                AS loan_count,
    ROUND(100.0 * SUM(is_default) / NULLIF(COUNT(*), 0), 2)     AS default_rate_pct,
    ROUND(AVG(age_years)::NUMERIC, 1)                            AS avg_age
FROM gold.hc_features_v2
GROUP BY employment_status_grouped
ORDER BY employment_status_grouped;

CREATE OR REPLACE VIEW gold.vw_v2_dpd_vs_default AS
SELECT
    CASE
        WHEN max_dpd_24m = 0 THEN 'No DPD'
        WHEN max_dpd_24m <= 30 THEN '1-30 days'
        WHEN max_dpd_24m <= 90 THEN '31-90 days'
        ELSE '90+ days'
    END                                                          AS dpd_band,
    COUNT(*)::INT                                                AS loan_count,
    ROUND(100.0 * SUM(is_default) / NULLIF(COUNT(*), 0), 2)     AS default_rate_pct
FROM gold.hc_features_v2
GROUP BY dpd_band
ORDER BY dpd_band;
