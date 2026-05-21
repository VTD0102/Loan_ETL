# So sánh và Chi tiết Đặc trưng (Features) của các Mô hình Rủi ro Tín dụng

Tài liệu này trình bày chi tiết các đặc trưng được sử dụng trong hai mô hình `customer_risk_model` (LightGBM) và `scorecard_model` (Logistic Regression). Hầu hết các đặc trưng được trích xuất từ bảng `gold.hc_features_v2`.

Bảng dưới đây phân định rõ mô hình nào sử dụng đặc trưng nào (với bí danh - alias nếu có), **nguồn thu thập** và **khuyến nghị định dạng/đơn vị đầu vào** để mô hình đạt độ chính xác cao nhất trong quá trình inference.

**Chú thích cột Nguồn thu thập:**

| Ký hiệu | Ý nghĩa |
| :--- | :--- |
| Form | Người dùng nhập trực tiếp trên form đăng ký, **không** bị CIC ghi đè |
| Form → CIC override | User nhập default trên form, nhưng nếu CCCD khớp record CIC thì `apply_cic_to_payload` ghi đè giá trị từ CIC (`backend/services/cic_service.py:63-86`). Audit gốc giữ ở field `self_*`. |
| Backend từ CIC | Không qua form; backend set thẳng từ `cic_record.*` trước khi gọi ML (vd `cic_monthly_installment`) |
| Tự tính | `build_model_input` tính từ các field khác tại inference (`backend/services/model_feature_builder.py:91-126`) |
| DB nội bộ | Truy vấn từ bảng `loan_applications` của user (history) |
| Imputed (artifact) | Không có trong payload và không tự tính được ⇒ rơi xuống `feature_defaults` trong `customer_risk_model.pkl`. CIC mock hiện tại **không** expose các field này. |

**Tóm tắt phân loại 35 feature của LightGBM v4:**

- **Form-only (10)** — user phải nhập: `monthly_income`, `loan_amount`, `term`, `employment_status`, `occupation_type`, `years_employed`, `age_years`, `education_ordinal`, `is_homeowner`, `is_married_flag`, `income_verifiable_flag` (default `True` nếu thiếu).
- **Form → CIC override (5)** — user khai default, CIC ghi đè khi có CCCD: `num_bureau_records`, `num_active_credit` (cũng dùng làm alias `num_active_credit_bureau`), `total_overdue_amount`, `max_credit_overdue_days`, `has_bad_debt`.
- **Backend từ CIC (1, không vào feature_cols)** — `cic_monthly_installment` (lấy từ `cic_record.total_monthly_installment`), chỉ dùng để tính `dti`.
- **Tự tính (10)** — `dti`, `loan_amount_to_income`, `log_monthly_income`, `high_dti_flag`, `payment_to_income` (= `dti`), `current_debt_ratio` (= `total_overdue_amount / loan_amount`), `total_debt_to_income` (= `total_overdue_amount / (income×12)`), `max_overdue_amount` (alias = `total_overdue_amount`), `income_missing_flag`, `dti_missing_flag`.
- **DB nội bộ (2)** — `num_previous_loans`, `previous_default_rate` (từ lịch sử đơn vay; `_history_features` trong `model_feature_builder.py:210-230`).
- **Imputed từ artifact (5)** — `avg_dpd_recent`, `num_installs_dpd10`, `total_prolongations`, `cb_queries_30d`, `num_cb_queries`. CIC mock không cung cấp các tỷ lệ DPD chi tiết / count truy vấn này, nên 100% đơn dùng giá trị median train. Đây là điểm cần lưu ý khi đánh giá model — 5 feature này không mang thông tin thực tế ở production.
- **Demographics khác cũng Form**: thêm `listing_category` (input nhưng không vào model v4).

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
| `debt_to_income_ratio` | Tỷ lệ nợ trên thu nhập (DTI, **combined**) | **Tự tính** `(loan_amount/term + cic_monthly_installment) / monthly_income` — xem `compute_combined_dti` trong `backend/services/model_feature_builder.py`. Nếu user không khai nợ CIC → `cic_monthly_installment=0`, rút về `(loan_amount/term)/income`. | `dti` | `debt_to_income_ratio` | **Số thực (Float 0-1)** - VD: `0.35` thay vì `35%`. Giữ độ chính xác thập phân. |
| `loan_amount_to_income` | Quy mô khoản vay / Thu nhập | **Tự tính** `loan_amount/(income×12)` | `loan_amount_to_income` | `loan_amount_to_income` | **Số thực (Float)** - VD: `12.5`. |
| `log_monthly_income` | Logarit tự nhiên của thu nhập | **Tự tính** `ln(1 + income)` | `log_monthly_income` | `log_monthly_income` | **Số thực (Float)** - Tính bằng `ln(1+income)` với income ở HC unit. VD: `10.60` (income=40000, median train). |
| `payment_to_income` | DTI khoản vay hiện tại | **Tự tính** (trùng DTI, đã loại v4) | `payment_to_income` | `payment_to_income` | **Số thực (Float 0-1)** - VD: `0.15`. |
| `high_dti_flag` | Cờ DTI rủi ro cao | **Tự tính** `1` nếu DTI > `dti_p75` (~0.149 theo artifact v4) | `high_dti_flag` | `high_dti_flag` | **Số nguyên (0 hoặc 1)** |
| `current_debt_ratio` | Dư nợ / khoản vay đề xuất | **Tự tính** `total_overdue_amount / loan_amount` (tử số từ CIC override) | `current_debt_ratio` | `current_debt_ratio` | **Số thực (Float ≥0)** - VD: `0.04`. |
| `total_debt_to_income` | Tổng nợ quá hạn / Thu nhập năm | **Tự tính** `total_overdue_amount / (monthly_income × 12)` (tử số từ CIC override) | `total_debt_to_income` | `total_debt_to_income` | **Số thực (Float)** - VD: `0.0`. |

## 2. Hành vi Trễ hạn & Lịch sử Tín dụng (DPD & Bureau)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `max_dpd_24m` | Số ngày chậm trả lớn nhất (24 tháng) | **Tự tính** alias = `max_credit_overdue_days` (tới từ CIC `max_dpd_12m`) | `max_dpd_24m` | `max_dpd_24m` | **Số nguyên (Ngày)** - VD: `45`. |
| `avg_dpd_recent` | Số ngày chậm trả trung bình | **Imputed (artifact)** — CIC mock không tính | `avg_dpd_recent` | `avg_dpd_recent` | **Số thực (Float)** - Lấy median train. |
| `num_installs_dpd10` | Số lần thanh toán trễ > 10 ngày | **Imputed (artifact)** — CIC mock không tính | `num_installs_dpd10` | `num_installs_dpd10` | **Số nguyên (Lần)** - Lấy median train. |
| `num_bureau_records` | Tổng số hồ sơ tín dụng (= `len(cic.loan_history)`) | **Form → CIC override** | `num_bureau_records` | `num_bureau_records` | **Số nguyên (Hồ sơ)** - VD: `5`. |
| `num_active_credit` | Số khoản vay đang hoạt động (= `cic.total_active_loans`) | **Form → CIC override** | `num_active_credit` & `num_active_credit_bureau` (alias) | `num_active_credit` | **Số nguyên (Khoản)** - VD: `2`. *(LightGBM nhân đôi cột này với alias thứ hai)*. |
| `total_overdue_amount` | Tổng số tiền đang quá hạn (= `cic.total_overdue_amount`) | **Form → CIC override** | `total_overdue_amount` | `total_overdue_amount` | **Số thực (HC unit, magnitude ≈ USD)** - VD: `1500`. ⚠️ Không phải VND. |
| `max_credit_overdue_days` | Số ngày trễ lớn nhất (= `cic.max_dpd_12m`) | **Form → CIC override** | `max_credit_overdue_days` | `max_credit_overdue_days` | **Số nguyên (Ngày)** - VD: `90`. |
| `has_bad_debt` | Đã từng có nợ xấu nhóm 3+ (= `cic.bad_debt_flag`) | **Form → CIC override** | `has_bad_debt` | `has_bad_debt` | **Số nguyên (0 hoặc 1)** |
| `total_prolongations` | Tổng số lần xin gia hạn nợ | **Imputed (artifact)** — CIC mock không tính | `total_prolongations` | `total_prolongations` | **Số nguyên (Lần)** - Lấy median train. |
| `max_overdue_amount` | Số tiền quá hạn cao nhất | **Tự tính** alias = `total_overdue_amount` (CIC override) | `max_overdue_amount` | ❌ | **Số thực (HC unit, magnitude ≈ USD)** - VD: `5000`. ⚠️ Không phải VND. |

## 3. Hành vi Nội bộ & Truy vấn CIC (Previous Apps & CB Queries)

| Tên Đặc trưng (Gốc) | Ý nghĩa | Nguồn thu thập | LightGBM Model | LR Scorecard Model | Định dạng / Đơn vị Đầu vào Tối ưu |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `num_previous_loans` | Số khoản vay đã từng vay nội bộ | **DB nội bộ** (đơn đã duyệt) | `num_previous_loans` | `num_previous_loans` | **Số nguyên (Khoản)** - VD: `4`. |
| `previous_default_rate` | Tỷ lệ vỡ nợ của các khoản vay trước | **DB nội bộ** + Tự tính `rejected/total` | `previous_default_rate` | `previous_default_rate` | **Số thực (Float 0-1)** - VD: `0.25`. |
| `cb_queries_30d` | Số lần tra CIC trong 30 ngày qua | **Imputed (artifact)** — CIC mock không track query count | `cb_queries_30d` | `cb_queries_30d` | **Số nguyên (Lần)** - Lấy median train. |
| `num_cb_queries` | Tổng số lần tra CIC | **Imputed (artifact)** — CIC mock không track query count | `num_cb_queries` | `num_cb_queries` | **Số nguyên (Lần)** - Lấy median train. |

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
