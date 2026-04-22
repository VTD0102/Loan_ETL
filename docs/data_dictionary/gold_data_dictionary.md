# Gold Schema Data Dictionary

Tài liệu này mô tả ý nghĩa các thuộc tính trong lớp `gold` của hệ thống.

Lớp Gold là lớp dữ liệu phục vụ:
- Machine Learning
- risk scoring
- dashboard
- phân tích nghiệp vụ

Gold hiện gồm:
- 1 bảng feature chính: `gold.loan_features_v1`
- nhiều view phân tích phục vụ dashboard

---

# 1. Vai trò của Gold

Gold được xây từ:
- `core.loans`
- `core.borrowers`
- `core.credit_profiles`
- các bảng dimension trong `core`
- `silver.prosper_loans_cleansed` để lấy `is_default`

Mục tiêu của Gold là:
- gom dữ liệu từ nhiều bảng về đúng grain phân tích
- tạo feature engineering
- loại bỏ leakage
- tạo analytical views cho dashboard

---

# 2. Bảng `gold.loan_features_v1`

## Grain
**1 dòng = 1 khoản vay = 1 `listing_key`**

## Vai trò
Đây là bảng feature chính dùng cho:
- train model
- predict
- scoring
- phân tích rủi ro

---

# 3. Data Dictionary chi tiết của `gold.loan_features_v1`

---

## 3.1. Nhóm khóa và target

| Thuộc tính | Ý nghĩa |
|---|---|
| `listing_key` | Khóa chính của khoản vay trong Gold |
| `member_key` | Mã người vay |
| `loan_number` | Mã khoản vay hiển thị |
| `is_default` | Biến mục tiêu của mô hình: 1 = vỡ nợ, 0 = không |

---

## 3.2. Nhóm thuộc tính gốc từ khoản vay

| Thuộc tính | Ý nghĩa |
|---|---|
| `loan_original_amount` | Số tiền vay ban đầu |
| `term` | Thời hạn khoản vay |
| `borrower_apr` | APR của khoản vay |
| `borrower_rate` | Lãi suất danh nghĩa |
| `listing_creation_date` | Ngày tạo listing |
| `loan_origination_date` | Ngày khoản vay chính thức được cấp |

---

## 3.3. Nhóm thuộc tính gốc từ borrower

| Thuộc tính | Ý nghĩa |
|---|---|
| `borrower_state` | Bang / khu vực cư trú |
| `is_homeowner` | Người vay có sở hữu nhà hay không |
| `income_verifiable` | Thu nhập có thể xác minh hay không |

---

## 3.4. Nhóm thuộc tính gốc từ credit profile

| Thuộc tính | Ý nghĩa |
|---|---|
| `credit_score_range_lower` | Cận dưới điểm tín dụng |
| `credit_score_range_upper` | Cận trên điểm tín dụng |
| `debt_to_income_ratio` | Tỷ lệ nợ trên thu nhập |
| `stated_monthly_income` | Thu nhập tháng khai báo |
| `prosper_rating_alpha` | Xếp hạng tín dụng |
| `prosper_score` | Điểm tín dụng nội bộ |

---

## 3.5. Nhóm thuộc tính danh mục đã join

| Thuộc tính | Ý nghĩa |
|---|---|
| `employment_status_name` | Tình trạng việc làm sau khi join từ bảng dimension |
| `occupation_name` | Nghề nghiệp sau khi join từ bảng dimension |
| `income_range_label` | Nhóm thu nhập sau khi join từ bảng dimension |
| `category_name` | Tên mục đích vay sau khi join từ bảng dimension |

---

## 3.6. Nhóm feature engineered từ credit

| Thuộc tính | Ý nghĩa |
|---|---|
| `credit_score_midpoint` | Điểm tín dụng đại diện, tính từ trung bình cận dưới và cận trên |
| `credit_score_band` | Nhóm điểm tín dụng, ví dụ `<600`, `600-639`, `640-679`, `680-719`, `720+` |
| `rating_ordinal` | Biến đổi `prosper_rating_alpha` sang số để mô hình dễ xử lý |

### Mapping `rating_ordinal`

| Rating | Giá trị |
|---|---|
| HR | 1 |
| E | 2 |
| D | 3 |
| C | 4 |
| B | 5 |
| A | 6 |
| AA | 7 |

---

## 3.7. Nhóm feature engineered từ income

| Thuộc tính | Ý nghĩa |
|---|---|
| `annual_income_est` | Thu nhập năm ước tính = `stated_monthly_income * 12` |
| `log_monthly_income` | Log của thu nhập tháng để giảm độ lệch phân phối |
| `income_range_ordinal` | Biến đổi nhóm thu nhập sang thứ tự số |

---

## 3.8. Nhóm feature engineered từ gánh nặng tài chính

| Thuộc tính | Ý nghĩa |
|---|---|
| `loan_amount_to_income` | Tỷ lệ số tiền vay trên thu nhập năm |
| `rate_apr_spread` | Chênh lệch giữa APR và borrower rate |
| `high_dti_flag` | Cờ cảnh báo nếu DTI cao |

---

## 3.9. Nhóm feature thời gian

| Thuộc tính | Ý nghĩa |
|---|---|
| `origination_year` | Năm phát sinh khoản vay |
| `origination_month` | Tháng phát sinh khoản vay |
| `origination_quarter` | Quý phát sinh khoản vay |
| `listing_year` | Năm tạo listing |
| `listing_month` | Tháng tạo listing |
| `listing_quarter` | Quý tạo listing |
| `post_2009_flag` | Cờ cho biết khoản vay phát sinh sau 2009 hay không |

---

## 3.10. Nhóm feature term

| Thuộc tính | Ý nghĩa |
|---|---|
| `term_12_flag` | Cờ cho khoản vay 12 tháng |
| `term_36_flag` | Cờ cho khoản vay 36 tháng |
| `term_60_flag` | Cờ cho khoản vay 60 tháng |

---

## 3.11. Nhóm feature boolean

| Thuộc tính | Ý nghĩa |
|---|---|
| `is_homeowner_flag` | Chuyển `is_homeowner` sang 0/1 |
| `income_verifiable_flag` | Chuyển `income_verifiable` sang 0/1 |

---

## 3.12. Nhóm feature categorical đã nhóm lại

| Thuộc tính | Ý nghĩa |
|---|---|
| `employment_status_grouped` | Nhóm lại trạng thái việc làm thành các nhóm tổng quát hơn |
| `occupation_cleaned` | Nghề nghiệp đã chuẩn hóa để dễ phân tích |

---

## 3.13. Nhóm missing flags

| Thuộc tính | Ý nghĩa |
|---|---|
| `prosper_score_missing_flag` | Cờ cho biết `prosper_score` có bị thiếu hay không |
| `rating_missing_flag` | Cờ cho biết `prosper_rating_alpha` có bị thiếu hay không |
| `income_missing_flag` | Cờ cho biết `stated_monthly_income` có bị thiếu hay không |
| `dti_missing_flag` | Cờ cho biết `debt_to_income_ratio` có bị thiếu hay không |
| `credit_score_missing_flag` | Cờ cho biết khoảng điểm tín dụng có bị thiếu hay không |

---

# 4. Các analytical views trong Gold

Ngoài bảng `loan_features_v1`, Gold còn có các view phục vụ dashboard.

---

## 4.1. `gold.vw_default_rate_by_term`

**Vai trò:**  
Tổng hợp tỷ lệ default theo thời hạn khoản vay.

| Cột | Ý nghĩa |
|---|---|
| `term` | Thời hạn khoản vay |
| `total_loans` | Tổng số khoản vay |
| `default_loans` | Số khoản vay default |
| `default_rate_pct` | Tỷ lệ default theo phần trăm |

---

## 4.2. `gold.vw_default_rate_by_income`

**Vai trò:**  
Tổng hợp tỷ lệ default theo nhóm thu nhập.

| Cột | Ý nghĩa |
|---|---|
| `income_range_label` | Nhóm thu nhập |
| `total_loans` | Tổng số khoản vay |
| `default_loans` | Số khoản vay default |
| `default_rate_pct` | Tỷ lệ default theo phần trăm |

---

## 4.3. `gold.vw_risk_by_employment`

**Vai trò:**  
Phân tích rủi ro theo nhóm việc làm.

| Cột | Ý nghĩa |
|---|---|
| `employment_status_grouped` | Nhóm việc làm |
| `total_loans` | Tổng số khoản vay |
| `default_loans` | Số khoản vay default |
| `avg_loan_amount_to_income` | Tỷ lệ vay/thu nhập trung bình |
| `avg_dti` | DTI trung bình |
| `default_rate_pct` | Tỷ lệ default theo phần trăm |

---

## 4.4. `gold.vw_category_summary`

**Vai trò:**  
Tóm tắt theo mục đích vay.

| Cột | Ý nghĩa |
|---|---|
| `category_name` | Tên mục đích vay |
| `total_loans` | Tổng số khoản vay |
| `avg_loan_amount` | Số tiền vay trung bình |
| `avg_borrower_rate` | Lãi suất trung bình |
| `default_loans` | Số khoản vay default |
| `default_rate_pct` | Tỷ lệ default theo phần trăm |

---

## 4.5. `gold.vw_state_summary`

**Vai trò:**  
Tóm tắt theo bang / khu vực cư trú.

| Cột | Ý nghĩa |
|---|---|
| `borrower_state` | Bang / khu vực |
| `total_loans` | Tổng số khoản vay |
| `default_loans` | Số khoản vay default |
| `default_rate_pct` | Tỷ lệ default theo phần trăm |
| `avg_loan_amount` | Số tiền vay trung bình |

---

# 5. Mối quan hệ logic trong Gold

Gold không được chuẩn hóa mạnh như Core, vì mục tiêu của Gold là:
- phân tích
- thống kê
- huấn luyện ML

Do đó:

- `gold.loan_features_v1` là bảng trung tâm
- các view Gold đều được xây từ bảng này

Nói cách khác:

```text
core + silver
   ↓
gold.loan_features_v1
   ↓
gold analytical views