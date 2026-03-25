-- 1. Nạp dữ liệu vào các bảng Dimension (Dùng ON CONFLICT để tránh lỗi trùng lặp)
INSERT INTO core.dim_employment_status (employment_status_name)
SELECT DISTINCT employment_status FROM silver.prosper_loans_cleansed 
WHERE employment_status IS NOT NULL
ON CONFLICT (employment_status_name) DO NOTHING;

INSERT INTO core.dim_occupation (occupation_name)
SELECT DISTINCT occupation FROM silver.prosper_loans_cleansed 
WHERE occupation IS NOT NULL
ON CONFLICT (occupation_name) DO NOTHING;

INSERT INTO core.dim_income_range (income_range_label)
SELECT DISTINCT income_range FROM silver.prosper_loans_cleansed 
WHERE income_range IS NOT NULL
ON CONFLICT (income_range_label) DO NOTHING;

INSERT INTO core.dim_loan_status (loan_status_name)
SELECT DISTINCT loan_status FROM silver.prosper_loans_cleansed 
WHERE loan_status IS NOT NULL
ON CONFLICT (loan_status_name) DO NOTHING;

-- Riêng Listing Category nạp bằng tay hoặc ánh xạ từ số
-- Cập nhật danh sách Listing Category đầy đủ từ 0 đến 20
INSERT INTO core.dim_listing_category (category_id, category_name)
VALUES 
(0, 'Not Available'), (1, 'Debt Consolidation'), (2, 'Home Improvement'), 
(3, 'Business'), (4, 'Personal Loan'), (5, 'Student Use'), 
(6, 'Auto'), (7, 'Other'), (8, 'Baby&Adoption'), 
(9, 'Boat'), (10, 'Cosmetic Procedures'), (11, 'Engagement Ring'), 
(12, 'Green Loans'), (13, 'Household Expenses'), (14, 'Large Purchases'), 
(15, 'Medical/Dental'), (16, 'Motorcycle'), (17, 'RV'), 
(18, 'Taxes'), (19, 'Vacation'), (20, 'Wedding Loans')
ON CONFLICT (category_id) DO UPDATE SET category_name = EXCLUDED.category_name;

-- 2. Nạp dữ liệu vào bảng Borrowers (Lấy unique member_key)
INSERT INTO core.borrowers (member_key, borrower_state, is_homeowner, income_verifiable)
SELECT DISTINCT ON (member_key) 
    member_key, borrower_state, is_borrower_homeowner, income_verifiable
FROM silver.prosper_loans_cleansed
WHERE member_key IS NOT NULL
ON CONFLICT (member_key) DO UPDATE SET
    borrower_state = EXCLUDED.borrower_state,
    is_homeowner = EXCLUDED.is_homeowner;

-- 3. Nạp dữ liệu vào bảng Loans
INSERT INTO core.loans (
    listing_key, loan_number, member_key, loan_original_amount, term, 
    borrower_apr, borrower_rate, listing_creation_date, loan_origination_date, 
    closed_date, loan_status_id, category_id, employment_status_id, occupation_id, income_range_id
)
SELECT 
    s.listing_key, s.loan_number, s.member_key, s.loan_original_amount, s.term,
    s.borrower_apr, s.borrower_rate, s.listing_creation_date, s.loan_origination_date, s.closed_date,
    ls.loan_status_id, s.listing_category_numeric, es.employment_status_id, occ.occupation_id, ir.income_range_id
FROM silver.prosper_loans_cleansed s
LEFT JOIN core.dim_loan_status ls ON s.loan_status = ls.loan_status_name
LEFT JOIN core.dim_employment_status es ON s.employment_status = es.employment_status_name
LEFT JOIN core.dim_occupation occ ON s.occupation = occ.occupation_name
LEFT JOIN core.dim_income_range ir ON s.income_range = ir.income_range_label
ON CONFLICT (listing_key) DO NOTHING;

-- 4. Nạp dữ liệu vào bảng Credit Profiles
INSERT INTO core.credit_profiles (
    listing_key, credit_score_range_lower, credit_score_range_upper, 
    debt_to_income_ratio, stated_monthly_income, prosper_rating_alpha, prosper_score
)
SELECT 
    listing_key, credit_score_range_lower, credit_score_range_upper, 
    debt_to_income_ratio, stated_monthly_income, prosper_rating_alpha, prosper_score
FROM silver.prosper_loans_cleansed
ON CONFLICT (listing_key) DO NOTHING;