# So sánh và Chi tiết Đặc trưng (Features) của các Mô hình Rủi ro Tín dụng

Tài liệu này trình bày chi tiết các đặc trưng được sử dụng trong hai mô hình `customer_risk_model` (LightGBM) và `scorecard_model` (Logistic Regression). Hầu hết các đặc trưng được trích xuất từ bảng `gold.hc_features_v2`.

Bảng dưới đây phân định rõ mô hình nào sử dụng đặc trưng nào (với bí danh - alias nếu có), **nguồn thu thập** và **khuyến nghị định dạng/đơn vị đầu vào** để mô hình đạt độ chính xác cao nhất trong quá trình inference.

**Chú thích cột Nguồn thu thập:**

| Ký hiệu | Ý nghĩa |
| :--- | :--- |
| Form | Người dùng nhập trực tiếp trên form đăng ký |
| Tự tính | Được tính toán từ các feature khác tại inference |
| DB nội bộ | Truy vấn từ bảng lịch sử đơn vay trong hệ thống |
| CIC / Bureau | Dữ liệu từ trung tâm thông tin tín dụng (bên ngoài) |

> ⚠️ **Đơn vị tiền tệ — KHÔNG phải VND.**
> Model `customer_risk_model` (LightGBM v4) được huấn luyện trên dataset *Home Credit Credit Risk Model Stability* (Đông Âu). Toàn bộ trường tiền (`monthly_income`, `loan_amount`, `total_overdue_amount`, `max_overdue_amount`) ở **đơn vị tiền gốc của tập train (HC unit, magnitude ≈ USD/EUR)**, không phải VND.
> Bằng chứng từ `customer_risk_model.pkl` — median train (`feature_defaults`):
> - `monthly_income` ≈ **40,000**
> - `loan_amount` ≈ **35,199**
> - `log_monthly_income` ≈ **10.60** (= ln(40,001))
> - `dti_p75` ≈ **0.149** (ratio, không phải tiền)
>
> Nếu form FE nhập VND raw (ví dụ 15,000,000) và gửi thẳng vào model, `log_monthly_income` sẽ ≈ 16.5 — lệch ~6σ so với phân phối train → prediction không đáng tin. Khi triển khai cho UX VND, **phải convert VND → HC unit trước khi gọi `build_model_input`** (xem `backend/services/model_feature_builder.py`).

---

## 1. Thu nhập, Khoản vay & Gánh nặng Nợ (Income, Loan & Debt)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `stated_monthly_income` | Thu nhập hàng tháng | **Form** | `monthly_income` | ❌ | **Số thực (HC unit, magnitude ≈ USD)** - VD: `40000` (median train). Không chia tỷ lệ. ⚠️ Không phải VND. |
| `loan_original_amount` | Số tiền gốc khoản vay | **Form** | `loan_amount` | ❌ | **Số thực (HC unit, magnitude ≈ USD)** - VD: `35199` (median train). Không chia tỷ lệ. ⚠️ Không phải VND. |
| `term` | Kỳ hạn vay | **Form** | `term` | ❌ | **Số nguyên (Tháng)** - VD: `12`, `24`. |
| `debt_to_income_ratio` | Tỷ lệ nợ trên thu nhập (DTI) | **Tự tính** `(loan_amount/term)/income` | `dti` | `debt_to_income_ratio` | **Số thực (Float 0-1)** - VD: `0.35` thay vì `35%`. Giữ độ chính xác thập phân. |
| `loan_amount_to_income` | Quy mô khoản vay / Thu nhập | **Tự tính** `loan_amount/(income×12)` | `loan_amount_to_income` | `loan_amount_to_income` | **Số thực (Float)** - VD: `12.5`. |
| `log_monthly_income` | Logarit tự nhiên của thu nhập | **Tự tính** `ln(1 + income)` | `log_monthly_income` | `log_monthly_income` | **Số thực (Float)** - Tính bằng `ln(1+income)` với income ở HC unit. VD: `10.60` (income=40000, median train). |
| `payment_to_income` | DTI khoản vay hiện tại | **Tự tính** (trùng DTI, đã loại v4) | `payment_to_income` | `payment_to_income` | **Số thực (Float 0-1)** - VD: `0.15`. |
| `high_dti_flag` | Cờ DTI rủi ro cao | **Tự tính** `1` nếu DTI > `dti_p75` (~0.149 theo artifact v4) | `high_dti_flag` | `high_dti_flag` | **Số nguyên (0 hoặc 1)** |
| `current_debt_ratio` | Dư nợ / Tổng hạn mức | **CIC / Bureau** | `current_debt_ratio` | `current_debt_ratio` | **Số thực (Float 0-1)** - VD: `0.85`. |
| `total_debt_to_income` | Tổng dư nợ / Thu nhập | **CIC / Bureau** + Tự tính | `total_debt_to_income` | `total_debt_to_income` | **Số thực (Float)** - VD: `5.2`. |

## 2. Hành vi Trễ hạn & Lịch sử Tín dụng (DPD & Bureau)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `max_dpd_24m` | Số ngày chậm trả lớn nhất (24 tháng) | **CIC / Bureau** | `max_dpd_24m` | `max_dpd_24m` | **Số nguyên (Ngày)** - VD: `45`. |
| `avg_dpd_recent` | Số ngày chậm trả trung bình | **CIC / Bureau** | `avg_dpd_recent` | `avg_dpd_recent` | **Số thực (Float)** - Giữ phần thập phân để phân biệt chi tiết (VD: `12.5`). |
| `num_installs_dpd10` | Số lần thanh toán trễ > 10 ngày | **CIC / Bureau** | `num_installs_dpd10` | `num_installs_dpd10` | **Số nguyên (Lần)** - VD: `3`. |
| `num_bureau_records` | Tổng số hồ sơ tín dụng | **Form** (người dùng tự khai) | `num_bureau_records` | `num_bureau_records` | **Số nguyên (Hồ sơ)** - VD: `5`. |
| `num_active_credit` | Số khoản vay đang hoạt động | **Form** (người dùng tự khai) | `num_active_credit` & `num_active_credit_bureau` | `num_active_credit` | **Số nguyên (Khoản)** - VD: `2`. *(Lưu ý: LightGBM nhân đôi cột này với alias thứ hai)*. |
| `total_overdue_amount` | Tổng số tiền đang quá hạn | **Form** (người dùng tự khai) | `total_overdue_amount` | `total_overdue_amount` | **Số thực (HC unit, magnitude ≈ USD)** - VD: `1500`. ⚠️ Không phải VND. |
| `max_credit_overdue_days` | Số ngày trễ lớn nhất tại CIC | **Form** (người dùng tự khai) | `max_credit_overdue_days` | `max_credit_overdue_days` | **Số nguyên (Ngày)** - VD: `90`. |
| `has_bad_debt` | Đã từng có nợ xấu (nhóm 3+) | **Form** (người dùng tự khai, đã loại v4) | `has_bad_debt` | `has_bad_debt` | **Số nguyên (0 hoặc 1)** |
| `total_prolongations` | Tổng số lần xin gia hạn nợ | **CIC / Bureau** | `total_prolongations` | `total_prolongations` | **Số nguyên (Lần)** - VD: `1`. |
| `max_overdue_amount` | Số tiền quá hạn cao nhất lịch sử | **CIC / Bureau** | `max_overdue_amount` | ❌ | **Số thực (HC unit, magnitude ≈ USD)** - VD: `5000`. ⚠️ Không phải VND. |

## 3. Hành vi Nội bộ & Truy vấn CIC (Previous Apps & CB Queries)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `num_previous_loans` | Số khoản vay đã từng vay nội bộ | **DB nội bộ** (đơn đã duyệt) | `num_previous_loans` | `num_previous_loans` | **Số nguyên (Khoản)** - VD: `4`. |
| `previous_default_rate` | Tỷ lệ vỡ nợ của các khoản vay trước | **DB nội bộ** + Tự tính `rejected/total` | `previous_default_rate` | `previous_default_rate` | **Số thực (Float 0-1)** - VD: `0.25`. |
| `cb_queries_30d` | Số lần tra CIC trong 30 ngày qua | **CIC / Bureau** | `cb_queries_30d` | `cb_queries_30d` | **Số nguyên (Lần)** - VD: `2`. |
| `num_cb_queries` | Tổng số lần tra CIC | **CIC / Bureau** | `num_cb_queries` | `num_cb_queries` | **Số nguyên (Lần)** - VD: `10`. |

## 4. Thông tin Nhân khẩu học, Nghề nghiệp & Xã hội (Demographics & Employment)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `age_years` | Độ tuổi | **Form** | `age_years` | `age_years` | **Số thực (Float)** - Ưu tiên giữ phần thập phân (số năm + số tháng) thay vì làm tròn để mô hình phân nhánh chính xác. VD: `28.5`. |
| `years_employed` | Thâm niên làm việc | **Form** | `years_employed` | `years_employed` | **Số thực (Float)** - Giữ thập phân (đại diện cho tháng). VD: `2.5` (tương đương 30 tháng). |
| `education_ordinal` | Cấp bậc học vấn (Đã mã hóa) | **Form** | `education_ordinal` | `education_ordinal` | **Số nguyên (1, 2, 3...)** - Các mức rank có thứ tự từ thấp đến cao. |
| `is_homeowner_flag` | Sở hữu nhà/đất | **Form** | `is_homeowner` | `is_homeowner_flag` | **Số nguyên (0 hoặc 1)** |
| `income_verifiable_flag` | Thu nhập có thể kiểm chứng | **Form** | `income_verifiable_flag` | `income_verifiable_flag` | **Số nguyên (0 hoặc 1)** |
| `is_married_flag` | Đã kết hôn | **Form** | `is_married_flag` | `is_married_flag` | **Số nguyên (0 hoặc 1)** |
| `employment_status_grouped` | Nhóm nghề nghiệp | **Form** | `employment_status` | `employment_status_grouped` | **Chuỗi (String)** - Khớp chính xác tệp (VD: `"Employed"`, `"Self-employed"`, `"Retired"`, `"Not employed"`, `"Other/Unknown"`). |
| `occupation_type` | Loại công việc | **Form** | `occupation_type` | `occupation_type` | **Chuỗi (String)** - Khớp chính xác (VD: `"PRIVATE_SECTOR_EMPLOYEE"`, `"SALARIED_GOVT"`, `"OTHER"`). |

## 5. Cờ Đánh dấu Khuyết dữ liệu (Missing Indicators)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `income_missing_flag` | Dữ liệu thu nhập bị thiếu/trống | **Tự tính** (1 nếu income = null) | `income_missing_flag` | `income_missing_flag` | **Số nguyên (0 hoặc 1)** |
| `dti_missing_flag` | Dữ liệu DTI bị thiếu/trống | **Tự tính** (1 nếu DTI = null) | `dti_missing_flag` | `dti_missing_flag` | **Số nguyên (0 hoặc 1)** |
