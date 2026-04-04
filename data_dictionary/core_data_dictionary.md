# Core Schema Data Dictionary

Tài liệu này mô tả ý nghĩa các thuộc tính của toàn bộ bảng trong schema `core`, đồng thời giải thích mối quan hệ giữa các bảng.

Schema `core` là lớp **CSDL nghiệp vụ quan hệ** của hệ thống, được xây từ dữ liệu đã làm sạch ở Silver.
Mục tiêu của lớp này là:

* chuẩn hóa dữ liệu
* giảm lặp
* thể hiện rõ thực thể và quan hệ
* phục vụ phân tích, dự đoán rủi ro và dashboard

---

# 1. Tổng quan các bảng trong Core

Schema `core` hiện gồm 8 bảng:

## Nhóm bảng danh mục (Dimension Tables)

* `core.dim_employment_status`
* `core.dim_occupation`
* `core.dim_income_range`
* `core.dim_loan_status`
* `core.dim_listing_category`

## Nhóm bảng thực thể nghiệp vụ

* `core.borrowers`
* `core.loans`
* `core.credit_profiles`

---

# 2. Data Dictionary chi tiết

---

## 2.1. Bảng `core.dim_employment_status`

**Vai trò:**
Lưu danh mục tình trạng việc làm của người vay.

### Các thuộc tính

| Thuộc tính               | Ý nghĩa                                                                     |
| ------------------------ | --------------------------------------------------------------------------- |
| `employment_status_id`   | Khóa chính của bảng tình trạng việc làm                                     |
| `employment_status_name` | Tên trạng thái việc làm, ví dụ: Employed, Full-time, Self-employed, Retired |

### Ý nghĩa nghiệp vụ

Bảng này giúp chuẩn hóa các giá trị trạng thái việc làm để:

* tránh lặp text
* dễ join
* dễ phân tích theo nhóm việc làm

---

## 2.2. Bảng `core.dim_occupation`

**Vai trò:**
Lưu danh mục nghề nghiệp của người vay.

### Các thuộc tính

| Thuộc tính        | Ý nghĩa                         |
| ----------------- | ------------------------------- |
| `occupation_id`   | Khóa chính của bảng nghề nghiệp |
| `occupation_name` | Tên nghề nghiệp của người vay   |

### Ý nghĩa nghiệp vụ

Bảng này giúp:

* chuẩn hóa nghề nghiệp
* giảm lặp dữ liệu text
* phục vụ phân tích rủi ro theo nghề nghiệp

---

## 2.3. Bảng `core.dim_income_range`

**Vai trò:**
Lưu danh mục khoảng thu nhập của người vay.

### Các thuộc tính

| Thuộc tính           | Ý nghĩa                                                                          |
| -------------------- | -------------------------------------------------------------------------------- |
| `income_range_id`    | Khóa chính của bảng khoảng thu nhập                                              |
| `income_range_label` | Nhãn khoảng thu nhập, ví dụ: `$25,000-49,999`, `$50,000-74,999`, `Not displayed` |

### Ý nghĩa nghiệp vụ

Bảng này giúp:

* chuẩn hóa các mức thu nhập
* hỗ trợ phân tích theo phân khúc thu nhập
* dễ mapping sang thứ tự tăng dần nếu cần trong Gold

---

## 2.4. Bảng `core.dim_loan_status`

**Vai trò:**
Lưu danh mục trạng thái khoản vay.

### Các thuộc tính

| Thuộc tính         | Ý nghĩa                                                                    |
| ------------------ | -------------------------------------------------------------------------- |
| `loan_status_id`   | Khóa chính của bảng trạng thái khoản vay                                   |
| `loan_status_name` | Tên trạng thái khoản vay, ví dụ: Current, Completed, Chargedoff, Defaulted |

### Ý nghĩa nghiệp vụ

Bảng này cho phép:

* quản lý trạng thái khoản vay theo kiểu chuẩn hóa
* phục vụ thống kê số lượng khoản vay theo trạng thái
* tránh lặp text trong bảng `loans`

---

## 2.5. Bảng `core.dim_listing_category`

**Vai trò:**
Lưu danh mục mục đích vay.

### Các thuộc tính

| Thuộc tính      | Ý nghĩa                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| `category_id`   | Mã mục đích vay, cũng là khóa chính                                     |
| `category_name` | Tên mục đích vay, ví dụ: Debt Consolidation, Home Improvement, Business |

### Ý nghĩa nghiệp vụ

Bảng này giúp:

* diễn giải `listing_category_numeric`
* hỗ trợ phân tích theo mục đích vay
* phục vụ dashboard và báo cáo nghiệp vụ

---

## 2.6. Bảng `core.borrowers`

**Vai trò:**
Lưu thông tin người vay.

### Các thuộc tính

| Thuộc tính          | Ý nghĩa                                             |
| ------------------- | --------------------------------------------------- |
| `member_key`        | Khóa chính định danh người vay trong hệ thống nguồn |
| `borrower_state`    | Bang hoặc khu vực cư trú của người vay              |
| `is_homeowner`      | Người vay có sở hữu nhà hay không                   |
| `income_verifiable` | Thu nhập của người vay có thể xác minh hay không    |

### Ý nghĩa nghiệp vụ

Đây là bảng thực thể mô tả borrower.
Một người vay có thể xuất hiện trong nhiều khoản vay, nên việc tách `borrowers` ra giúp:

* giảm trùng lặp dữ liệu
* nhóm nhiều khoản vay về cùng một người
* phân tích theo borrower

---

## 2.7. Bảng `core.loans`

**Vai trò:**
Bảng trung tâm lưu thông tin khoản vay.

### Các thuộc tính

| Thuộc tính              | Ý nghĩa                                                  |
| ----------------------- | -------------------------------------------------------- |
| `listing_key`           | Khóa chính của khoản vay/listing                         |
| `loan_number`           | Mã số khoản vay hiển thị                                 |
| `member_key`            | Khóa ngoại liên kết tới người vay trong bảng `borrowers` |
| `loan_original_amount`  | Số tiền vay ban đầu                                      |
| `term`                  | Thời hạn khoản vay, thường là 12, 36 hoặc 60 tháng       |
| `borrower_apr`          | Annual Percentage Rate, phản ánh chi phí vay thực tế     |
| `borrower_rate`         | Lãi suất danh nghĩa của khoản vay                        |
| `listing_creation_date` | Ngày hồ sơ vay được tạo                                  |
| `loan_origination_date` | Ngày khoản vay chính thức được cấp                       |
| `closed_date`           | Ngày khoản vay kết thúc                                  |
| `loan_status_id`        | Khóa ngoại tới bảng `dim_loan_status`                    |
| `category_id`           | Khóa ngoại tới bảng `dim_listing_category`               |
| `employment_status_id`  | Khóa ngoại tới bảng `dim_employment_status`              |
| `occupation_id`         | Khóa ngoại tới bảng `dim_occupation`                     |
| `income_range_id`       | Khóa ngoại tới bảng `dim_income_range`                   |

### Ý nghĩa nghiệp vụ

Đây là bảng lõi của toàn hệ thống.
Mỗi dòng tương ứng với **một khoản vay**.

Bảng này chứa:

* dữ liệu tài chính của khoản vay
* dữ liệu thời gian
* khóa ngoại tới các bảng danh mục
* liên kết tới borrower

Đây cũng là bảng trung tâm để:

* join sang credit profile
* phân tích trạng thái khoản vay
* xây Gold
* xây dashboard

---

## 2.8. Bảng `core.credit_profiles`

**Vai trò:**
Lưu hồ sơ tín dụng gắn với từng khoản vay.

### Các thuộc tính

| Thuộc tính                 | Ý nghĩa                                         |
| -------------------------- | ----------------------------------------------- |
| `listing_key`              | Khóa chính, đồng thời liên kết tới bảng `loans` |
| `credit_score_range_lower` | Cận dưới của khoảng điểm tín dụng               |
| `credit_score_range_upper` | Cận trên của khoảng điểm tín dụng               |
| `debt_to_income_ratio`     | Tỷ lệ nợ trên thu nhập                          |
| `stated_monthly_income`    | Thu nhập hàng tháng do người vay khai báo       |
| `prosper_rating_alpha`     | Xếp hạng tín dụng theo Prosper                  |
| `prosper_score`            | Điểm tín dụng nội bộ của Prosper                |

### Ý nghĩa nghiệp vụ

Bảng này tách riêng phần thông tin tín dụng khỏi bảng `loans`.
Điều này có lợi vì:

* mô hình dữ liệu rõ ràng hơn
* các thuộc tính credit/risk được gom vào một nơi
* thuận tiện cho phân tích rủi ro và xây feature cho ML

---

# 3. Mối quan hệ giữa các bảng

Đây là phần quan trọng nhất của Core schema.

---

## 3.1. Quan hệ giữa `borrowers` và `loans`

### Quan hệ

* Một borrower có thể có nhiều loan
* Một loan chỉ thuộc về một borrower

### Kiểu quan hệ

**1 - N**

### Khóa liên kết

* `core.borrowers.member_key`
* `core.loans.member_key`

### Ý nghĩa

Một người vay có thể đăng ký nhiều khoản vay khác nhau theo thời gian.
Do đó:

* `borrowers` là thực thể cha
* `loans` là thực thể con

---

## 3.2. Quan hệ giữa `loans` và `credit_profiles`

### Quan hệ

* Mỗi loan có một credit profile tương ứng
* Mỗi credit profile gắn với một loan

### Kiểu quan hệ

**1 - 1** hoặc gần như 1 - 1 theo `listing_key`

### Khóa liên kết

* `core.loans.listing_key`
* `core.credit_profiles.listing_key`

### Ý nghĩa

Thông tin tín dụng là phần mở rộng của khoản vay, nhưng được tách riêng để chuẩn hóa.

---

## 3.3. Quan hệ giữa `dim_employment_status` và `loans`

### Quan hệ

* Một trạng thái việc làm có thể xuất hiện ở nhiều khoản vay
* Một khoản vay chỉ tham chiếu một trạng thái việc làm

### Kiểu quan hệ

**1 - N**

### Khóa liên kết

* `core.dim_employment_status.employment_status_id`
* `core.loans.employment_status_id`

### Ý nghĩa

Cho phép phân tích:

* tỷ lệ default theo tình trạng việc làm
* số lượng khoản vay theo việc làm

---

## 3.4. Quan hệ giữa `dim_occupation` và `loans`

### Quan hệ

* Một nghề nghiệp có thể gắn với nhiều khoản vay
* Mỗi khoản vay chỉ gắn với một nghề nghiệp

### Kiểu quan hệ

**1 - N**

### Khóa liên kết

* `core.dim_occupation.occupation_id`
* `core.loans.occupation_id`

### Ý nghĩa

Cho phép phân tích risk theo nghề nghiệp.

---

## 3.5. Quan hệ giữa `dim_income_range` và `loans`

### Quan hệ

* Một mức thu nhập có thể xuất hiện ở nhiều khoản vay
* Mỗi khoản vay chỉ thuộc một nhóm thu nhập

### Kiểu quan hệ

**1 - N**

### Khóa liên kết

* `core.dim_income_range.income_range_id`
* `core.loans.income_range_id`

### Ý nghĩa

Cho phép phân tích:

* default rate theo income range
* phân khúc người vay theo thu nhập

---

## 3.6. Quan hệ giữa `dim_loan_status` và `loans`

### Quan hệ

* Một trạng thái khoản vay có thể áp dụng cho nhiều khoản vay
* Mỗi khoản vay chỉ có một trạng thái tại một thời điểm

### Kiểu quan hệ

**1 - N**

### Khóa liên kết

* `core.dim_loan_status.loan_status_id`
* `core.loans.loan_status_id`

### Ý nghĩa

Cho phép:

* quản lý trạng thái chuẩn hóa
* phân tích trạng thái khoản vay
* làm báo cáo số lượng current/completed/defaulted

---

## 3.7. Quan hệ giữa `dim_listing_category` và `loans`

### Quan hệ

* Một mục đích vay có thể xuất hiện ở nhiều khoản vay
* Mỗi khoản vay chỉ có một mục đích vay

### Kiểu quan hệ

**1 - N**

### Khóa liên kết

* `core.dim_listing_category.category_id`
* `core.loans.category_id`

### Ý nghĩa

Cho phép phân tích:

* mục đích vay nào phổ biến nhất
* mục đích vay nào rủi ro cao hơn

---

# 4. Tóm tắt sơ đồ quan hệ

Có thể mô tả Core schema bằng dạng text như sau:

```text
dim_employment_status   1 ─── N
dim_occupation          1 ─── N
dim_income_range        1 ─── N
dim_loan_status         1 ─── N
dim_listing_category    1 ─── N
                              loans   1 ─── 1   credit_profiles
borrowers               1 ─── N
```

Hoặc đọc theo nghiệp vụ:

* Một người vay (`borrowers`) có thể có nhiều khoản vay (`loans`)
* Mỗi khoản vay (`loans`) có một hồ sơ tín dụng (`credit_profiles`)
* Mỗi khoản vay đồng thời tham chiếu tới:

  * một trạng thái việc làm
  * một nghề nghiệp
  * một nhóm thu nhập
  * một trạng thái khoản vay
  * một mục đích vay

---

# 5. Vai trò của Core trong toàn hệ thống

Schema `core` là lớp dữ liệu nghiệp vụ trung tâm của dự án.

## Core nhận dữ liệu từ đâu?

* từ `silver.prosper_loans_cleansed`

## Core dùng để làm gì?

* lưu trữ dữ liệu đã chuẩn hóa
* thể hiện mô hình quan hệ đúng chuẩn CSDL
* làm nguồn cho Gold
* làm nguồn cho phân tích nghiệp vụ
* làm nền cho tích hợp ML và RAG

## Core khác gì so với Silver?

* Silver: 1 bảng sạch nhưng vẫn còn dạng “flat table”
* Core: đã tách thành nhiều bảng quan hệ đúng bản chất nghiệp vụ

---

# 6. Ghi chú quan trọng khi dùng cho Gold và ML

Không phải mọi cột trong Core đều được đưa thẳng vào ML.

## Có thể dùng cho feature engineering

* `loan_original_amount`
* `term`
* `borrower_apr`
* `borrower_rate`
* `credit_score_range_lower`
* `credit_score_range_upper`
* `debt_to_income_ratio`
* `stated_monthly_income`
* `prosper_rating_alpha`
* `prosper_score`
* `employment_status`
* `occupation`
* `income_range`
* `is_homeowner`
* `income_verifiable`
* `borrower_state`

## Không nên dùng trực tiếp cho ML vì leakage

* `closed_date`
* `loan_status_id` nếu dùng như outcome sau khi khoản vay đã diễn ra

---

# 7. Kết luận

Core schema hiện tại đã đáp ứng rất tốt yêu cầu của một mô hình dữ liệu nghiệp vụ quan hệ:

* có thực thể
* có bảng danh mục
* có khóa chính
* có khóa ngoại
* có mối quan hệ rõ ràng
* có khả năng mở rộng cho Gold, ML và RAG

Đây là phần nền tảng quan trọng nhất để phát triển:

* Gold layer
* dashboard
* dự đoán rủi ro
* hỗ trợ thẩm định
