-- 1. Tạo Schema Core
CREATE SCHEMA IF NOT EXISTS core;

-- 2. Tạo các bảng Danh mục (Thêm IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS core.dim_employment_status (
    employment_status_id SERIAL PRIMARY KEY,
    employment_status_name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_occupation (
    occupation_id SERIAL PRIMARY KEY,
    occupation_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_income_range (
    income_range_id SERIAL PRIMARY KEY,
    income_range_label VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_loan_status (
    loan_status_id SERIAL PRIMARY KEY,
    loan_status_name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dim_listing_category (
    category_id INTEGER PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL
);

-- 3. Tạo bảng thực thể chính (Thêm IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS core.borrowers (
    member_key VARCHAR(100) PRIMARY KEY,
    borrower_state VARCHAR(10),
    is_homeowner BOOLEAN,
    income_verifiable BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS core.loans (
    listing_key VARCHAR(100) PRIMARY KEY,
    loan_number VARCHAR(50) UNIQUE,
    member_key VARCHAR(100) NOT NULL,
    loan_original_amount NUMERIC(15, 2) CHECK (loan_original_amount > 0),
    term INTEGER CHECK (term IN (12, 36, 60)),
    borrower_apr NUMERIC(10, 5),
    borrower_rate NUMERIC(10, 5),
    listing_creation_date TIMESTAMP,
    loan_origination_date TIMESTAMP,
    closed_date TIMESTAMP,
    loan_status_id INTEGER REFERENCES core.dim_loan_status(loan_status_id),
    category_id INTEGER REFERENCES core.dim_listing_category(category_id),
    employment_status_id INTEGER REFERENCES core.dim_employment_status(employment_status_id),
    occupation_id INTEGER REFERENCES core.dim_occupation(occupation_id),
    income_range_id INTEGER REFERENCES core.dim_income_range(income_range_id),
    CONSTRAINT fk_borrower FOREIGN KEY (member_key) REFERENCES core.borrowers(member_key)
);

CREATE TABLE IF NOT EXISTS core.credit_profiles (
    profile_id SERIAL PRIMARY KEY,
    listing_key VARCHAR(100) UNIQUE REFERENCES core.loans(listing_key),
    credit_score_range_lower INTEGER,
    credit_score_range_upper INTEGER,
    debt_to_income_ratio NUMERIC(10, 5),
    stated_monthly_income NUMERIC(15, 2),
    prosper_rating_alpha VARCHAR(5),
    prosper_score INTEGER
);