-- SILVER LAYER — Home Credit Default Risk
-- Source : bronze.home_credit_raw  (application_train.csv)
-- Target : silver.home_credit_cleansed
--
-- Column mapping sao cho tương thích với retrain_customer_model.py
-- và cùng schema với silver.prosper_loans_cleansed.

CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.home_credit_cleansed;

CREATE TABLE silver.home_credit_cleansed AS
WITH cleaned AS (
    SELECT
        -- ── Keys ──────────────────────────────────────────────────────────
        "SK_ID_CURR"::TEXT                             AS listing_key,
        "SK_ID_CURR"::TEXT                             AS member_key,

        -- ── Target ────────────────────────────────────────────────────────
        CASE WHEN "TARGET" = 1 THEN 1 ELSE 0 END      AS is_default,

        -- ── Loan ──────────────────────────────────────────────────────────
        "AMT_CREDIT"                                   AS loan_original_amount,

        -- Term ≈ credit / annuity (tháng). Giới hạn 12–60 để tránh outlier.
        CASE
            WHEN "AMT_ANNUITY" IS NOT NULL AND "AMT_ANNUITY" > 0
            THEN GREATEST(12, LEAST(60,
                     ROUND("AMT_CREDIT" / "AMT_ANNUITY")::INT
                 ))
            ELSE 36
        END                                            AS term,

        -- ── Income ────────────────────────────────────────────────────────
        "AMT_INCOME_TOTAL" / 12.0                     AS stated_monthly_income,

        CASE
            WHEN "AMT_INCOME_TOTAL" < 45000   THEN '$1-24,999'
            WHEN "AMT_INCOME_TOTAL" < 90000   THEN '$25,000-49,999'
            WHEN "AMT_INCOME_TOTAL" < 135000  THEN '$50,000-74,999'
            WHEN "AMT_INCOME_TOTAL" < 180000  THEN '$75,000-99,999'
            ELSE '$100,000+'
        END                                            AS income_range,

        -- ── DTI: monthly_payment / monthly_income ─────────────────────────
        CASE
            WHEN "AMT_INCOME_TOTAL" > 0 AND "AMT_ANNUITY" IS NOT NULL
            THEN ROUND(
                ("AMT_ANNUITY" / NULLIF("AMT_INCOME_TOTAL" / 12.0, 0))::NUMERIC,
                5
            )
            ELSE NULL
        END                                            AS debt_to_income_ratio,

        -- ── Credit Score (EXT_SOURCE_2 → 300–850) ─────────────────────────
        -- EXT_SOURCE_2 actual range = [0, 0.855], multiplier 643 = 550/0.855
        -- để max = 0.855 → 850 (cũ là * 550 → cap tại 770, mất 80 điểm trên).
        -- FIX #6
        CASE
            WHEN "EXT_SOURCE_2" IS NOT NULL
            THEN GREATEST(300, LEAST(850,
                     ROUND(300 + "EXT_SOURCE_2" * 643)::INT - 25
                 ))
            ELSE NULL
        END                                            AS credit_score_range_lower,

        CASE
            WHEN "EXT_SOURCE_2" IS NOT NULL
            THEN GREATEST(300, LEAST(850,
                     ROUND(300 + "EXT_SOURCE_2" * 643)::INT + 25
                 ))
            ELSE NULL
        END                                            AS credit_score_range_upper,

        -- ── Demographic features ──────────────────────────────────────────
        -- DAYS_BIRTH âm (đếm ngày ngược tới ngày sinh) → tuổi = -DAYS_BIRTH/365
        ROUND(-"DAYS_BIRTH" / 365.25, 1)::NUMERIC      AS age_years,
        "CODE_GENDER"                                  AS gender,
        "NAME_EDUCATION_TYPE"                          AS education_type,
        "NAME_FAMILY_STATUS"                           AS family_status,
        "CNT_CHILDREN"::INT                            AS cnt_children,
        "CNT_FAM_MEMBERS"::NUMERIC                     AS cnt_fam_members,

        -- ── v3 features ───────────────────────────────────────────────────
        -- years_employed: abs(DAYS_EMPLOYED)/365.25; 365243 (N/A) và NULL → 0
        CASE
            WHEN "DAYS_EMPLOYED" IS NULL OR "DAYS_EMPLOYED" = 365243 THEN 0.0
            ELSE ROUND(ABS("DAYS_EMPLOYED") / 365.25, 1)
        END::NUMERIC                                   AS years_employed,

        -- occupation_type: 18 nghề nghiệp HC; NULL → 'Unknown'
        COALESCE("OCCUPATION_TYPE", 'Unknown')         AS occupation_type,

        -- ── Rating (analogue of prosper_rating_alpha) ─────────────────────
        CASE
            WHEN "EXT_SOURCE_2" >= 0.80 THEN 'AA'
            WHEN "EXT_SOURCE_2" >= 0.65 THEN 'A'
            WHEN "EXT_SOURCE_2" >= 0.50 THEN 'B'
            WHEN "EXT_SOURCE_2" >= 0.35 THEN 'C'
            WHEN "EXT_SOURCE_2" >= 0.20 THEN 'D'
            WHEN "EXT_SOURCE_2" IS NOT NULL THEN 'HR'
            ELSE NULL
        END                                            AS prosper_rating_alpha,

        -- ── Homeowner ─────────────────────────────────────────────────────
        -- Lưu dưới dạng 'Yes'/'No' để tương thích với SILVER_QUERY hiện tại
        CASE WHEN "FLAG_OWN_REALTY" = 'Y' THEN 'Yes' ELSE 'No' END
                                                       AS is_homeowner,
        CASE WHEN "FLAG_OWN_REALTY" = 'Y' THEN TRUE ELSE FALSE END
                                                       AS is_borrower_homeowner,

        -- ── Employment ────────────────────────────────────────────────────
        CASE "NAME_INCOME_TYPE"
            WHEN 'Working'              THEN 'Employed'
            WHEN 'Commercial associate' THEN 'Self-employed'
            WHEN 'Pensioner'            THEN 'Retired'
            WHEN 'State servant'        THEN 'Employed'
            WHEN 'Student'              THEN 'Not employed'
            WHEN 'Unemployed'           THEN 'Unemployed'
            ELSE 'Other'
        END                                            AS employment_status,

        -- ── Income verifiable ─────────────────────────────────────────────
        -- DAYS_EMPLOYED = 365243 là placeholder "Not applicable" trong HC
        CASE
            WHEN "FLAG_EMP_PHONE" = 1
             AND "DAYS_EMPLOYED" <> 365243
             AND "DAYS_EMPLOYED" IS NOT NULL
            THEN TRUE
            ELSE FALSE
        END                                            AS income_verifiable,

        -- ── Listing category (1=Cash, 2=Revolving) ────────────────────────
        CASE "NAME_CONTRACT_TYPE"
            WHEN 'Cash loans'       THEN 1
            WHEN 'Revolving loans'  THEN 2
            ELSE 0
        END                                            AS listing_category_id,

        -- ── Prosper score proxy (EXT_SOURCE mean → 1–10) ──────────────────
        CASE
            WHEN "EXT_SOURCE_2" IS NOT NULL
            THEN GREATEST(1, LEAST(10,
                     ROUND("EXT_SOURCE_2" * 10)::INT
                 ))
            ELSE NULL
        END                                            AS prosper_score,

        -- ── Rates (HC không có APR thực — term tự derive từ credit/annuity,
        --    nên (annuity*12/credit - 1) cho giá trị âm 88.7% rows. Để NULL.) ─
        NULL::NUMERIC                                  AS borrower_apr,
        NULL::NUMERIC                                  AS borrower_rate,

        -- ── Dates (HC không có ngày gốc — để NULL thay vì CURRENT_TIMESTAMP
        --    để tránh origination_year/month bị cố định = năm chạy ETL) ────
        NULL::TIMESTAMP                                AS loan_origination_date,
        NULL::TIMESTAMP                                AS listing_creation_date,
        NULL::TIMESTAMP                                AS date_credit_pulled,
        NULL::TIMESTAMP                                AS closed_date,
        NULL::VARCHAR                                  AS loan_status,
        NULL::VARCHAR                                  AS borrower_state,
        NULL::VARCHAR                                  AS loan_key,
        NULL::VARCHAR                                  AS loan_number,
        NULL::VARCHAR                                  AS occupation

    FROM bronze.home_credit_raw
    WHERE "AMT_INCOME_TOTAL" > 0
      AND "AMT_CREDIT"       > 0
      AND "TARGET"           IS NOT NULL
)
SELECT *
FROM cleaned
WHERE debt_to_income_ratio IS NOT NULL
  AND debt_to_income_ratio BETWEEN 0 AND 5    -- loại outlier DTI cực đoan
  AND stated_monthly_income > 0;

-- ── Index cho ML queries ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_hc_silver_is_default
    ON silver.home_credit_cleansed(is_default);

CREATE INDEX IF NOT EXISTS idx_hc_silver_member_key
    ON silver.home_credit_cleansed(member_key);

