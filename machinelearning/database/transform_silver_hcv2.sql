-- SILVER LAYER — Home Credit Credit Risk Model Stability (v2)
-- Source : bronze.train_base + train_static_0 + train_static_cb_0
--          + train_person_1 + train_credit_bureau_a_1 + train_applprev_1
-- Target : silver.hc_v2_cleansed
--
-- Joins multi-depth tables into a single flat table.
-- depth=0 tables join directly on case_id.
-- depth=1 tables are aggregated per case_id first.

CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.hc_v2_cleansed;

CREATE TABLE silver.hc_v2_cleansed AS
WITH
-- ═══════════════════════════════════════════════════════════════════════════
-- 1. Person (depth=1): filter applicant only (num_group1=0), one row per case
-- ═══════════════════════════════════════════════════════════════════════════
person_applicant AS (
    SELECT
        case_id,
        birth_259D                         AS birth_date,
        education_927M                     AS education_level,
        mainoccupationinc_384A             AS occupation_income,
        incometype_1044T                   AS income_type,
        CASE empl_employedtotal_800L
            WHEN 'LESS_ONE'  THEN 0.5
            WHEN 'MORE_ONE'  THEN 3.0
            WHEN 'MORE_FIVE' THEN 7.0
            ELSE NULL
        END                                AS employment_length,
        CAST(familystate_447L AS VARCHAR)   AS family_state,
        CAST(gender_992L AS VARCHAR)        AS gender,
        CAST(housetype_905L AS VARCHAR)     AS house_type,
        CAST(maritalst_703L AS VARCHAR)     AS marital_status
    FROM bronze.train_person_1
    WHERE num_group1 = 0
),

-- ═══════════════════════════════════════════════════════════════════════════
-- 2. Credit Bureau A (depth=1): aggregate per case_id
--    ~15.9M rows → 1.39M unique case_ids
-- ═══════════════════════════════════════════════════════════════════════════
bureau_agg AS (
    SELECT
        case_id,
        COUNT(*)::INT                                   AS num_bureau_contracts,
        -- Active vs closed contracts
        COUNT(*) FILTER (
            WHERE contractst_545M = 'a55475b1'
        )::INT                                          AS num_contracts_type_a,
        COUNT(*) FILTER (
            WHERE contractst_545M = '7241344e'
        )::INT                                          AS num_contracts_type_b,
        -- DPD (days past due)
        COALESCE(MAX(dpdmax_139P), 0)                   AS max_dpd_active,
        COALESCE(MAX(dpdmax_757P), 0)                   AS max_dpd_closed,
        -- Outstanding & overdue
        COALESCE(SUM(debtoutstand_525A), 0)::NUMERIC    AS total_outstanding_debt,
        COALESCE(SUM(debtoverdue_47A), 0)::NUMERIC      AS total_overdue_amount_bureau,
        COALESCE(SUM(overdueamount_659A), 0)::NUMERIC   AS total_overdue_active,
        COALESCE(SUM(overdueamount_31A), 0)::NUMERIC    AS total_overdue_closed,
        COALESCE(MAX(overdueamountmax_155A), 0)::NUMERIC AS max_overdue_amount,
        -- Contract counts
        COALESCE(MAX(numberofcontrsvalue_258L), 0)::INT AS num_active_contracts_cb,
        COALESCE(MAX(numberofcontrsvalue_358L), 0)::INT AS num_closed_contracts_cb,
        -- Overdue instalments
        COALESCE(MAX(numberofoverdueinstls_725L), 0)::INT AS max_overdue_instls_active,
        COALESCE(MAX(numberofoverdueinstls_834L), 0)::INT AS max_overdue_instls_closed,
        -- Instalment amounts
        COALESCE(AVG(instlamount_768A), 0)::NUMERIC     AS avg_instalment_active,
        -- Prolongations
        COALESCE(SUM(prolongationcount_599L), 0)::INT   AS total_prolongations
    FROM bronze.train_credit_bureau_a_1
    GROUP BY case_id
),

-- ═══════════════════════════════════════════════════════════════════════════
-- 3. Previous Applications (depth=1): aggregate per case_id
--    ~6.5M rows → 1.22M unique case_ids
--    status_219L: A=Approved, D/K=common, T=?, N=?, ...
-- ═══════════════════════════════════════════════════════════════════════════
prev_app_agg AS (
    SELECT
        case_id,
        COUNT(*)::INT                                                  AS num_previous_apps,
        COUNT(*) FILTER (WHERE status_219L = 'A')::INT                 AS num_prev_approved,
        COUNT(*) FILTER (WHERE status_219L IN ('D', 'N', 'Q'))::INT    AS num_prev_rejected,
        COUNT(*) FILTER (WHERE status_219L = 'K')::INT                 AS num_prev_active,
        COALESCE(AVG(credamount_590A), 0)::NUMERIC                     AS avg_prev_credit_amount,
        COALESCE(MAX(actualdpd_943P), 0)                               AS max_prev_dpd,
        COALESCE(AVG(actualdpd_943P), 0)::NUMERIC                      AS avg_prev_dpd,
        -- Rejection rate (proxy for credit history negativity)
        ROUND(
            COUNT(*) FILTER (WHERE status_219L IN ('D', 'N', 'Q'))::NUMERIC
            / NULLIF(COUNT(*), 0),
            4
        )                                                              AS previous_rejection_rate
    FROM bronze.train_applprev_1
    GROUP BY case_id
),

-- ═══════════════════════════════════════════════════════════════════════════
-- 4. Static CB (depth=0): credit bureau queries and external data
-- ═══════════════════════════════════════════════════════════════════════════
cb_static AS (
    SELECT
        case_id,
        -- Bureau query counts (credit hunger signal)
        COALESCE(days30_165L, 0)::INT    AS cb_queries_30d,
        COALESCE(days90_310L, 0)::INT    AS cb_queries_90d,
        COALESCE(days180_256L, 0)::INT   AS cb_queries_180d,
        COALESCE(days360_512L, 0)::INT   AS cb_queries_360d,
        -- Credit bureau rejection history
        COALESCE(for3years_128L, 0)      AS rejections_3y,
        COALESCE(foryear_618L, 0)        AS rejections_1y,
        -- Number of queries total
        COALESCE(numberofqueries_373L, 0)::INT AS num_cb_queries,
        -- Contract sum from external bureau
        contractssum_5085716L            AS cb_contracts_sum
    FROM bronze.train_static_cb_0
)

-- ═══════════════════════════════════════════════════════════════════════════
-- FINAL JOIN: base + static_0 + cb_static + person + bureau_agg + prev_app
-- ═══════════════════════════════════════════════════════════════════════════
SELECT
    -- ── Keys & Target ─────────────────────────────────────────────────────
    b.case_id::TEXT                                    AS listing_key,
    b.case_id::TEXT                                    AS member_key,
    b.target                                           AS is_default,
    b.date_decision,
    b.WEEK_NUM,

    -- ── Loan features (static_0) ──────────────────────────────────────────
    s.credamount_770A                                  AS loan_original_amount,
    s.annuity_780A                                     AS annuity,
    s.maininc_215A                                     AS stated_monthly_income,
    s.currdebt_22A                                     AS current_debt,
    s.totaldebt_9A                                     AS total_debt,

    -- ── Term (credit / annuity, capped 6–120 months) ─────────────────────
    CASE
        WHEN s.annuity_780A IS NOT NULL AND s.annuity_780A > 0
        THEN GREATEST(6, LEAST(120,
                 ROUND(s.credamount_770A / s.annuity_780A)::INT
             ))
        ELSE 36
    END                                                AS term,

    -- ── Income (monthly) ──────────────────────────────────────────────────
    s.maininc_215A                                     AS monthly_income,

    -- ── DTI (annuity / monthly_income) ────────────────────────────────────
    CASE
        WHEN s.maininc_215A > 0 AND s.annuity_780A IS NOT NULL
        THEN ROUND((s.annuity_780A / s.maininc_215A)::NUMERIC, 5)
        ELSE NULL
    END                                                AS debt_to_income_ratio,

    -- ── DPD features (static_0 — direct) ─────────────────────────────────
    COALESCE(s.maxdpdlast24m_143P, 0)                  AS max_dpd_24m,
    COALESCE(s.maxdpdlast12m_727P, 0)                  AS max_dpd_12m,
    COALESCE(s.maxdpdlast3m_392P, 0)                   AS max_dpd_3m,
    COALESCE(s.avgdbddpdlast24m_3658932P, 0)::NUMERIC  AS avg_dpd_24m,
    COALESCE(s.avgdbddpdlast3m_4187120P, 0)::NUMERIC   AS avg_dpd_3m,
    COALESCE(s.numactivecreds_622L, 0)::INT             AS num_active_credits,
    COALESCE(s.numinstlswithdpd10_728L, 0)::INT         AS num_installs_dpd10,
    COALESCE(s.numinstlswithdpd5_4187116L, 0)::INT      AS num_installs_dpd5,

    -- ── Payment behavior (static_0) ──────────────────────────────────────
    COALESCE(s.avgpmtlast12m_4525200A, 0)::NUMERIC     AS avg_payment_12m,
    COALESCE(s.cntpmts24_3658933L, 0)::INT              AS num_payments_24m,
    COALESCE(s.cntincpaycont9m_3716944L, 0)::INT        AS num_incoming_payments_9m,

    -- ── Application behavior (static_0) ──────────────────────────────────
    COALESCE(s.applications30d_658L, 0)::INT            AS num_apps_30d,

    -- ── Person demographics ──────────────────────────────────────────────
    pa.birth_date,
    -- Age in years from birth_date
    CASE
        WHEN pa.birth_date IS NOT NULL
        THEN ROUND((b.date_decision::DATE - pa.birth_date::DATE) / 365.25, 1)::NUMERIC
        ELSE NULL
    END                                                AS age_years,
    pa.education_level,
    pa.occupation_income,
    pa.income_type,
    pa.employment_length,
    pa.family_state,
    pa.gender,
    pa.house_type,

    -- ── Employment status grouped ─────────────────────────────────────────
    CASE pa.income_type
        WHEN 'EMPLOYED'                  THEN 'Employed'
        WHEN 'PRIVATE_SECTOR_EMPLOYEE'   THEN 'Employed'
        WHEN 'SALARIED_GOVT'             THEN 'Employed'
        WHEN 'RETIRED_PENSIONER'         THEN 'Retired'
        WHEN 'SELFEMPLOYED'              THEN 'Self-employed'
        WHEN 'HANDICAPPED'              THEN 'Not employed'
        WHEN 'HANDICAPPED_2'            THEN 'Not employed'
        WHEN 'HANDICAPPED_3'            THEN 'Not employed'
        WHEN 'OTHER'                    THEN 'Other/Unknown'
        ELSE 'Other/Unknown'
    END                                                AS employment_status,

    -- ── Income verifiable ─────────────────────────────────────────────────
    CASE
        WHEN pa.income_type IN ('EMPLOYED', 'PRIVATE_SECTOR_EMPLOYEE',
                                'SALARIED_GOVT', 'SELFEMPLOYED')
             AND pa.employment_length IS NOT NULL
             AND pa.employment_length > 0
        THEN TRUE
        ELSE FALSE
    END                                                AS income_verifiable,

    -- ── Homeowner flag ────────────────────────────────────────────────────
    CASE
        WHEN pa.house_type = 'OWNED' THEN TRUE
        ELSE FALSE
    END                                                AS is_homeowner,

    -- ── Family / marital ──────────────────────────────────────────────────
    CASE
        WHEN pa.family_state IN ('MARRIED', 'LIVING_WITH_PARTNER') THEN TRUE
        ELSE FALSE
    END                                                AS is_married,

    -- ── Bureau aggregates (from CTE) ──────────────────────────────────────
    COALESCE(ba.num_bureau_contracts, 0)               AS num_bureau_records,
    COALESCE(ba.num_active_contracts_cb, 0)            AS num_active_credit_bureau,
    COALESCE(ba.total_outstanding_debt, 0)::NUMERIC    AS total_outstanding_debt,
    COALESCE(ba.total_overdue_amount_bureau, 0)::NUMERIC AS total_overdue_amount,
    COALESCE(ba.max_dpd_active, 0)                     AS max_dpd_bureau_active,
    COALESCE(ba.max_dpd_closed, 0)                     AS max_dpd_bureau_closed,
    COALESCE(ba.max_overdue_amount, 0)::NUMERIC        AS max_overdue_amount,
    COALESCE(ba.max_overdue_instls_active, 0)          AS max_overdue_instls,
    COALESCE(ba.total_prolongations, 0)                AS total_prolongations,

    -- ── Previous application aggregates ───────────────────────────────────
    COALESCE(paa.num_previous_apps, 0)                 AS num_previous_apps,
    COALESCE(paa.num_prev_approved, 0)                 AS num_previous_loans,
    COALESCE(paa.num_prev_rejected, 0)                 AS num_prev_rejected,
    COALESCE(paa.previous_rejection_rate, 0)::NUMERIC  AS previous_default_rate,
    COALESCE(paa.max_prev_dpd, 0)                      AS max_prev_app_dpd,
    COALESCE(paa.avg_prev_dpd, 0)::NUMERIC             AS avg_prev_app_dpd,

    -- ── CB static features ───────────────────────────────────────────────
    COALESCE(cbs.cb_queries_30d, 0)                    AS cb_queries_30d,
    COALESCE(cbs.cb_queries_90d, 0)                    AS cb_queries_90d,
    COALESCE(cbs.cb_queries_180d, 0)                   AS cb_queries_180d,
    COALESCE(cbs.num_cb_queries, 0)                    AS num_cb_queries,
    COALESCE(cbs.rejections_3y, 0)                     AS cb_rejections_3y

FROM bronze.train_base b
JOIN bronze.train_static_0 s USING (case_id)
LEFT JOIN cb_static cbs USING (case_id)
LEFT JOIN person_applicant pa USING (case_id)
LEFT JOIN bureau_agg ba USING (case_id)
LEFT JOIN prev_app_agg paa USING (case_id)
WHERE b.target IS NOT NULL
  AND s.credamount_770A > 0
  AND s.annuity_780A > 0;

-- ── Indexes ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_hcv2_silver_default
    ON silver.hc_v2_cleansed(is_default);

CREATE INDEX IF NOT EXISTS idx_hcv2_silver_member
    ON silver.hc_v2_cleansed(member_key);
