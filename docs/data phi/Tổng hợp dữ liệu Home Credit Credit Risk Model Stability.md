# Tổng hợp dữ liệu Home Credit Credit Risk Model Stability

## 1\. Lớp Bronze (Raw Data)

Dữ liệu Bronze được nạp trực tiếp từ nguồn Parquet vào hệ quản trị cơ sở dữ liệu mà không thay đổi cấu trúc dữ liệu.

| Bảng | Số cột | Số bản ghi |
| --- | --- | --- |
| train_base | 5   | 1,526,659 |
| train_static_0 | 168 | 1,526,659 |
| train_static_cb_0 | 53  | 1,500,476 |
| train_person_1 | 37  | 2,973,991 |
| train_applprev_1 | 41  | 6,525,979 |
| train_credit_bureau_a_1 | 79  | 15,940,537 |

### Tổng số bảng

- 6 bảng nguồn
- Tổng cộng 383 cột
- Hơn 30 triệu bản ghi

## 2\. Lớp Silver (hc_v2_cleansed)

### Thông tin tổng quan

| Thuộc tính | Giá trị |
| --- | --- |
| Tên bảng | hc_v2_cleansed |
| Schema | silver |
| Số cột | 58  |
| Số bản ghi | 1,526,659 |
| Khóa chính | listing_key |
| Biến mục tiêu | is_default |
| Tỷ lệ Default | 3.10% |
| Tỷ lệ NULL Income | 33.50% |
| Tỷ lệ NULL Age | 0.00% |

### Các cột trong Silver

| STT | Tên cột |
| --- | --- |
| 1   | listing_key |
| 2   | member_key |
| 3   | is_default |
| 4   | date_decision |
| 5   | WEEK_NUM |
| 6   | loan_original_amount |
| 7   | annuity |
| 8   | stated_monthly_income |
| 9   | current_debt |
| 10  | total_debt |
| 11  | term |
| 12  | monthly_income |
| 13  | debt_to_income_ratio |
| 14  | max_dpd_24m |
| 15  | max_dpd_12m |
| 16  | max_dpd_3m |
| 17  | avg_dpd_24m |
| 18  | avg_dpd_3m |
| 19  | num_active_credits |
| 20  | num_installs_dpd10 |
| 21  | num_installs_dpd5 |
| 22  | avg_payment_12m |
| 23  | num_payments_24m |
| 24  | num_incoming_payments_9m |
| 25  | num_apps_30d |
| 26  | birth_date |
| 27  | age_years |
| 28  | education_level |
| 29  | occupation_income |
| 30  | income_type |
| 31  | employment_length |
| 32  | family_state |
| 33  | gender |
| 34  | house_type |
| 35  | employment_status |
| 36  | income_verifiable |
| 37  | is_homeowner |
| 38  | is_married |
| 39  | num_bureau_records |
| 40  | num_active_credit_bureau |
| 41  | total_outstanding_debt |
| 42  | total_overdue_amount |
| 43  | max_dpd_bureau_active |
| 44  | max_dpd_bureau_closed |
| 45  | max_overdue_amount |
| 46  | max_overdue_instls |
| 47  | total_prolongations |
| 48  | num_previous_apps |
| 49  | num_previous_loans |
| 50  | num_prev_rejected |
| 51  | previous_default_rate |
| 52  | max_prev_app_dpd |
| 53  | avg_prev_app_dpd |
| 54  | cb_queries_30d |
| 55  | cb_queries_90d |
| 56  | cb_queries_180d |
| 57  | num_cb_queries |
| 58  | cb_rejections_3y |

## 3\. Chuyển đổi Bronze → Silver

### Nguồn dữ liệu sử dụng

| Bảng Bronze | Vai trò |
| --- | --- |
| train_base | Bảng trung tâm chứa target |
| train_static_0 | Thông tin tín dụng và lịch sử thanh toán |
| train_static_cb_0 | Thông tin truy vấn Credit Bureau |
| train_person_1 | Thông tin nhân khẩu học khách hàng |
| train_applprev_1 | Lịch sử khoản vay trước |
| train_credit_bureau_a_1 | Lịch sử tín dụng từ Credit Bureau |

### Các xử lý chính

- Chuẩn hóa tên cột sang tiếng Anh có ý nghĩa nghiệp vụ.
- Gộp dữ liệu từ 6 bảng nguồn về 1 bảng phân tích.
- Tổng hợp các chỉ số lịch sử tín dụng theo khách hàng.
- Tổng hợp lịch sử khoản vay trước.
- Tính toán các chỉ số tài chính:
    - debt_to_income_ratio
    - previous_default_rate
    - total_outstanding_debt
    - total_overdue_amount
- Chuẩn hóa các biến nhân khẩu học.
- Loại bỏ cấu trúc dữ liệu phân mảnh và mã hóa khó hiểu của bộ dữ liệu gốc.

### Kết quả

| Chỉ tiêu | Bronze | Silver |
| --- | --- | --- |
| Số bảng | 6   | 1   |
| Tổng số cột | 383 | 58  |
| Số bản ghi chính | 1,526,659 | 1,526,659 |
| Mức độ dễ hiểu | Thấp | Cao |
| Sẵn sàng cho ML | Chưa | Có  |

Silver trở thành bảng dữ liệu phân tích thống nhất, sẵn sàng cho các bước Feature Engineering và xây dựng mô hình dự báo rủi ro tín dụng ở lớp Gold.