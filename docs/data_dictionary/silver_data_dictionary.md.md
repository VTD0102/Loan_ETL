# 📊 Silver Layer Data Dictionary

Tài liệu này mô tả ý nghĩa các thuộc tính trong bảng `silver.prosper_loans_cleansed`.
Dữ liệu đã được làm sạch, chuẩn hóa và sẵn sàng phục vụ cho Core, Gold và Machine Learning.

---

## 🔑 1. Nhóm Khóa & Định danh

| Thuộc tính    | Ý nghĩa                                                                     |
| ------------- | --------------------------------------------------------------------------- |
| `listing_key` | Khóa chính của bản ghi sau khi loại bỏ trùng lặp                            |
| `member_key`  | Mã định danh người vay, dùng để liên kết nhiều khoản vay của cùng một người |
| `loan_key`    | Mã định danh khoản vay, dùng để join với các bảng khác                      |
| `loan_number` | Mã khoản vay hiển thị cho người dùng hoặc báo cáo                           |

---

## ⏱️ 2. Nhóm Thời gian

| Thuộc tính              | Ý nghĩa                                                       |
| ----------------------- | ------------------------------------------------------------- |
| `listing_creation_date` | Ngày tạo hồ sơ vay ban đầu                                    |
| `loan_origination_date` | Ngày khoản vay chính thức được cấp                            |
| `closed_date`           | Ngày khoản vay kết thúc (⚠️ không dùng cho ML vì gây leakage) |
| `date_credit_pulled`    | Ngày hệ thống lấy thông tin tín dụng của khách hàng           |

---

## 📌 3. Nhóm Trạng thái & Target

| Thuộc tính    | Ý nghĩa                                                 |
| ------------- | ------------------------------------------------------- |
| `loan_status` | Trạng thái khoản vay (Current, Completed, Defaulted...) |
| `is_default`  | Biến mục tiêu: 1 = vỡ nợ, 0 = bình thường               |

---

## 💰 4. Nhóm Lãi suất

| Thuộc tính      | Ý nghĩa                                        |
| --------------- | ---------------------------------------------- |
| `borrower_rate` | Lãi suất thực tế khách hàng phải trả           |
| `borrower_apr`  | Lãi suất bao gồm cả phí, phản ánh chi phí thực |

---

## 📉 5. Nhóm Tín dụng (Credit)

| Thuộc tính                 | Ý nghĩa                                            |
| -------------------------- | -------------------------------------------------- |
| `prosper_rating_alpha`     | Xếp hạng tín dụng (A → HR), phản ánh mức độ rủi ro |
| `prosper_score`            | Điểm tín dụng nội bộ của hệ thống Prosper          |
| `credit_score_range_lower` | Cận dưới của điểm tín dụng (FICO)                  |
| `credit_score_range_upper` | Cận trên của điểm tín dụng (FICO)                  |
| `debt_to_income_ratio`     | Tỷ lệ nợ trên thu nhập, đo khả năng trả nợ         |

---

## 💵 6. Nhóm Thu nhập

| Thuộc tính              | Ý nghĩa                                    |
| ----------------------- | ------------------------------------------ |
| `stated_monthly_income` | Thu nhập hàng tháng do khách hàng khai báo |
| `income_range`          | Nhóm thu nhập (phân loại theo khoảng)      |
| `income_verifiable`     | Thu nhập có được xác minh hay không        |

---

## 🏦 7. Nhóm Khoản vay

| Thuộc tính                 | Ý nghĩa                               |
| -------------------------- | ------------------------------------- |
| `loan_original_amount`     | Số tiền vay ban đầu                   |
| `term`                     | Thời hạn khoản vay (12, 36, 60 tháng) |
| `listing_category_numeric` | Mã số thể hiện mục đích vay           |

---

## 👤 8. Nhóm Nhân khẩu học

| Thuộc tính              | Ý nghĩa                           |
| ----------------------- | --------------------------------- |
| `occupation`            | Nghề nghiệp của người vay         |
| `employment_status`     | Tình trạng việc làm               |
| `is_borrower_homeowner` | Người vay có sở hữu nhà hay không |
| `borrower_state`        | Bang/khu vực cư trú của người vay |

---

## 🎯 Ghi chú quan trọng

* Các biến như:

  * `credit_score`
  * `debt_to_income_ratio`
  * `income`
  * `loan_amount`

  👉 Là những yếu tố chính ảnh hưởng đến khả năng vỡ nợ.

* Không sử dụng cho Machine Learning:

  * `closed_date`
  * `loan_status` (trực tiếp)

---

## 🚀 Vai trò của Silver Layer

Silver là lớp dữ liệu:

* Đã làm sạch và chuẩn hóa
* Là nguồn đầu vào cho:

  * Core (mô hình dữ liệu quan hệ)
  * Gold (feature engineering & BI)
  * Machine Learning

---
