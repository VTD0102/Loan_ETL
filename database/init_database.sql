-- Khởi tạo schema cho pipeline Bronze -> Silver trên PostgreSQL.
-- File này chỉ tạo các object cần thiết cho Silver layer, không tạo Gold.

-- Schema Bronze: lưu dữ liệu thô ingest từ source.
CREATE SCHEMA IF NOT EXISTS bronze;

-- Schema Silver: lưu dữ liệu đã làm sạch và chuẩn hóa để phục vụ downstream.
CREATE SCHEMA IF NOT EXISTS silver;

-- Schema Gold 
CREATE SCHEMA IF NOT EXISTS gold;

-- Tạo mới bảng Silver để đảm bảo đúng schema mục tiêu.
DROP TABLE IF EXISTS silver.prosper_loans_cleansed;

CREATE TABLE silver.prosper_loans_cleansed (
    listing_key TEXT PRIMARY KEY,
    listing_creation_date TIMESTAMP,
    loan_status TEXT,
    closed_date TIMESTAMP,
    borrower_apr NUMERIC(10, 5),
    borrower_rate NUMERIC(10, 5),
    prosper_rating_alpha TEXT,
    prosper_score INTEGER,
    listing_category_numeric INTEGER,
    occupation TEXT,
    employment_status TEXT,
    is_borrower_homeowner BOOLEAN,
    credit_score_range_lower INTEGER,
    credit_score_range_upper INTEGER,
    debt_to_income_ratio NUMERIC(10, 5),
    income_range TEXT,
    stated_monthly_income NUMERIC(15, 2),
    loan_original_amount NUMERIC(15, 2),
    loan_origination_date TIMESTAMP,
    term INTEGER,
    is_default SMALLINT NOT NULL
);

COMMENT ON TABLE silver.prosper_loans_cleansed IS
'Silver layer cho Prosper loan dataset: dữ liệu đã làm sạch, ép kiểu, khử trùng lặp và gắn cờ default.';

COMMENT ON COLUMN silver.prosper_loans_cleansed.listing_key IS
'Khóa duy nhất của listing sau khi loại bỏ duplicate theo listing_key.';

COMMENT ON COLUMN silver.prosper_loans_cleansed.prosper_rating_alpha IS
'Giá trị rating chuẩn hóa, ưu tiên ProsperRating (Alpha), fallback sang CreditGrade.';

COMMENT ON COLUMN silver.prosper_loans_cleansed.is_default IS
'Target phục vụ downstream: 1 nếu LoanStatus = Chargedoff/Defaulted, ngược lại = 0.';

-- Tạo Index cho loan_status và listing_creation_date để tối ưu query
CREATE INDEX IF NOT EXISTS idx_silver_loan_status ON silver.prosper_loans_cleansed(loan_status);
CREATE INDEX IF NOT EXISTS idx_silver_listing_creation_date ON silver.prosper_loans_cleansed(listing_creation_date);

