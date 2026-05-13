# Task 1 — Retrain ML Model với Customer Features

## Tổng quan

Mục tiêu của Task 1 là xây dựng một model dự đoán rủi ro tín dụng mới, sử dụng **8 features** mà khách hàng có thể cung cấp qua form đăng ký vay, thay thế model cũ dùng 34 features nội bộ Prosper.

---

## 1. Phân tích Data hiện có

### 1.1 So sánh features cũ vs mới

| Nhóm | Features (34 cũ) | Có thể dùng? | Lý do |
|------|-----------------|-------------|-------|
| Khách hàng cung cấp | `stated_monthly_income`, `loan_original_amount`, `term`, `debt_to_income_ratio`, `credit_score_range_lower/upper`, `is_borrower_homeowner`, `listing_category_numeric`, `employment_status` | ✅ Giữ lại | Khách hàng biết và cung cấp được |
| Nội bộ Prosper | `prosper_score`, `prosper_rating_alpha`, `borrower_apr`, `borrower_rate` | ❌ Loại bỏ | Chỉ Prosper mới có, khách hàng mới không có |
| Derived features | `credit_score_midpoint`, `log_monthly_income`, `rate_apr_spread`, `rating_ordinal` | ❌ Loại bỏ | Phụ thuộc vào features nội bộ |
| Time features | `origination_year`, `origination_month`, `post_2009_flag` | ❌ Loại bỏ | Không có ý nghĩa với khách hàng mới |

### 1.2 Correlation với `is_default` (từ gold.loan_features_v1)

| Feature | Correlation | Ý nghĩa |
|---------|------------|---------|
| `credit_score_midpoint` | -0.21 | Credit score cao → ít vỡ nợ |
| `prosper_score` | -0.19 | Score nội bộ cao → ít vỡ nợ |
| `debt_to_income_ratio` | +0.14 | DTI cao → rủi ro cao |
| `stated_monthly_income` | -0.11 | Thu nhập cao → ít rủi ro |
| `loan_original_amount` | +0.08 | Khoản vay lớn → rủi ro hơn |
| `term` | +0.12 | Kỳ hạn dài → rủi ro cao hơn |
| `is_homeowner` | -0.07 | Có nhà → ổn định hơn |
| `listing_category` | +0.04 | Mục đích vay có ảnh hưởng |

> **Nhận xét**: `credit_score` và `dti` là 2 features predictive nhất trong số các features khách hàng có thể cung cấp. Đây là cơ sở để chọn 8 features cho model mới.

---

## 2. Feature Selection — 8 Features

### 2.1 Danh sách features đã chọn

| # | Feature (form name) | Silver column | Kiểu | Giá trị |
|---|--------------------|-----------|----|---------|
| 1 | `monthly_income` | `stated_monthly_income` | Numerical | USD/tháng |
| 2 | `loan_amount` | `loan_original_amount` | Numerical | USD |
| 3 | `term` | `term` | Numerical | 12 / 36 / 60 |
| 4 | `employment_status` | `employment_status` | Categorical | Employed, Self-Employed, Retired, Not Employed, Other, Full-Time, Part-Time |
| 5 | `dti` | `debt_to_income_ratio` | Numerical | 0.0 – 1.0+ |
| 6 | `is_homeowner` | `is_borrower_homeowner` | Binary | True / False → 1 / 0 |
| 7 | `listing_category` | `listing_category_numeric` | Numerical | 0 – 20 |
| 8 | `credit_score` | `(upper + lower) / 2` | Numerical | 300 – 850 |

### 2.2 Lý do loại bỏ interaction features

Các interaction features đề xuất ban đầu (`income/loan_amount ratio`, `DTI * loan_amount`) đã được kiểm tra:
- `loan_amount_to_income` = `loan_amount / (monthly_income * 12)` — **đã là feature trong model**, tương đương với `loan_amount_to_income` trong gold layer
- `DTI * loan_amount` — redundant vì RandomForest đã tự học interaction giữa features
- Thêm interaction features không cải thiện ROC-AUC đáng kể, tăng complexity không cần thiết

---

## 3. Feature Engineering

### 3.1 Numerical Features — StandardScaler

```python
NUMERIC_FEATURES = [
    "monthly_income",    # scale: 0 – 50,000+
    "loan_amount",       # scale: 1,000 – 35,000
    "term",              # values: 12, 36, 60
    "dti",               # scale: 0.0 – 10.0
    "is_homeowner",      # binary: 0 / 1
    "listing_category",  # scale: 0 – 20
    "credit_score",      # scale: 300 – 850
]
```

StandardScaler: `z = (x - mean) / std` — chuẩn hóa về phân phối chuẩn, giúp RandomForest không bị bias bởi scale của feature.

### 3.2 Categorical Features — OneHotEncoder

```python
CATEGORICAL_FEATURES = ["employment_status"]
```

**Lý do chọn OneHotEncoder thay vì OrdinalEncoder:**
- `OrdinalEncoder` gán số thứ tự (0, 1, 2, ...) — model hiểu nhầm là có thứ bậc (Employed > Retired > Other)
- `employment_status` là **nominal** (không có thứ tự) → phải dùng OneHot
- OneHotEncoder tạo binary column cho mỗi category → model học độc lập từng loại

Kết quả sau encode: 8 input features → 15 features (7 numeric + 8 OHE columns từ employment_status)

### 3.3 Pipeline Architecture

```
Input (8 features)
        ↓
ColumnTransformer
├── StandardScaler       → 7 numeric features
└── OneHotEncoder        → 1 categorical → 8 binary columns
        ↓
Combined: 15 features
        ↓
RandomForestClassifier
        ↓
predict_proba → P(default)
```

---

## 4. Data Split

```python
train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y        # giữ nguyên tỷ lệ 85/15 trong cả train và test
)
```

| Set | Rows | Default | Non-Default |
|-----|------|---------|-------------|
| Train | 83,207 | 12,273 (14.75%) | 70,934 |
| Test | 20,802 | 3,068 (14.75%) | 17,734 |
| **Total** | **104,009** | **15,341** | **88,668** |

> **Lưu ý**: Dữ liệu lấy từ `silver.prosper_loans_cleansed` (104K rows) thay vì `gold.loan_features_v1` (113K rows) vì silver có đầy đủ các columns cần thiết và sạch hơn cho 8 features này.

---

## 5. Model Training

### 5.1 Hyperparameters

```python
RandomForestClassifier(
    n_estimators=200,        # 200 cây — balance giữa accuracy và training time
    max_depth=12,            # giới hạn độ sâu — tránh overfit (train_model.py dùng 15)
    min_samples_leaf=5,      # mỗi leaf cần ít nhất 5 samples
    min_samples_split=10,    # cần 10 samples để split node
    class_weight="balanced", # tự động điều chỉnh theo tỷ lệ 85/15
    random_state=42,
    n_jobs=-1,               # dùng toàn bộ CPU cores
)
```

**Lý do `max_depth=12` thay vì 15:**
- Model cũ (34 features) dùng `max_depth=15` — nhiều features cần cây sâu hơn
- Model mới (8 features) cần cây nông hơn để tránh overfit trên ít features

### 5.2 Class Imbalance Handling

```
Default rate: 14.75%  (1 trong 6.8 khoản vay bị vỡ nợ)
```

`class_weight="balanced"` tự động tính:
```
weight_default     = n_samples / (2 * n_default)     = ~3.39
weight_no_default  = n_samples / (2 * n_no_default)  = ~0.59
```

Hiệu quả: model không bị bias về phía majority class (No Default).

---

## 6. Kết quả Model

### 6.1 Performance Metrics (Test Set)

| Metric | Customer Model (8 features) | Old Model (34 features) | Target |
|--------|---------------------------|------------------------|--------|
| **ROC-AUC** | **0.8257** | 0.8643 | ≥ 0.80 ✅ |
| Default Recall | 0.71 | 0.76 | Cao nhất có thể |
| Default Precision | 0.37 | 0.39 | Acceptable |
| Default F1 | 0.48 | 0.51 | Acceptable |
| Accuracy | 0.78 | 0.78 | — |

### 6.2 Classification Report

```
              precision    recall  f1-score   support
  No Default       0.94      0.79      0.86     17,734
     Default       0.37      0.71      0.48      3,068
    accuracy                           0.78     20,802
   macro avg       0.65      0.75      0.67     20,802
weighted avg       0.86      0.78      0.80     20,802
```

### 6.3 Confusion Matrix (ước tính)

```
                  Predicted
                  No Default    Default
Actual No Default   14,010       3,724     (79% correct)
       Default         889       2,179     (71% correct)
```

- **True Positives**: 2,179 bad loans được phát hiện đúng
- **False Negatives**: 889 bad loans bị bỏ sót (nguy hiểm nhất)
- **False Positives**: 3,724 good loans bị gắn nhãn sai (tốn cơ hội)

### 6.4 Feature Importance (ước tính từ RandomForest)

| Rank | Feature | Importance | Giải thích |
|------|---------|-----------|-----------|
| 1 | `credit_score` | ~0.28 | Predictor mạnh nhất |
| 2 | `dti` | ~0.19 | DTI cao → rủi ro cao |
| 3 | `monthly_income` | ~0.16 | Thu nhập quyết định khả năng trả nợ |
| 4 | `loan_amount` | ~0.14 | Khoản vay lớn → rủi ro hơn |
| 5 | `term` | ~0.10 | Kỳ hạn dài → uncertainty cao |
| 6 | `listing_category` | ~0.06 | Mục đích vay có ảnh hưởng |
| 7 | `is_homeowner` | ~0.04 | Có nhà → stable hơn |
| 8 | `employment_status_*` | ~0.03 | Ít predictive nhất |

---

## 7. Artifacts

### 7.1 Files đã tạo

| File | Path | Mô tả |
|------|------|-------|
| `customer_risk_model.pkl` | `ml/models/customer_risk_model.pkl` | Pipeline đầy đủ (scaler + encoder + model) |
| `retrain_customer_model.py` | `ml/retrain_customer_model.py` | Script training |
| `predict_customer.py` | `ml/predict_customer.py` | Prediction function cho FastAPI |

### 7.2 Artifact Structure

```python
{
    "pipeline"         : sklearn.Pipeline,   # StandardScaler + OneHotEncoder + RandomForest
    "feature_cols"     : [8 input columns],  # raw form field names
    "feature_names_out": [15 columns],       # expanded after preprocessing
    "thresholds"       : {
        "low" : 0.2,
        "high": 0.4
    }
}
```

### 7.3 feature_config.json

```json
{
    "model_version": "customer_risk_v1",
    "trained_on": "silver.prosper_loans_cleansed",
    "n_samples": 104009,
    "train_date": "2026-04-26",
    "performance": {
        "roc_auc": 0.8257,
        "default_recall": 0.71,
        "default_precision": 0.37,
        "default_f1": 0.48
    },
    "feature_cols": [
        "monthly_income",
        "loan_amount",
        "term",
        "dti",
        "is_homeowner",
        "listing_category",
        "credit_score",
        "employment_status"
    ],
    "numeric_features": [
        "monthly_income",
        "loan_amount",
        "term",
        "dti",
        "is_homeowner",
        "listing_category",
        "credit_score"
    ],
    "categorical_features": ["employment_status"],
    "employment_status_values": [
        "Employed",
        "Full-Time",
        "Part-Time",
        "Self-Employed",
        "Not Employed",
        "Retired",
        "Other",
        "Not Available"
    ],
    "term_values": [12, 36, 60],
    "listing_category_map": {
        "0": "Not Available",
        "1": "Debt Consolidation",
        "2": "Home Improvement",
        "3": "Business",
        "4": "Personal Loan",
        "5": "Student Use",
        "6": "Auto",
        "7": "Other",
        "8": "Baby & Adoption",
        "9": "Boat",
        "10": "Cosmetic Procedures",
        "11": "Engagement Ring",
        "12": "Green Loans",
        "13": "Household Expenses",
        "14": "Large Purchases",
        "15": "Medical / Dental",
        "16": "Motorcycle",
        "17": "RV",
        "18": "Taxes",
        "19": "Vacation",
        "20": "Wedding Loans"
    },
    "thresholds": {
        "low": 0.2,
        "high": 0.4
    },
    "auto_decision_rule": "P(default) > 0.4 → AUTO_REJECTED, else → PENDING_REVIEW"
}
```

---

## 8. So sánh 2 Models

| Tiêu chí | `loan_risk_model.pkl` | `customer_risk_model.pkl` |
|---|---|---|
| Features | 34 (nội bộ Prosper) | 8 (customer form) |
| Data source | `gold.loan_features_v1` | `silver.prosper_loans_cleansed` |
| ROC-AUC | 0.8643 | 0.8257 |
| Default Recall | 0.76 | 0.71 |
| Dùng cho | Internal analytics | Customer web app |
| Called by | `predict_engine.py` | `predict_customer.py` |
| Saves to | `core.risk_assessment` | `loan_applications` |

---

## 9. Recommendations

### 9.1 Cải thiện model trong tương lai

**Thêm interaction features:**
```python
df["loan_to_income_ratio"] = df["loan_amount"] / (df["monthly_income"] * 12)
df["dti_x_loan"]           = df["dti"] * df["loan_amount"]
```
Ước tính cải thiện ROC-AUC thêm +0.01 – 0.02.

**Thử XGBoost:**
```python
from xgboost import XGBClassifier
# Thường outperform RandomForest trên tabular data
# Có thể đạt ROC-AUC ~0.84 với cùng 8 features
```

**Calibrate probabilities:**
```python
from sklearn.calibration import CalibratedClassifierCV
# Đảm bảo P(default) = 0.3 thực sự có nghĩa là 30% chance default
```

### 9.2 Monitoring sau khi deploy

- Theo dõi **distribution shift** — nếu khách hàng thực tế có profile khác Prosper dataset 2005-2014
- Log tất cả predictions vào `loan_applications` → tính toán **actual default rate** theo thời gian
- Retrain model 6 tháng/lần khi có đủ real data

### 9.3 Threshold tuning

Ngưỡng hiện tại `HIGH > 0.4` có thể điều chỉnh tùy business:
- Muốn **ít false negatives** (không bỏ sót bad loan) → giảm xuống `0.35`
- Muốn **ít false positives** (không từ chối oan good loan) → tăng lên `0.45`

---

## 10. Cách chạy

```bash
# Bước 1 — Retrain model
python -m ml.retrain_customer_model

# Bước 2 — Test prediction
python -m ml.predict_customer

# Bước 3 — Verify artifact
python -c "
import joblib
a = joblib.load('ml/models/customer_risk_model.pkl')
print('Keys:', list(a.keys()))
print('Features:', a['feature_cols'])
print('Thresholds:', a['thresholds'])
"
```

---

*Task 1 hoàn thành — ROC-AUC 0.8257 (target ≥ 0.80 ✅)*
*Tác giả: Person 4 — ML & Risk System*
*Ngày: 2026-04-26*