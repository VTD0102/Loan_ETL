-- XÓA DỮ LIỆU CŨ TRƯỚC KHI NẠP (Để tránh lỗi trùng lặp khi chạy lại)
TRUNCATE TABLE silver.prosper_loans_cleansed;

---------------------------------------------------------
-- PHẦN 2: NẠP DỮ LIỆU VỚI LOGIC CHỐNG TRÙNG LẶP      --
---------------------------------------------------------

INSERT INTO silver.prosper_loans_cleansed (
    listing_key, listing_creation_date, loan_status, closed_date,
    borrower_apr, borrower_rate, prosper_rating_alpha, prosper_score,
    listing_category_numeric, occupation, employment_status,
    is_borrower_homeowner, credit_score_range_lower, credit_score_range_upper,
    debt_to_income_ratio, income_range, stated_monthly_income,
    loan_original_amount, loan_origination_date, term, is_default
)
SELECT DISTINCT ON ("ListingKey") -- CHỈ LẤY DUY NHẤT 1 DÒNG cho mỗi ListingKey
    "ListingKey",
    "ListingCreationDate"::TIMESTAMP,
    "LoanStatus",
    NULLIF("ClosedDate", '')::TIMESTAMP,
    NULLIF("BorrowerAPR", '')::DECIMAL,
    NULLIF("BorrowerRate", '')::DECIMAL,
    COALESCE(NULLIF("ProsperRating (Alpha)", ''), NULLIF("CreditGrade", '')),
    NULLIF("ProsperScore", '')::FLOAT::INT,
    NULLIF("ListingCategory (numeric)", '')::FLOAT::INT,
    "Occupation",
    "EmploymentStatus",
    "IsBorrowerHomeowner"::BOOLEAN,
    NULLIF("CreditScoreRangeLower", '')::FLOAT::INT,
    NULLIF("CreditScoreRangeUpper", '')::FLOAT::INT,
    NULLIF("DebtToIncomeRatio", '')::DECIMAL,
    "IncomeRange",
    NULLIF("StatedMonthlyIncome", '')::DECIMAL,
    NULLIF("LoanOriginalAmount", '')::DECIMAL,
    "LoanOriginationDate"::TIMESTAMP,
    NULLIF("Term", '')::FLOAT::INT,
    CASE WHEN "LoanStatus" IN ('Chargedoff', 'Defaulted') THEN 1 ELSE 0 END
FROM bronze.prosper_loans_raw
ORDER BY "ListingKey", "ListingCreationDate" DESC; -- Ưu tiên lấy dòng mới nhất nếu trùng
COMMENT ON TABLE silver.prosper_loans_cleansed IS 'Bảng dữ liệu đã làm sạch, ép kiểu và loại trùng lặp cho dự án Prosper';
COMMENT ON COLUMN silver.prosper_loans_cleansed.is_default IS '1: Khoản vay vỡ nợ (Chargedoff/Defaulted), 0: Bình thường';
COMMENT ON COLUMN silver.prosper_loans_cleansed.prosper_rating_alpha IS 'Hạng tín dụng gộp từ ProsperRating và CreditGrade';
-- Cấp quyền xem cho tất cả mọi người
GRANT USAGE ON SCHEMA silver TO PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA silver TO PUBLIC;