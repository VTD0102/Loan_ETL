# So sánh và Chi tiết Đặc trưng (Features) của các Mô hình Rủi ro Tín dụng

Tài liệu này trình bày chi tiết các đặc trưng được sử dụng trong hai mô hình `customer_risk_model` (LightGBM) và `scorecard_model` (Logistic Regression). Hầu hết các đặc trưng được trích xuất từ bảng `gold.hc_features_v2`. 

Bảng dưới đây phân định rõ mô hình nào sử dụng đặc trưng nào (với bí danh - alias nếu có) và **khuyến nghị định dạng/đơn vị đầu vào (Input Unit)** để mô hình đạt độ chính xác cao nhất trong quá trình inference (dự đoán thực tế).

---

## 1. Thu nhập, Khoản vay & Gánh nặng Nợ (Income, Loan & Debt)

| Tên Đặc trưng (Gốc) | Ý nghĩa | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :---: | :---: | :--- |
| `stated_monthly_income` | Thu nhập hàng tháng | `monthly_income` | ❌ | **Số nguyên (VND)** - VD: `15000000`. Không chia tỷ lệ (triệu/nghìn). |
| `loan_original_amount` | Số tiền gốc khoản vay | `loan_amount` | ❌ | **Số nguyên (VND)** - VD: `50000000`. Không chia tỷ lệ. |
| `term` | Kỳ hạn vay | `term` | ❌ | **Số nguyên (Tháng)** - VD: `12`, `24`. |
| `debt_to_income_ratio` | Tỷ lệ nợ trên thu nhập (DTI) | `dti` | `debt_to_income_ratio` | **Số thực (Float 0-1)** - VD: `0.35` thay vì `35%`. Giữ độ chính xác thập phân. |
| `loan_amount_to_income`| Quy mô khoản vay / Thu nhập | `loan_amount_to_income` | `loan_amount_to_income` | **Số thực (Float)** - VD: `12.5`. |
| `log_monthly_income` | Logarit tự nhiên của thu nhập | `log_monthly_income` | `log_monthly_income` | **Số thực (Float)** - Tính bằng `ln(income)`, giữ nguyên phần thập phân. VD: `16.523`. |
| `payment_to_income` | DTI khoản vay hiện tại | `payment_to_income` | `payment_to_income` | **Số thực (Float 0-1)** - VD: `0.15`. |
| `high_dti_flag` | Cờ DTI rủi ro cao | `high_dti_flag` | `high_dti_flag` | **Số nguyên (0 hoặc 1)** |
| `current_debt_ratio` | Dư nợ / Tổng hạn mức | `current_debt_ratio` | `current_debt_ratio` | **Số thực (Float 0-1)** - VD: `0.85`. |
| `total_debt_to_income` | Tổng dư nợ / Thu nhập | `total_debt_to_income` | `total_debt_to_income` | **Số thực (Float)** - VD: `5.2`. |

## 2. Hành vi Trễ hạn & Lịch sử Tín dụng (DPD & Bureau)

| Tên Đặc trưng (Gốc) | Ý nghĩa | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :---: | :---: | :--- |
| `max_dpd_24m` | Số ngày chậm trả lớn nhất (24 tháng)| `max_dpd_24m` | `max_dpd_24m` | **Số nguyên (Ngày)** - VD: `45`. |
| `avg_dpd_recent` | Số ngày chậm trả trung bình | `avg_dpd_recent` | `avg_dpd_recent` | **Số thực (Float)** - Giữ phần thập phân để phân biệt chi tiết (VD: `12.5`). |
| `num_installs_dpd10` | Số lần thanh toán trễ > 10 ngày | `num_installs_dpd10`| `num_installs_dpd10` | **Số nguyên (Lần)** - VD: `3`. |
| `num_bureau_records` | Tổng số hồ sơ tín dụng | `num_bureau_records` | `num_bureau_records` | **Số nguyên (Hồ sơ)** - VD: `5`. |
| `num_active_credit` | Số khoản vay đang hoạt động | `num_active_credit` & `num_active_credit_bureau` | `num_active_credit` | **Số nguyên (Khoản)** - VD: `2`. *(Lưu ý: LightGBM nhân đôi cột này với alias thứ hai)*. |
| `total_overdue_amount` | Tổng số tiền đang quá hạn | `total_overdue_amount`| `total_overdue_amount` | **Số nguyên (VND)** - VD: `1500000`. |
| `max_credit_overdue_days`| Số ngày trễ lớn nhất tại CIC | `max_credit_overdue_days`| `max_credit_overdue_days` | **Số nguyên (Ngày)** - VD: `90`. |
| `has_bad_debt` | Đã từng có nợ xấu (nhóm 3+) | `has_bad_debt` | `has_bad_debt` | **Số nguyên (0 hoặc 1)** |
| `total_prolongations` | Tổng số lần xin gia hạn nợ | `total_prolongations`| `total_prolongations` | **Số nguyên (Lần)** - VD: `1`. |
| `max_overdue_amount` | Số tiền quá hạn cao nhất lịch sử | `max_overdue_amount` | ❌ | **Số nguyên (VND)** - VD: `5000000`. |

## 3. Hành vi Nội bộ & Truy vấn CIC (Previous Apps & CB Queries)

| Tên Đặc trưng (Gốc) | Ý nghĩa | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :---: | :---: | :--- |
| `num_previous_loans` | Số khoản vay đã từng vay nội bộ | `num_previous_loans` | `num_previous_loans` | **Số nguyên (Khoản)** - VD: `4`. |
| `previous_default_rate` | Tỷ lệ vỡ nợ của các khoản vay trước | `previous_default_rate`| `previous_default_rate`| **Số thực (Float 0-1)** - VD: `0.25`. |
| `cb_queries_30d` | Số lần tra CIC trong 30 ngày qua | `cb_queries_30d` | `cb_queries_30d` | **Số nguyên (Lần)** - VD: `2`. |
| `num_cb_queries` | Tổng số lần tra CIC | `num_cb_queries` | `num_cb_queries` | **Số nguyên (Lần)** - VD: `10`. |

## 4. Thông tin Nhân khẩu học, Nghề nghiệp & Xã hội (Demographics & Employment)

| Tên Đặc trưng (Gốc) | Ý nghĩa | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :---: | :---: | :--- |
| `age_years` | Độ tuổi | `age_years` | `age_years` | **Số thực (Float)** - Ưu tiên giữ phần thập phân (số năm + số tháng) thay vì làm tròn để mô hình phân nhánh chính xác. VD: `28.5`. |
| `years_employed` | Thâm niên làm việc | `years_employed` | `years_employed` | **Số thực (Float)** - Giữ thập phân (đại diện cho tháng). VD: `2.5` (tương đương 30 tháng). |
| `education_ordinal` | Cấp bậc học vấn (Đã mã hóa) | `education_ordinal` | `education_ordinal` | **Số nguyên (1, 2, 3...)** - Các mức rank có thứ tự từ thấp đến cao. |
| `is_homeowner_flag` | Sở hữu nhà/đất | `is_homeowner` | `is_homeowner_flag` | **Số nguyên (0 hoặc 1)** |
| `income_verifiable_flag`| Thu nhập có thể kiểm chứng | `income_verifiable_flag`| `income_verifiable_flag`| **Số nguyên (0 hoặc 1)** |
| `is_married_flag` | Đã kết hôn | `is_married_flag` | `is_married_flag` | **Số nguyên (0 hoặc 1)** |
| `employment_status_grouped`| Nhóm nghề nghiệp | `employment_status` | `employment_status_grouped`| **Chuỗi (String)** - Khớp chính xác tệp (VD: `"Employed"`, `"Self-employed"`, `"Retired"`, `"Not employed"`, `"Other/Unknown"`). |
| `occupation_type` | Loại công việc | `occupation_type` | `occupation_type` | **Chuỗi (String)** - Khớp chính xác (VD: `"PRIVATE_SECTOR_EMPLOYEE"`, `"SALARIED_GOVT"`, `"OTHER"`). |

## 5. Cờ Đánh dấu Khuyết dữ liệu (Missing Indicators)

| Tên Đặc trưng (Gốc) | Ý nghĩa | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :---: | :---: | :--- |
| `income_missing_flag` | Dữ liệu thu nhập bị thiếu/trống | `income_missing_flag`| `income_missing_flag`| **Số nguyên (0 hoặc 1)** |
| `dti_missing_flag` | Dữ liệu DTI bị thiếu/trống | `dti_missing_flag` | `dti_missing_flag` | **Số nguyên (0 hoặc 1)** |
