-- GOLD LAYER — Home Credit Features
-- Source : silver.home_credit_cleansed
-- Target : gold.hc_features_v1
--
-- Tính toán cùng 12 features mà train_scorecard.py sử dụng
-- (tương thích với gold.loan_features_v1 từ Prosper).

CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.hc_features_v1;

CREATE TABLE gold.hc_features_v1 AS
WITH
-- FIX #2: Threshold high_dti_flag tính từ 75th percentile của DTI thực tế
-- trong HC (thay vì 0.35 của Prosper — sẽ làm 99.7% rows = 1)
dti_threshold AS (
    SELECT quantile_cont(debt_to_income_ratio, 0.75) AS p75
    FROM silver.home_credit_cleansed
    WHERE debt_to_income_ratio IS NOT NULL
),
-- FIX #4: Aggregate previous applications per customer
-- num_previous_loans   = số lần đã được duyệt vay trước đó
-- previous_default_rate = tỉ lệ application bị Refused/Canceled (proxy cho
--                         credit history negativity — không phải default thực)
prev_stats AS (
    SELECT
        "SK_ID_CURR"::TEXT                              AS member_key,
        COUNT(*) FILTER (WHERE "NAME_CONTRACT_STATUS" = 'Approved')::INT
                                                        AS num_previous_loans,
        ROUND(
            (COUNT(*) FILTER (WHERE "NAME_CONTRACT_STATUS" IN ('Refused','Canceled'))::NUMERIC
             / NULLIF(COUNT(*), 0)),
            4
        )                                               AS previous_default_rate
    FROM bronze.previous_application_raw
    GROUP BY "SK_ID_CURR"
),
-- FIX #10: Bureau aggregates (credit history từ các ngân hàng khác).
-- Đây là signal credit history quan trọng nhất — 1.72M rows từ bureau.csv.
bureau_stats AS (
    SELECT
        "SK_ID_CURR"::TEXT                              AS member_key,
        COUNT(*)::INT                                   AS num_bureau_records,
        COUNT(*) FILTER (WHERE "CREDIT_ACTIVE" = 'Active')::INT
                                                        AS num_active_credit,
        COALESCE(SUM("AMT_CREDIT_SUM_OVERDUE"), 0)::NUMERIC
                                                        AS total_overdue_amount,
        COALESCE(MAX("CREDIT_DAY_OVERDUE"), 0)::INT
                                                        AS max_credit_overdue_days,
        MAX(CASE WHEN "CREDIT_ACTIVE" = 'Bad debt' THEN 1 ELSE 0 END)
                                                        AS has_bad_debt
    FROM bronze.bureau_raw
    GROUP BY "SK_ID_CURR"
)
SELECT
    s.listing_key,
    s.member_key,
    s.is_default,

    -- ── Raw ────────────────────────────────────────────────────────────────
    s.loan_original_amount,
    s.term,
    s.stated_monthly_income,
    s.debt_to_income_ratio,
    s.credit_score_range_lower,
    s.credit_score_range_upper,
    s.income_range,
    s.prosper_rating_alpha,
    s.prosper_score,
    s.borrower_apr,

    -- ── Credit Score ───────────────────────────────────────────────────────
    (s.credit_score_range_lower + s.credit_score_range_upper) / 2.0
        AS credit_score_midpoint,

    CASE
        WHEN (s.credit_score_range_lower + s.credit_score_range_upper) / 2.0 < 580  THEN 'Poor'
        WHEN (s.credit_score_range_lower + s.credit_score_range_upper) / 2.0 < 670  THEN 'Fair'
        WHEN (s.credit_score_range_lower + s.credit_score_range_upper) / 2.0 < 740  THEN 'Good'
        ELSE 'Excellent'
    END                                                         AS credit_score_band,

    CASE s.prosper_rating_alpha
        WHEN 'HR' THEN 1 WHEN 'E'  THEN 2 WHEN 'D' THEN 3
        WHEN 'C'  THEN 4 WHEN 'B'  THEN 5 WHEN 'A' THEN 6
        WHEN 'AA' THEN 7 ELSE NULL
    END                                                         AS rating_ordinal,

    -- ── Income ─────────────────────────────────────────────────────────────
    LN(1 + GREATEST(s.stated_monthly_income, 0))                AS log_monthly_income,

    s.stated_monthly_income * 12                                AS annual_income_est,

    CASE s.income_range
        WHEN '$1-24,999'       THEN 1
        WHEN '$25,000-49,999'  THEN 2
        WHEN '$50,000-74,999'  THEN 3
        WHEN '$75,000-99,999'  THEN 4
        WHEN '$100,000+'       THEN 5
        ELSE NULL
    END                                                         AS income_range_ordinal,

    -- ── Burden ─────────────────────────────────────────────────────────────
    CASE
        WHEN s.stated_monthly_income > 0
        THEN ROUND(
            (s.loan_original_amount / NULLIF(s.stated_monthly_income * 12, 0))::NUMERIC,
            5
        )
        ELSE NULL
    END                                                         AS loan_amount_to_income,

    -- payment_to_income = DTI (monthly_payment / monthly_income)
    s.debt_to_income_ratio                                      AS payment_to_income,

    -- FIX #2: threshold lấy động từ dti_threshold CTE (~75th percentile của HC)
    CASE WHEN s.debt_to_income_ratio > d.p75 THEN 1 ELSE 0 END  AS high_dti_flag,

    -- ── Behavioral (FIX #4: join từ bronze.previous_application_raw) ──────
    COALESCE(p.num_previous_loans, 0)                           AS num_previous_loans,
    COALESCE(p.previous_default_rate, 0.0)::NUMERIC             AS previous_default_rate,

    -- ── Bureau (FIX #10: credit history từ ngân hàng khác qua bronze.bureau_raw) ─
    COALESCE(b.num_bureau_records, 0)                           AS num_bureau_records,
    COALESCE(b.num_active_credit, 0)                            AS num_active_credit,
    COALESCE(b.total_overdue_amount, 0.0)::NUMERIC              AS total_overdue_amount,
    COALESCE(b.max_credit_overdue_days, 0)                      AS max_credit_overdue_days,
    COALESCE(b.has_bad_debt, 0)                                 AS has_bad_debt,

    -- ── Loan type (Cash=1, Revolving=0) ───────────────────────────────────
    CASE WHEN s.listing_category_id = 1 THEN 1 ELSE 0 END       AS loan_type,

    -- ── Boolean flags ──────────────────────────────────────────────────────
    CASE WHEN s.is_homeowner = 'Yes' THEN 1 ELSE 0 END          AS is_homeowner_flag,
    s.income_verifiable::INT                                    AS income_verifiable_flag,

    -- ── Term flags (FIX #5: HC term continuous 12-45 từ credit/annuity, max
    --    thực tế là 45 không phải 60. Buckets cân bằng theo phân phối thực:
    --    ≤18 (34%), 19-25 (37%), ≥26 (29%) — mỗi row có đúng 1 flag = 1.) ──
    CASE WHEN s.term <= 18                  THEN 1 ELSE 0 END   AS term_12_flag,
    CASE WHEN s.term BETWEEN 19 AND 25      THEN 1 ELSE 0 END   AS term_36_flag,
    CASE WHEN s.term >= 26                  THEN 1 ELSE 0 END   AS term_60_flag,

    -- ── Employment grouped ─────────────────────────────────────────────────
    CASE s.employment_status
        WHEN 'Employed'      THEN 'Employed'
        WHEN 'Self-employed' THEN 'Self-employed'
        WHEN 'Retired'       THEN 'Retired'
        WHEN 'Not employed'  THEN 'Not employed'
        WHEN 'Unemployed'    THEN 'Not employed'
        ELSE 'Other/Unknown'
    END                                                         AS employment_status_grouped,

    -- ── Demographics ──────────────────────────────────────────────────────
    s.age_years,
    s.cnt_children,
    s.cnt_fam_members,
    -- v3: new features
    s.years_employed,
    s.occupation_type,

    -- Gender: Male=1, Female=0, XNA → NULL
    CASE s.gender
        WHEN 'M' THEN 1
        WHEN 'F' THEN 0
        ELSE NULL
    END                                                         AS gender_male_flag,

    -- Education ordinal: cao hơn = học vấn cao hơn
    CASE s.education_type
        WHEN 'Academic degree'              THEN 5
        WHEN 'Higher education'             THEN 4
        WHEN 'Incomplete higher'            THEN 3
        WHEN 'Secondary / secondary special' THEN 2
        WHEN 'Lower secondary'              THEN 1
        ELSE NULL
    END                                                         AS education_ordinal,

    -- Family status (3 nhóm chính)
    CASE
        WHEN s.family_status IN ('Married', 'Civil marriage')    THEN 'Married'
        WHEN s.family_status IN ('Single / not married')         THEN 'Single'
        WHEN s.family_status IN ('Widow', 'Separated')           THEN 'Other'
        ELSE 'Other'
    END                                                         AS family_status_grouped,

    CASE WHEN s.family_status IN ('Married', 'Civil marriage') THEN 1 ELSE 0 END
                                                                AS is_married_flag,

    -- ── Missing flags ──────────────────────────────────────────────────────
    CASE WHEN s.credit_score_range_lower IS NULL THEN 1 ELSE 0 END AS credit_score_missing_flag,
    CASE WHEN s.debt_to_income_ratio     IS NULL THEN 1 ELSE 0 END AS dti_missing_flag,
    CASE WHEN s.prosper_rating_alpha     IS NULL THEN 1 ELSE 0 END AS rating_missing_flag,
    -- FIX #9: prosper_score_missing_flag bỏ — Silver filter EXT_SOURCE_2 IS NOT NULL
    --         nên prosper_score luôn có giá trị (flag luôn = 0, zero variance).
    CASE WHEN s.stated_monthly_income    IS NULL THEN 1 ELSE 0 END AS income_missing_flag,

    -- ── Time (FIX #3 cascade: loan_origination_date giờ NULL trong Silver
    --    → origination_year/month sẽ NULL thay vì cố định năm chạy ETL) ────
    EXTRACT(YEAR  FROM s.loan_origination_date)::INT            AS origination_year,
    EXTRACT(MONTH FROM s.loan_origination_date)::INT            AS origination_month,
    s.loan_origination_date

FROM silver.home_credit_cleansed s
CROSS JOIN dti_threshold d
LEFT JOIN prev_stats   p ON s.member_key = p.member_key
LEFT JOIN bureau_stats b ON s.member_key = b.member_key
WHERE s.credit_score_range_lower IS NOT NULL
  AND s.stated_monthly_income    >  0
  AND s.loan_original_amount     >  0;

ALTER TABLE gold.hc_features_v1
ADD PRIMARY KEY (listing_key);

CREATE INDEX IF NOT EXISTS idx_hc_gold_is_default
    ON gold.hc_features_v1(is_default);

CREATE INDEX IF NOT EXISTS idx_hc_gold_credit_score
    ON gold.hc_features_v1(credit_score_midpoint);


-- ── Analytical views for admin credit dashboard ─────────────────────────────

CREATE OR REPLACE VIEW gold.vw_credit_score_distribution AS
SELECT
    CASE
        WHEN credit_score_midpoint >= 740 THEN 'Excellent (740+)'
        WHEN credit_score_midpoint >= 670 THEN 'Good (670-739)'
        WHEN credit_score_midpoint >= 580 THEN 'Fair (580-669)'
        ELSE 'Poor (<580)'
    END                                                          AS score_band,
    COUNT(*)::INT                                                AS loan_count,
    ROUND(100.0 * SUM(is_default) / NULLIF(COUNT(*), 0), 2)     AS default_rate_pct,
    ROUND(AVG(debt_to_income_ratio)::NUMERIC, 4)                 AS avg_dti
FROM gold.hc_features_v1
GROUP BY score_band
ORDER BY score_band;

CREATE OR REPLACE VIEW gold.vw_dti_vs_default AS
SELECT
    CASE
        WHEN payment_to_income < 0.5  THEN 'Low (<0.5)'
        WHEN payment_to_income < 1.0  THEN 'Medium (0.5-1)'
        WHEN payment_to_income < 2.0  THEN 'High (1-2)'
        ELSE 'Very High (2+)'
    END                                                          AS dti_band,
    COUNT(*)::INT                                                AS loan_count,
    ROUND(100.0 * SUM(is_default) / NULLIF(COUNT(*), 0), 2)     AS default_rate_pct
FROM gold.hc_features_v1
GROUP BY dti_band
ORDER BY dti_band;

CREATE OR REPLACE VIEW gold.vw_employment_vs_default AS
SELECT
    employment_status_grouped                                    AS employment,
    COUNT(*)::INT                                                AS loan_count,
    ROUND(100.0 * SUM(is_default) / NULLIF(COUNT(*), 0), 2)     AS default_rate_pct,
    ROUND(AVG(credit_score_midpoint)::NUMERIC, 1)               AS avg_credit_score
FROM gold.hc_features_v1
GROUP BY employment_status_grouped
ORDER BY employment_status_grouped;

