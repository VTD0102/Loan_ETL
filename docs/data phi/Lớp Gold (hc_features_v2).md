# 4\. Lớp Gold (hc_features_v2)

## Thông tin tổng quan

| Thuộc tính | Giá trị |
| --- | --- |
| Tên bảng | hc_features_v2 |
| Schema | gold |
| Số cột | 53  |
| Số bản ghi | 1,526,659 |
| Khóa chính | listing_key |
| Biến mục tiêu | is_default |
| Tỷ lệ Default | 3.10% |

## Danh sách các cột trong Gold

| STT | Tên cột |
| --- | --- |
| 1   | listing_key |
| 2   | member_key |
| 3   | is_default |
| 4   | date_decision |
| 5   | WEEK_NUM |
| 6   | loan_original_amount |
| 7   | term |
| 8   | stated_monthly_income |
| 9   | debt_to_income_ratio |
| 10  | loan_amount_to_income |
| 11  | log_monthly_income |
| 12  | payment_to_income |
| 13  | high_dti_flag |
| 14  | current_debt_ratio |
| 15  | total_debt_to_income |
| 16  | max_dpd_24m |
| 17  | max_dpd_12m |
| 18  | max_dpd_3m |
| 19  | avg_dpd_24m |
| 20  | avg_dpd_recent |
| 21  | num_active_credit |
| 22  | num_installs_dpd10 |
| 23  | num_installs_dpd5 |
| 24  | avg_payment_12m |
| 25  | num_payments_24m |
| 26  | num_incoming_payments_9m |
| 27  | num_apps_30d |
| 28  | num_bureau_records |
| 29  | num_active_credit_bureau |
| 30  | total_outstanding_debt |
| 31  | total_overdue_amount |
| 32  | max_credit_overdue_days |
| 33  | max_overdue_amount |
| 34  | max_overdue_instls |
| 35  | total_prolongations |
| 36  | has_bad_debt |
| 37  | num_previous_loans |
| 38  | previous_default_rate |
| 39  | max_prev_app_dpd |
| 40  | avg_prev_app_dpd |
| 41  | cb_queries_30d |
| 42  | cb_queries_90d |
| 43  | num_cb_queries |
| 44  | age_years |
| 45  | years_employed |
| 46  | education_ordinal |
| 47  | is_homeowner_flag |
| 48  | income_verifiable_flag |
| 49  | is_married_flag |
| 50  | employment_status_grouped |
| 51  | occupation_type |
| 52  | income_missing_flag |
| 53  | dti_missing_flag |

## Phân nhóm Feature

### 1\. Thông tin khoản vay

- loan_original_amount
- term
- debt_to_income_ratio
- loan_amount_to_income
- payment_to_income
- current_debt_ratio
- total_debt_to_income

### 2\. Thu nhập và khả năng tài chính

- stated_monthly_income
- log_monthly_income
- occupation_type
- income_verifiable_flag
- income_missing_flag

### 3\. Lịch sử thanh toán

- max_dpd_24m
- max_dpd_12m
- max_dpd_3m
- avg_dpd_24m
- avg_dpd_recent
- avg_payment_12m
- num_payments_24m
- num_incoming_payments_9m

### 4\. Hành vi tín dụng hiện tại

- num_active_credit
- num_installs_dpd10
- num_installs_dpd5
- num_apps_30d

### 5\. Thông tin Credit Bureau

- num_bureau_records
- num_active_credit_bureau
- total_outstanding_debt
- total_overdue_amount
- max_credit_overdue_days
- max_overdue_amount
- max_overdue_instls
- total_prolongations
- has_bad_debt

### 6\. Lịch sử vay trước

- num_previous_loans
- previous_default_rate
- max_prev_app_dpd
- avg_prev_app_dpd

### 7\. Thông tin truy vấn tín dụng

- cb_queries_30d
- cb_queries_90d
- num_cb_queries

### 8\. Thông tin nhân khẩu học

- age_years
- years_employed
- education_ordinal
- is_homeowner_flag
- is_married_flag
- employment_status_grouped

### 9\. Cờ chất lượng dữ liệu

- income_missing_flag
- dti_missing_flag

## Chuyển đổi Silver → Gold

### Đầu vào

| Bảng | Số cột | Số bản ghi |
| --- | --- | --- |
| silver.hc_v2_cleansed | 58  | 1,526,659 |

### Đầu ra

| Bảng | Số cột | Số bản ghi |
| --- | --- | --- |
| gold.hc_features_v2 | 53  | 1,526,659 |

### Các xử lý chính

- Tạo các tỷ lệ tài chính:
    - debt_to_income_ratio
    - loan_amount_to_income
    - payment_to_income
    - current_debt_ratio
    - total_debt_to_income
- Tạo các feature hành vi tín dụng:
    - high_dti_flag
    - has_bad_debt
- Chuẩn hóa dữ liệu nhân khẩu học:
    - education_ordinal
    - employment_status_grouped
    - occupation_type
- Tạo các feature lịch sử tín dụng:
    - previous_default_rate
    - max_prev_app_dpd
    - avg_prev_app_dpd
- Xử lý dữ liệu thiếu:
    - income_missing_flag
    - dti_missing_flag
- Loại bỏ các cột trung gian không cần thiết cho Machine Learning.

## Kết quả cuối cùng

Bảng gold.hc_features_v2 là tập Feature Store cuối cùng được sử dụng trực tiếp cho quá trình huấn luyện mô hình Machine Learning.

| Chỉ tiêu | Giá trị |
| --- | --- |
| Số hồ sơ vay | 1,526,659 |
| Số feature | 53  |
| Biến mục tiêu | 1   |
| Tổng số cột | 53  |
| Tỷ lệ Default | 3.10% |

Đây là lớp dữ liệu cuối cùng trong kiến trúc ETL Bronze → Silver → Gold, sẵn sàng phục vụ huấn luyện, đánh giá và triển khai mô hình dự báo rủi ro tín dụng.