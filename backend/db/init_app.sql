-- CreditIntel App Tables
-- Run once on Supabase SQL Editor when creating backend app tables manually.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    username      VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ─── Loan Applications ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loan_applications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status              VARCHAR(30) NOT NULL CHECK (status IN (
                            'AUTO_REJECTED','PENDING_REVIEW','ADMIN_REJECTED',
                            'AWAITING_INFO','INFO_SUBMITTED','APPROVED',
                            'REJECTED','PENDING')),
    -- Customer form inputs
    monthly_income      NUMERIC(15,2),
    loan_amount         NUMERIC(15,2),
    term                INT,
    employment_status   VARCHAR(50),
    dti                 NUMERIC(6,4),
    is_homeowner        BOOLEAN,
    listing_category    VARCHAR(50),
    credit_score        NUMERIC(6,2),
    -- Optional inputs for the current customer risk model
    occupation_type     VARCHAR(100),
    years_employed      NUMERIC(5,2),
    num_bureau_records  INT,
    num_active_credit   INT,
    total_overdue_amount NUMERIC(15,2),
    max_credit_overdue_days INT,
    has_bad_debt        BOOLEAN,
    income_verifiable_flag BOOLEAN,
    age_years           INT,
    education_ordinal   INT,
    is_married_flag     BOOLEAN,
    -- ML outputs
    default_probability NUMERIC(6,4),
    risk_level          VARCHAR(10),
    risk_score          INT,
    recommended_amount  NUMERIC(15,2),
    recommended_term    INT,
    model_version       VARCHAR(100),
    feature_snapshot    JSONB,
    imputed_features    JSONB,
    -- Metadata
    submitted_at        TIMESTAMP DEFAULT NOW(),
    reviewed_at         TIMESTAMP,
    reviewed_by         UUID REFERENCES users(id),
    admin_note          TEXT
);

CREATE INDEX IF NOT EXISTS idx_loan_apps_user   ON loan_applications(user_id);
CREATE INDEX IF NOT EXISTS idx_loan_apps_status ON loan_applications(status);

-- ─── Personal Info ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS personal_info (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id   UUID NOT NULL REFERENCES loan_applications(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id),
    full_name        VARCHAR(200),
    id_card_number   VARCHAR(20),
    phone            VARCHAR(20),
    email            VARCHAR(255),
    date_of_birth    DATE,
    address          TEXT,
    submitted_at     TIMESTAMP DEFAULT NOW()
);

-- ─── Chat ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role       VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    sources    JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user     ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session  ON chat_messages(session_id, created_at);

-- ─── Seed admin account ───────────────────────────────────────────────────────
-- Replace <HASHED_PASSWORD> with bcrypt hash before running
-- INSERT INTO users (email, username, password_hash, role)
-- VALUES ('admin@creditintel.vn', 'admin', '<HASHED_PASSWORD>', 'admin');
