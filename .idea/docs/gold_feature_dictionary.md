# Feature Dictionary – Gold Layer

## Dataset

**Table:** `gold.loan_features_v1`
**Purpose:** Model-ready dataset dùng cho bài toán **loan default prediction**.

Mỗi dòng trong bảng đại diện cho **một khoản vay duy nhất (listing_key)** sau khi đã:

* Làm sạch dữ liệu (Silver layer)
* Loại bỏ duplicate
* Loại bỏ data leakage
* Thực hiện feature engineering

Dataset này chỉ chứa **origination-safe features**, tức là chỉ dùng thông tin có sẵn **tại thời điểm khoản vay được tạo**.

---

# 1. Identifier & Target

## listing_key

**Type:** TEXT

**Mô tả**

Khóa định danh duy nhất của mỗi listing khoản vay.

**Vai trò**

* Primary key của bảng Gold
* Dùng để join với các bảng khác nếu cần.

---

## is_default

**Type:** INT (0 / 1)

**Mô tả**

Biến mục tiêu (target variable) cho bài toán dự đoán vỡ nợ.

**Logic tạo**

```text
1 → LoanStatus ∈ {Chargedoff, Defaulted}
0 → các trạng thái còn lại
```

**Ý nghĩa**

* `1` → khoản vay bị vỡ nợ
* `0` → khoản vay không vỡ nợ

---

# 2. Loan Pricing Features

## borrower_apr

**Type:** DECIMAL

**Mô tả**

Annual Percentage Rate – lãi suất thực tế hàng năm mà borrower phải trả.

Bao gồm:

* lãi suất
* phí liên quan

**Ý nghĩa**

APR cao thường phản ánh **risk cao hơn**.

---

## borrower_rate

**Type:** DECIMAL

**Mô tả**

Lãi suất danh nghĩa của khoản vay.

**Ý nghĩa**

* borrower_rate cao → borrower có risk cao hơn
* thường tương quan mạnh với default probability.

---

## rate_apr_spread

**Type:** DECIMAL

**Công thức**

```text
borrower_apr - borrower_rate
```

**Ý nghĩa**

Phản ánh **chênh lệch giữa APR và interest rate**.

Spread lớn có thể phản ánh:

* nhiều phí
* risk pricing.

---

# 3. Credit Risk Features

## prosper_rating_alpha

**Type:** TEXT

**Mô tả**

Hạng tín dụng của borrower do Prosper đánh giá.

**Các mức**

```
AA, A, B, C, D, E, HR
```

**Ý nghĩa**

Rating cao → borrower ít rủi ro hơn.

---

## rating_ordinal

**Type:** INT

**Encoding**

| Rating | Value |
| ------ | ----- |
| HR     | 1     |
| E      | 2     |
| D      | 3     |
| C      | 4     |
| B      | 5     |
| A      | 6     |
| AA     | 7     |

**Mục đích**

Chuyển rating từ **categorical → numeric** để mô hình ML sử dụng.

---

## prosper_score

**Type:** INT

**Mô tả**

Prosper proprietary credit score (1–11).

**Ý nghĩa**

Score cao → risk thấp.

---

## prosper_score_missing_flag

**Type:** INT

**Logic**

```
1 → prosper_score is NULL
0 → có score
```

**Mục đích**

Giúp model học được rằng **missing score cũng mang thông tin**.

---

# 4. Credit Score Features

## credit_score_range_lower

**Type:** INT

Lower bound của credit score.

---

## credit_score_range_upper

**Type:** INT

Upper bound của credit score.

---

## credit_score_midpoint

**Type:** FLOAT

**Công thức**

```text
(lower + upper) / 2
```

**Ý nghĩa**

Ước lượng **credit score thực tế của borrower**.

---

## credit_score_band

**Type:** TEXT

**Buckets**

```
<600
600–639
640–679
680–719
720+
```

**Ý nghĩa**

Bucket hóa credit score để phân tích risk theo nhóm.

---

## credit_score_missing_flag

**Type:** INT

**Logic**

```
1 → credit score missing
0 → available
```

---

# 5. Income Features

## stated_monthly_income

**Type:** DECIMAL

**Mô tả**

Thu nhập hàng tháng do borrower khai báo.

---

## log_monthly_income

**Type:** FLOAT

**Công thức**

```text
log(1 + stated_monthly_income)
```

**Mục đích**

Income thường **skewed distribution**, log transform giúp:

* giảm outlier
* cải thiện modeling.

---

## annual_income_est

**Type:** DECIMAL

**Công thức**

```text
monthly_income * 12
```

Ước lượng thu nhập năm.

---

## income_range

**Type:** TEXT

Khoảng thu nhập self-reported của borrower.

---

## income_range_ordinal

**Type:** INT

**Mapping**

| Range   | Value |
| ------- | ----- |
| $0      | 0     |
| $1–24k  | 1     |
| $25–49k | 2     |
| $50–74k | 3     |
| $75–99k | 4     |
| $100k+  | 5     |

**Mục đích**

Ordinal encoding cho ML model.

---

## income_missing_flag

**Type:** INT

```
1 → income missing
0 → available
```

---

# 6. Loan Burden Feature

## loan_original_amount

**Type:** DECIMAL

Số tiền vay ban đầu.

---

## loan_amount_to_income

**Type:** FLOAT

**Công thức**

```text
loan_amount / annual_income
```

**Ý nghĩa**

Đo **mức gánh nặng khoản vay so với thu nhập**.

Ratio cao → risk cao.

---

# 7. Debt Features

## debt_to_income_ratio

**Type:** DECIMAL

**Mô tả**

Tỷ lệ tổng nợ / thu nhập.

**Ý nghĩa**

DTI cao → borrower khó trả nợ hơn.

---

## dti_missing_flag

**Type:** INT

```
1 → missing
0 → available
```

---

# 8. Borrower Profile

## employment_status

**Type:** TEXT

Trạng thái việc làm của borrower.

---

## employment_status_grouped

**Type:** TEXT

Grouped categories:

```
Employed
Self-employed
Retired
Not employed
Other / Unknown
```

**Mục đích**

Giảm cardinality cho model.

---

## occupation

**Type:** TEXT

Nghề nghiệp borrower.

---

## occupation_cleaned

**Type:** TEXT

Occupation sau khi normalize và xử lý null.

---

## is_borrower_homeowner

**Type:** BOOLEAN

Borrower có sở hữu nhà hay không.

---

## is_homeowner_flag

**Type:** INT

```
1 → homeowner
0 → không
```

Homeownership thường tương quan với **financial stability**.

---

# 9. Loan Structure

## term

**Type:** INT

Thời hạn khoản vay (tháng).

Thông thường:

```
12
36
60
```

---

## term_12_flag

## term_36_flag

## term_60_flag

**Type:** INT

One-hot encoding của loan term.

---

# 10. Time Features

## loan_origination_date

Ngày khoản vay được tạo.

---

## listing_creation_date

Ngày listing được đăng.

---

## origination_year

## origination_month

## origination_quarter

Extract từ `loan_origination_date`.

**Mục đích**

Capture **economic cycle effects**.

---

## listing_year

## listing_month

## listing_quarter

Extract từ `listing_creation_date`.

---

## post_2009_flag

```
1 → loan sau 2009
0 → trước 2009
```

**Ý nghĩa**

Prosper thay đổi **credit rating system từ 2009**.

Feature này giúp model phân biệt **era effect**.

---

# 11. Listing Category

## listing_category_numeric

Numeric code cho mục đích vay.

Ví dụ:

```
Debt consolidation
Home improvement
Business
Auto
Personal
```

---

# 12. Leakage Prevention

Các cột sau **đã bị loại khỏi Gold** để tránh data leakage:

```
loan_status
closed_date
LoanCurrentDaysDelinquent
LoanMonthsSinceOrigination
LP_* payment variables
```

Gold dataset chỉ sử dụng **origination-time features**.

---

# 13. Final Dataset Summary

| Layer  | Table                         |
| ------ | ----------------------------- |
| Bronze | bronze.prosper_loans_raw      |
| Silver | silver.prosper_loans_cleansed |
| Gold   | gold.loan_features_v1         |

**Rows**

```
113,066 loans
```

**Use case**

```
Loan default prediction
```

---

# 14. Usage

Dataset này được dùng cho:

* Logistic Regression
* Random Forest
* XGBoost
* Credit risk analysis
* BI dashboard


