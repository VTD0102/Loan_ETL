# Data Pipeline Architecture – Prosper Loan Project

## Overview

Dự án sử dụng kiến trúc **Medallion Architecture** để xử lý dữ liệu khoản vay Prosper.

Pipeline được chia thành 3 lớp:

```
Raw CSV
   ↓
Bronze Layer
   ↓
Silver Layer
   ↓
Gold Layer
   ↓
Machine Learning / Analytics
```

Mục tiêu của pipeline là:

* chuẩn hóa dữ liệu
* loại bỏ dữ liệu lỗi
* tránh data leakage
* tạo dataset sẵn sàng cho Machine Learning.

---

# 1. Bronze Layer

## Table

```
bronze.prosper_loans_raw
```

## Source

```
data/raw/prosperLoanData.csv
```

## Số lượng cột

```
81 columns
```

## Vai trò

Bronze layer chứa **dữ liệu thô từ nguồn**.

Đặc điểm:

* giữ nguyên cấu trúc CSV
* không xử lý missing
* không ép kiểu dữ liệu
* không loại duplicate

Toàn bộ cột được load dưới dạng:

```
TEXT
```

để tránh lỗi ingestion.

## Ingestion Process

Script sử dụng:

```
load_bronze.py
```

Luồng xử lý:

```
CSV
 ↓
pandas read_csv
 ↓
PostgreSQL COPY / INSERT
 ↓
bronze.prosper_loans_raw
```

---

# 2. Silver Layer

## Table

```
silver.prosper_loans_cleansed
```

## Input

```
bronze.prosper_loans_raw
```

## Script

```
etl_silver.py
database/transform_silver.sql
```

## Vai trò

Silver layer thực hiện:

* data cleaning
* type casting
* null normalization
* duplicate removal
* target creation

Silver là dataset **đã chuẩn hóa nhưng chưa feature engineering**.

---

## Các bước xử lý trong Silver

### 1. Normalize null values

Các giá trị sau được chuyển thành `NULL`:

```
''
'null'
'n/a'
'na'
'none'
```

Ví dụ:

```
NULLIF(column, '')
```

---

### 2. Trim và chuẩn hóa text

Ví dụ:

```
btrim(column)
lower(column)
initcap(column)
```

Mục đích:

* chuẩn hóa category
* loại bỏ khoảng trắng.

---

### 3. Type casting

Các kiểu dữ liệu được ép về:

| Field   | Type      |
| ------- | --------- |
| date    | TIMESTAMP |
| rate    | NUMERIC   |
| income  | NUMERIC   |
| term    | INT       |
| score   | INT       |
| boolean | BOOLEAN   |

Ví dụ:

```
borrower_rate::numeric
loan_origination_date::timestamp
```

---

### 4. Boolean normalization

Ví dụ:

```
true / t / 1 / yes / y → TRUE
false / f / 0 / no / n → FALSE
```

---

### 5. Deduplicate records

Duplicate theo:

```
listing_key
```

Logic:

```
ROW_NUMBER() OVER (
    PARTITION BY listing_key
)
```

Giữ record mới nhất theo:

```
listing_creation_date
loan_origination_date
closed_date
```

---

### 6. Target creation

Silver tạo biến target:

```
is_default
```

Logic:

```
LoanStatus ∈ {Chargedoff, Defaulted} → 1
Else → 0
```

---

## Output columns

Silver giữ khoảng:

```
21 columns
```

Bao gồm:

* loan pricing
* borrower profile
* credit score
* income
* loan amount
* term
* target variable

---

# 3. Gold Layer

## Table

```
gold.loan_features_v1
```

## Input

```
silver.prosper_loans_cleansed
```

## Script

```
etl_gold.py
database/transform_gold.sql
```

---

## Vai trò

Gold layer tạo dataset **model-ready**.

Gold thực hiện:

* feature engineering
* encoding categorical features
* ratio features
* time features
* missing indicators
* leakage prevention

---

# 4. Leakage Prevention

Gold layer loại bỏ các biến **chỉ xuất hiện sau khi khoản vay hoạt động**.

Ví dụ:

```
loan_status
closed_date
LoanCurrentDaysDelinquent
LoanMonthsSinceOrigination
LP_* payment variables
```

Lý do:

Các biến này **không tồn tại tại thời điểm cấp loan**.

Nếu sử dụng sẽ gây:

```
data leakage
```

---

# 5. Feature Engineering

Gold tạo thêm nhiều feature quan trọng.

## Credit features

```
credit_score_midpoint
credit_score_band
rating_ordinal
```

---

## Income features

```
log_monthly_income
annual_income_est
income_range_ordinal
```

---

## Loan burden features

```
loan_amount_to_income
rate_apr_spread
```

---

## Time features

```
origination_year
origination_month
origination_quarter
listing_year
listing_month
listing_quarter
post_2009_flag
```

---

## Missing indicators

```
income_missing_flag
dti_missing_flag
prosper_score_missing_flag
credit_score_missing_flag
```

Các biến này giúp model hiểu rằng:

```
missing data cũng mang thông tin
```

---

# 6. Final Gold Dataset

## Table

```
gold.loan_features_v1
```

## Rows

```
113,066 loans
```

## Grain

```
1 row = 1 loan
```

## Target

```
is_default
```

## Dataset usage

Gold dataset được dùng cho:

* Machine Learning
* Risk modeling
* BI dashboard
* Statistical analysis

---

# 7. Pipeline Flow

```
CSV (Raw)
   ↓
load_bronze.py
   ↓
bronze.prosper_loans_raw
   ↓
etl_silver.py
   ↓
silver.prosper_loans_cleansed
   ↓
etl_gold.py
   ↓
gold.loan_features_v1
   ↓
ML models / dashboards
```

---

# 8. Technology Stack

| Component       | Tool                   |
| --------------- | ---------------------- |
| Language        | Python                 |
| Database        | PostgreSQL             |
| ETL             | SQL + Python           |
| Data processing | pandas                 |
| ML              | scikit-learn / XGBoost |
| Visualization   | Metabase / BI tools    |

---

# 9. Data Quality Controls

Pipeline đảm bảo:

* duplicate removal
* null normalization
* type validation
* leakage prevention
* feature consistency

---

# 10. Future Improvements

Có thể cải thiện pipeline bằng cách:

### Add more Silver features

Ví dụ:

```
MonthlyLoanPayment
EmploymentStatusDuration
IncomeVerifiable
FirstRecordedCreditLine
BankcardUtilization
CurrentDelinquencies
```

Các feature này sẽ giúp tạo thêm:

```
payment_to_income_ratio
credit_history_length
delinquency features
```

---

# 11. Summary

Pipeline sử dụng kiến trúc:

```
Bronze → Silver → Gold
```

để đảm bảo:

* dữ liệu sạch
* không leakage
* feature engineering chuẩn
* dataset sẵn sàng cho machine learning.
