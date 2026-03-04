CREATE DATABASE "postgres_LoanManagement";
-- Lớp Bronze: Chứa dữ liệu thô, không chỉnh sửa
CREATE SCHEMA IF NOT EXISTS bronze;

-- Lớp Silver: Dữ liệu đã sạch, chuẩn hóa kiểu dữ liệu cho Người 2 & 3
CREATE SCHEMA IF NOT EXISTS silver;

-- Lớp Gold: Dữ liệu đã sẵn sàng để train model cho Người 5
CREATE SCHEMA IF NOT EXISTS gold;
-- Xóa bảng cũ nếu muốn làm lại từ đầu
DROP TABLE IF EXISTS silver.prosper_loans_cleansed;

CREATE TABLE silver.prosper_loans_cleansed (
    listing_key TEXT PRIMARY KEY,
    listing_creation_date TIMESTAMP,
    loan_status TEXT,
    closed_date TIMESTAMP,
    borrower_apr DECIMAL(10, 5),
    borrower_rate DECIMAL(10, 5),
    prosper_rating_alpha TEXT, -- Cột quan trọng gộp từ 2 nguồn
    prosper_score INT,
    listing_category_numeric INT,
    occupation TEXT,
    employment_status TEXT,
    is_borrower_homeowner BOOLEAN,
    credit_score_range_lower INT,
    credit_score_range_upper INT,
    debt_to_income_ratio DECIMAL(10, 5),
    income_range TEXT,
    stated_monthly_income DECIMAL(15, 2),
    loan_original_amount DECIMAL(15, 2),
    loan_origination_date TIMESTAMP,
    term INT,
    -- Biến Target cho Người 5: 1 là Vỡ nợ, 0 là Bình thường
    is_default INT
);
