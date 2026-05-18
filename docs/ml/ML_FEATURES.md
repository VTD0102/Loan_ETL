# ML_FEATURES.md — Tài liệu đặc trưng & kết quả huấn luyện mô hình

> **Lưu ý 18/05/2026:** Tài liệu này mô tả pipeline v3 cũ. Pipeline hiện tại đã chuyển sang Home Credit Stability v2/v4, bỏ `credit_score`, `credit_score_midpoint`, `rating_ordinal`, `gender_male_flag`, `cnt_children`, `cnt_fam_members`. Xem `docs/migration_v2_summary.md` để lấy contract và metric mới nhất.

> **Phiên bản model:** customer_lgbm_v3 (LightGBM) + scorecard_v3 (LR Scorecard)  
> **Ngày cập nhật:** Tháng 5 năm 2026  
> **Dữ liệu huấn luyện:** 300,360 rows từ `gold.hc_features_v1` (Home Credit Default Risk)  
> **Tỷ lệ vỡ nợ thực tế:** 8.07%

---

## 1. Bảng tổng hợp đặc trưng (28 features)

### 1.1 Đặc trưng người dùng nhập trực tiếp trên form (22)

| # | Tên feature | Ý nghĩa | Nguồn | Độ ưu tiên (LightGBM gain) |
|---|------------|---------|-------|--------------------------|
| 1 | `credit_score` | Điểm tín dụng FICO-style (300–850). Tín hiệu tổng hợp mạnh nhất về lịch sử tín dụng. | Form — nhập số | **#1 — 3,386** |
| 2 | `loan_amount` | Số tiền vay yêu cầu (USD). Khoản vay lớn hơn khả năng trả = rủi ro cao. | Form — nhập số | **#3 — 3,017** |
| 3 | `dti` | Debt-to-Income ratio: tổng trả nợ hàng tháng / thu nhập tháng. Càng cao càng nguy. | Form — nhập số | **#4 — 2,811** |
| 4 | `years_employed` | Số năm làm việc liên tục tại công ty hiện tại. Thâm niên cao → thu nhập ổn định. | Form — nhập số (năm) | **#5 — 2,727** |
| 5 | `monthly_income` | Thu nhập hàng tháng (USD). Nền tảng để đánh giá khả năng trả nợ. | Form — nhập số | **#8 — 1,727** |
| 6 | `term` | Kỳ hạn vay: 12, 24, 36, 48 hoặc 60 tháng. Kỳ hạn dài → thanh toán nhỏ hơn nhưng tổng lãi cao hơn. | Form — chọn | **#7 — 1,916** |
| 7 | `occupation_type` | Nghề nghiệp (19 loại: 18 HC gốc + Unknown). Một số nghề có tỷ lệ vỡ nợ cao rõ rệt (xem bảng bên dưới). | Form — dropdown | **#13 — 1,171** |
| 8 | `education_ordinal` | Trình độ học vấn (1=Tiểu học → 5=Sau đại học). Học vấn cao tương quan với thu nhập ổn định. | Form — dropdown | **#14 — 465** |
| 9 | `cnt_fam_members` | Tổng số người trong gia đình. Nhiều người phụ thuộc → áp lực tài chính cao hơn. | Form — nhập số | **#15 — 415** |
| 10 | `log_monthly_income` | Log tự nhiên của thu nhập tháng. Giúp model xử lý phân phối thu nhập lệch phải. | Form — tự tính từ monthly_income | **#16 — 361** |
| 11 | `gender_male_flag` | Giới tính (1=Nam, 0=Nữ). Dùng như đặc trưng thống kê, không là yếu tố quyết định. | Form — toggle | **#17 — 276** |
| 12 | `cnt_children` | Số con. Tương quan với gánh nặng chi tiêu gia đình. | Form — nhập số | **#18 — 236** |
| 13 | `employment_status` | Tình trạng việc làm (Working / Commercial associate / Pensioner / State servant / Unemployed). | Form — dropdown | **#20 — 217** |
| 14 | `is_homeowner` | Có sở hữu nhà/bất động sản (1=Có). Tài sản thế chấp = giảm rủi ro. | Form — toggle | **#21 — 191** |
| 15 | `is_married_flag` | Tình trạng hôn nhân (1=Đã kết hôn). Thu nhập kép thường ổn định hơn. | Form — toggle | **#22 — 180** |
| 16 | `rating_ordinal` | Điểm đánh giá nội bộ (0–10, tương tự Prosper Score). Ước tính từ EXT_SOURCE_2. | Form — nhập số | **#23 — 179** |
| 17 | `max_credit_overdue_days` | Số ngày quá hạn tín dụng lớn nhất trong lịch sử bureau. | Form — nhập số | **#24 — 141** |
| 18 | `has_bad_debt` | Có nợ xấu trong lịch sử bureau (1=Có). | Form — toggle | **#27 — 0\*** |
| 19 | `income_verifiable_flag` | Thu nhập có thể xác minh qua hợp đồng lao động (1=Có). | Form — toggle | **#26 — 13** |
| 20 | `high_dti_flag` | Flag cứng: DTI > 43% (1=Có). Bổ sung cho dti liên tục. | Form — tự tính từ dti | **#25 — 22** |
| 21 | `listing_category` | Mục đích vay (1=Cash, 2=Revolving). | Form — dropdown | **#28 — 0\*** |
| 22 | `loan_amount_to_income` | Tỷ lệ khoản vay / thu nhập năm. Đo lường mức độ "over-leverage". | Form — tự tính | **#6 — 2,399** |

> \* `has_bad_debt` và `listing_category` có gain = 0 trong phiên bản này, có thể do phân phối lệch hoặc LightGBM không dùng split này. Cần theo dõi thêm.

---

### 1.2 Đặc trưng tự động tính từ lịch sử nội bộ DB (4)

| # | Tên feature | Ý nghĩa | Cách tính | Độ ưu tiên |
|---|------------|---------|-----------|-----------|
| 23 | `num_bureau_records` | Số hồ sơ tín dụng trong bureau. Nhiều = có lịch sử tín dụng lâu dài. | COUNT từ `bronze.bureau_raw` | **#9 — 1,656** |
| 24 | `num_active_credit` | Số khoản tín dụng đang hoạt động. Quá nhiều = đang vay nhiều nơi. | COUNT WHERE CREDIT_ACTIVE='Active' | **#12 — 1,208** |
| 25 | `total_overdue_amount` | Tổng số tiền quá hạn trong bureau (USD). | SUM(AMT_CREDIT_SUM_OVERDUE) | **#19 — 219** |
| 26 | `max_credit_overdue_days` | Số ngày quá hạn tối đa trong bureau. | MAX(CREDIT_DAY_OVERDUE) | **#24 — 141** |

---

### 1.3 Đặc trưng lịch sử đơn vay trong hệ thống CreditIntel (2)

| # | Tên feature | Ý nghĩa | Cách tính | Độ ưu tiên |
|---|------------|---------|-----------|-----------|
| 27 | `num_previous_loans` | Số đơn vay đã nộp trước đây của user. Nhiều = có lịch sử, ít = khách mới. | COUNT từ `loan_applications` WHERE user_id = current_user | **#11 — 1,247** |
| 28 | `previous_default_rate` | Tỷ lệ đơn bị AUTO_REJECTED trong lịch sử. 0 = chưa từng bị từ chối tự động. | COUNT(AUTO_REJECTED) / COUNT(*) | **#10 — 1,562** |

---

## 2. Tỷ lệ vỡ nợ theo đặc trưng quan trọng

### 2.1 Theo occupation_type (top 10)

| Nghề nghiệp | Số mẫu | Tỷ lệ vỡ nợ |
|------------|--------|------------|
| Low-skill Laborers | 2,050 | **17.3%** |
| Drivers | 18,411 | 11.4% |
| Waiters/barmen staff | 1,316 | 11.3% |
| Security staff | 6,569 | 10.7% |
| Laborers | 54,306 | 10.6% |
| Cooking staff | 5,738 | 10.5% |
| Cleaning staff | 4,501 | 9.7% |
| Sales staff | 31,256 | 9.6% |
| Realty agents | 748 | 7.9% |
| Secretaries | 1,267 | 6.9% |

Tỷ lệ vỡ nợ trung bình toàn tập: **8.07%**

### 2.2 Theo DTI band

| DTI | Số mẫu | Tỷ lệ vỡ nợ |
|-----|--------|------------|
| < 30% (thấp) | 515 | 8.3% |
| 30%–43% (trung bình) | 1,653 | 5.9% |
| > 43% (cao) | 298,192 | 8.1% |

> Lưu ý: Phần lớn dữ liệu nằm ở nhóm DTI > 43% (99.3%), nên phân biệt nhóm này còn yếu. Cần dữ liệu đa dạng hơn.

---

## 3. Kết quả huấn luyện Model 1 — LightGBM v3

### 3.1 Cấu hình

| Tham số | Giá trị |
|---------|---------|
| Algorithm | LightGBM (Gradient Boosting) |
| n_estimators | 500 |
| num_leaves | 63 |
| subsample | 0.8 |
| colsample_bytree | 0.8 |
| is_unbalance | True (xử lý class imbalance) |
| Train/Test split | 80/20 stratified |
| Train rows | 240,288 |
| Test rows | 60,072 |

### 3.2 Chỉ số đánh giá (test set)

| Chỉ số | Giá trị |
|--------|---------|
| **ROC-AUC** | **0.7306** |
| Accuracy | 0.72 |
| Precision (No Default) | 0.95 |
| Recall (No Default) | 0.74 |
| F1 (No Default) | 0.83 |
| Precision (Default) | 0.17 |
| Recall (Default) | 0.60 |
| F1 (Default) | 0.26 |

### 3.3 Phân tích ngưỡng quyết định

| Ngưỡng | Đơn bị từ chối | Recall (Default) | Precision (Default) | Diễn giải |
|--------|---------------|-----------------|--------------------|---------  |
| 0.15 | 52,199 (87%) | 97.21% | 9.03% | Cực kỳ thận trọng — từ chối gần hết |
| 0.20 | 47,355 (79%) | 94.22% | 9.64% | **Ngưỡng LOW (loan suggestion)** |
| 0.25 | 41,891 (70%) | 90.34% | 10.45% | |
| 0.30 | 36,379 (61%) | 86.03% | 11.46% | |
| 0.35 | 31,062 (52%) | 80.40% | 12.55% | |
| **0.40** | 26,102 (43%) | 73.76% | **13.70%** | **Ngưỡng AUTO_REJECT** |

**Nhận xét:**
- Ở ngưỡng 0.40: model bắt được 73.76% khách thực sự vỡ nợ và từ chối tự động 43% hồ sơ.
- Precision thấp (13.7%) vì dữ liệu imbalanced (8% default rate) — là bình thường với loan scoring.
- ROC-AUC 0.7306 ở mức khá cho tập dữ liệu không có ext_source_1/3. Kaggle winner đạt 0.80 nhờ feature engineering sâu hơn và thêm nguồn dữ liệu.

### 3.4 Feature importance (LightGBM gain)

| Hạng | Feature | Gain | Nhóm |
|------|---------|------|------|
| 1 | credit_score | 3,386 | Form — tài chính |
| 2 | age_years | 3,258 | Form — nhân khẩu |
| 3 | loan_amount | 3,017 | Form — tài chính |
| 4 | dti | 2,811 | Form — tài chính |
| 5 | years_employed | 2,727 | Form — việc làm |
| 6 | loan_amount_to_income | 2,399 | Form — tính toán |
| 7 | term | 1,916 | Form — tài chính |
| 8 | monthly_income | 1,727 | Form — tài chính |
| 9 | num_bureau_records | 1,656 | DB — bureau |
| 10 | previous_default_rate | 1,562 | DB — lịch sử CreditIntel |
| 11 | num_previous_loans | 1,247 | DB — lịch sử CreditIntel |
| 12 | num_active_credit | 1,208 | DB — bureau |
| 13 | occupation_type | 1,171 | Form — việc làm |
| 14 | education_ordinal | 465 | Form — nhân khẩu |
| 15 | cnt_fam_members | 415 | Form — nhân khẩu |
| 16 | log_monthly_income | 361 | Form — tính toán |
| 17 | gender_male_flag | 276 | Form — nhân khẩu |
| 18 | cnt_children | 236 | Form — nhân khẩu |
| 19 | total_overdue_amount | 219 | DB — bureau |
| 20 | employment_status | 217 | Form — việc làm |
| 21 | is_homeowner | 191 | Form — tài chính |
| 22 | is_married_flag | 180 | Form — nhân khẩu |
| 23 | rating_ordinal | 179 | Form — tài chính |
| 24 | max_credit_overdue_days | 141 | DB — bureau |
| 25 | high_dti_flag | 22 | Form — tính toán |
| 26 | income_verifiable_flag | 13 | Form — tài chính |
| 27 | listing_category | 0 | Form — tài chính |
| 28 | has_bad_debt | 0 | DB — bureau |

---

## 4. Kết quả huấn luyện Model 2 — LR Scorecard v3

### 4.1 Cấu hình

| Tham số | Giá trị |
|---------|---------|
| Algorithm | Logistic Regression (sklearn) |
| C (regularization) | 0.1 (L2) |
| max_iter | 500 |
| Preprocessing | StandardScaler (numeric) + OrdinalEncoder (categorical) |
| FICO params | base_score=600, base_odds=50, PDO=20 |
| Score range | 300 – 850 |
| Train/Test split | 80/20 stratified |

### 4.2 Chỉ số đánh giá (test set)

| Chỉ số | Giá trị |
|--------|---------|
| **ROC-AUC** | **0.7109** |
| Score range thực tế | 467 – 677 |
| Score mean | 564 |
| Score median | 566 |
| Accuracy | 0.92 |
| Precision (No Default) | 0.92 |
| Recall (No Default) | 1.00 |
| Precision (Default) | 0.40 |
| Recall (Default) | ~0.00 |

**Nhận xét:** LR Scorecard có recall default ≈ 0 ở threshold=0.5 — điều này bình thường vì LR không được calibrate class_weight. Mục đích chính của scorecard là **chuyển đổi xác suất thành điểm số 300–850** (interpretable score) để trình bày cho user, không phải để phân loại trực tiếp.

### 4.3 Đóng góp từng đặc trưng (điểm/std)

| Feature | Hệ số LR | Điểm/std | Hướng ảnh hưởng |
|---------|---------|---------|----------------|
| credit_score_midpoint | -0.516 | **+14.89** | Điểm tín dụng cao → an toàn hơn |
| num_bureau_records | -0.267 | **+7.70** | Nhiều hồ sơ tín dụng → có lịch sử lâu |
| years_employed | -0.227 | **+6.54** | Thâm niên cao → ổn định |
| education_ordinal | -0.212 | **+6.13** | Học vấn cao → ổn định hơn |
| age_years | -0.129 | +3.73 | Tuổi cao hơn → kinh nghiệm quản lý tài chính |
| num_previous_loans | -0.089 | +2.56 | Đã từng vay thành công → tốt |
| loan_amount_to_income | -0.079 | +2.27 | Khoản vay nhỏ so với thu nhập → tốt |
| is_married_flag | -0.056 | +1.60 | Đã kết hôn → thu nhập kép |
| employment_status_grouped | -0.031 | +0.89 | Việc làm ổn định → tốt |
| num_active_credit | +0.390 | **-11.26** | Nhiều tín dụng đang hoạt động → rủi ro |
| previous_default_rate | +0.200 | -5.78 | Từng bị từ chối → rủi ro |
| income_verifiable_flag | +0.178 | -5.12 | Không xác minh được thu nhập → rủi ro |
| gender_male_flag | +0.152 | -4.39 | Nam giới trong dataset này có rủi ro cao hơn |
| payment_to_income | +0.094 | -2.70 | Gánh nặng trả nợ cao → rủi ro |
| debt_to_income_ratio | +0.094 | -2.70 | DTI cao → rủi ro |
| rating_ordinal | +0.047 | -1.35 | Rating thấp → rủi ro |

### 4.4 So sánh 2 model

| Tiêu chí | LightGBM v3 | LR Scorecard v3 | Ghi chú |
|---------|------------|----------------|--------|
| ROC-AUC | **0.7306** | 0.7109 | LightGBM tốt hơn ~2% |
| Recall default | 73.76% (t=0.4) | ~0% (t=0.5) | Dùng LightGBM để AUTO_REJECT |
| Interpretability | Thấp | **Cao** | Scorecard giải thích được từng yếu tố |
| Mục đích chính | AUTO_REJECT + loan suggestion | Tính điểm 300–850 cho user | Dùng song song |
| ROC-AUC (version cũ) | 0.7529 (v2) | 0.7341 (v2) | Giảm ~2% do bỏ ext_source_1/3 |

---

## 5. Đề xuất bổ sung dữ liệu từ CSV có sẵn

Thư mục `data/home_credit/` có 5 file CSV chưa được khai thác (ngoài `bureau.csv` đã dùng). Mỗi file có thể cung cấp đặc trưng mới giúp tăng ROC-AUC.

---

### 5.1 `bureau_balance.csv` — 27.3M rows, 358 MB

**Cột:** `SK_ID_BUREAU`, `MONTHS_BALANCE`, `STATUS` (C/X/0/1/2/3/4/5)

**Đặc trưng có thể tạo:**

| Feature mới | Cách tính | Tác dụng dự kiến |
|------------|-----------|-----------------|
| `bureau_months_dpd_count` | COUNT tháng STATUS ∈ {1,2,3,4,5} (có DPD) | Tần suất quá hạn lịch sử |
| `bureau_max_dpd_status` | MAX(STATUS) per customer (0–5) | Mức quá hạn nghiêm trọng nhất |
| `bureau_recent_dpd_3m` | COUNT DPD trong 3 tháng gần nhất | Xu hướng quá hạn gần đây — quan trọng hơn lịch sử xa |
| `bureau_closed_credit_ratio` | COUNT(STATUS='C') / COUNT(*) | Tỷ lệ đóng tài khoản = trả hết nợ |

**Ước tính tăng AUC:** +0.01–0.02 (từ trend ngắn hạn 3 tháng)

---

### 5.2 `installments_payments.csv` — 13.6M rows, 690 MB

**Cột:** `DAYS_INSTALMENT`, `DAYS_ENTRY_PAYMENT`, `AMT_INSTALMENT`, `AMT_PAYMENT`

**Đặc trưng có thể tạo:**

| Feature mới | Cách tính | Tác dụng dự kiến |
|------------|-----------|-----------------|
| `avg_payment_delay_days` | AVG(DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT) | Độ trễ thanh toán trung bình — rất dự báo |
| `late_payment_rate` | COUNT(delay > 0) / COUNT(*) | % lần trả trễ hạn |
| `payment_amount_ratio` | AVG(AMT_PAYMENT / AMT_INSTALMENT) | Trả đủ hay thiếu so với số phải trả |
| `max_payment_delay_days` | MAX(DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT) | Trễ hạn tệ nhất trong lịch sử |

**Ước tính tăng AUC:** +0.02–0.03 (hành vi thanh toán là signal mạnh nhất)

---

### 5.3 `credit_card_balance.csv` — 3.84M rows, 405 MB

**Cột:** `AMT_BALANCE`, `AMT_CREDIT_LIMIT_ACTUAL`, `AMT_PAYMENT_CURRENT`, `AMT_INST_MIN_REGULARITY`, `SK_DPD`, `SK_DPD_DEF`

**Đặc trưng có thể tạo:**

| Feature mới | Cách tính | Tác dụng dự kiến |
|------------|-----------|-----------------|
| `cc_utilization_avg` | AVG(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL) | Tỷ lệ dùng hạn mức thẻ — > 70% = rủi ro |
| `cc_min_payment_ratio` | AVG(AMT_PAYMENT_CURRENT / AMT_INST_MIN_REGULARITY) | Có trả đúng số tối thiểu không |
| `cc_dpd_months` | COUNT(SK_DPD > 0) per customer | Số tháng có DPD trên thẻ tín dụng |
| `cc_max_dpd` | MAX(SK_DPD) per customer | DPD tệ nhất trên thẻ |

**Ước tính tăng AUC:** +0.01–0.015 (thẻ tín dụng phản ánh hành vi chi tiêu)

---

### 5.4 `POS_CASH_balance.csv` — 10M rows, 375 MB

**Cột:** `CNT_INSTALMENT`, `CNT_INSTALMENT_FUTURE`, `NAME_CONTRACT_STATUS`, `SK_DPD`, `SK_DPD_DEF`

**Đặc trưng có thể tạo:**

| Feature mới | Cách tính | Tác dụng dự kiến |
|------------|-----------|-----------------|
| `pos_active_contracts` | COUNT(NAME_CONTRACT_STATUS='Active') | Số hợp đồng POS đang chạy |
| `pos_dpd_months_count` | COUNT(SK_DPD > 0) | Tần suất quá hạn POS loan |
| `pos_completed_ratio` | COUNT(Completed) / COUNT(*) | Đã tất toán bao nhiêu hợp đồng |
| `pos_remaining_installments_avg` | AVG(CNT_INSTALMENT_FUTURE) | Còn bao nhiêu kỳ cần trả |

**Ước tính tăng AUC:** +0.005–0.01 (signal phụ, bổ sung bureau)

---

### 5.5 `previous_application.csv` — 1.67M rows, 386 MB

**Cột:** `AMT_APPLICATION`, `AMT_CREDIT`, `NAME_CONTRACT_STATUS`, `CODE_REJECT_REASON`, `DAYS_DECISION`, `RATE_INTEREST_PRIMARY`, `CNT_PAYMENT`

**Đặc trưng có thể tạo:**

| Feature mới | Cách tính | Tác dụng dự kiến |
|------------|-----------|-----------------|
| `prev_approval_rate` | COUNT(Approved) / COUNT(prev apps) | Tỷ lệ được duyệt — cao = uy tín tốt |
| `prev_credit_received_ratio` | AVG(AMT_CREDIT / AMT_APPLICATION) | Tỷ lệ nhận được so với yêu cầu |
| `prev_was_ever_rejected` | MAX(NAME_CONTRACT_STATUS='Refused') | Từng bị từ chối chưa |
| `days_since_last_application` | MIN(ABS(DAYS_DECISION)) | Thời gian kể từ đơn gần nhất — nộp dồn dập = rủi ro |
| `prev_avg_interest_rate` | AVG(RATE_INTEREST_PRIMARY) | Lãi suất trung bình các khoản vay cũ |

**Ước tính tăng AUC:** +0.015–0.025 (lịch sử đơn vay đã được thẩm định = rất tin cậy)

---

### 5.6 Tổng hợp đề xuất bổ sung

| Ưu tiên | File CSV | Features đề xuất | Độ phức tạp ETL | Ước tính tăng AUC |
|---------|----------|-----------------|----------------|------------------|
| **P1 — Cao** | `installments_payments.csv` | avg_payment_delay, late_payment_rate, payment_ratio | Trung bình (join SK_ID_PREV → SK_ID_CURR) | +0.02–0.03 |
| **P1 — Cao** | `previous_application.csv` | prev_approval_rate, days_since_last_app, was_rejected | Thấp (group by SK_ID_CURR trực tiếp) | +0.015–0.025 |
| **P2 — Trung bình** | `bureau_balance.csv` | recent_dpd_3m, max_dpd_status | Cao (27M rows, cần aggregation theo SK_ID_BUREAU → SK_ID_CURR) | +0.01–0.02 |
| **P2 — Trung bình** | `credit_card_balance.csv` | cc_utilization_avg, cc_dpd_months | Trung bình | +0.01–0.015 |
| **P3 — Thấp** | `POS_CASH_balance.csv` | pos_dpd_count, pos_completed_ratio | Trung bình | +0.005–0.01 |

**Tổng ước tính nếu thêm tất cả P1+P2:** ROC-AUC có thể đạt **0.76–0.78** (tăng ~5–7pp so với hiện tại).

---

### 5.7 Hướng dẫn tích hợp vào ETL

Thêm vào `etl/load_bronze.py`:

```python
# Thêm vào PREV_COLS
PREV_COLS = ["SK_ID_CURR", "SK_ID_PREV", "NAME_CONTRACT_STATUS",
             "AMT_APPLICATION", "AMT_CREDIT", "DAYS_DECISION", "CODE_REJECT_REASON"]

# File mới cần load
INSTALLMENTS_COLS = ["SK_ID_CURR", "SK_ID_PREV",
                     "DAYS_INSTALMENT", "DAYS_ENTRY_PAYMENT",
                     "AMT_INSTALMENT", "AMT_PAYMENT"]

BUREAU_BAL_COLS   = ["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"]
CC_BAL_COLS       = ["SK_ID_CURR", "MONTHS_BALANCE",
                     "AMT_BALANCE", "AMT_CREDIT_LIMIT_ACTUAL",
                     "AMT_PAYMENT_CURRENT", "SK_DPD"]
```

Thêm CTE vào `database/transform_gold_homecredit.sql`:

```sql
-- CTE: prev_app_agg
prev_app_agg AS (
    SELECT SK_ID_CURR,
        COUNT(*) AS prev_total,
        SUM(CASE WHEN NAME_CONTRACT_STATUS='Approved' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS prev_approval_rate,
        MIN(ABS(DAYS_DECISION)) AS days_since_last_prev_app,
        MAX(CASE WHEN NAME_CONTRACT_STATUS='Refused' THEN 1 ELSE 0 END) AS prev_was_rejected
    FROM bronze.previous_application_raw
    GROUP BY SK_ID_CURR
),
-- CTE: installments_agg
installments_agg AS (
    SELECT SK_ID_CURR,
        AVG(DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT) AS avg_payment_delay_days,
        SUM(CASE WHEN DAYS_ENTRY_PAYMENT > DAYS_INSTALMENT THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS late_payment_rate,
        AVG(AMT_PAYMENT / NULLIF(AMT_INSTALMENT, 0)) AS payment_amount_ratio
    FROM bronze.installments_raw
    GROUP BY SK_ID_CURR
)
```

---

## 6. Định hướng cải thiện khác (không liên quan CSV)

| Hướng | Chi tiết | Ước tính tăng AUC |
|-------|---------|------------------|
| **Hyperparameter tuning** | Dùng Optuna/BayesOpt thay vì cấu hình cứng hiện tại | +0.005–0.01 |
| **Feature crosses** | `credit_score × dti`, `years_employed × occupation_type` | +0.005–0.01 |
| **Tái cân bằng class** | SMOTE hoặc điều chỉnh `scale_pos_weight` | Tăng recall default, nhưng có thể giảm precision |
| **Target encoding** | Encode occupation_type bằng mean default rate thay vì ordinal | +0.005 |
| **Ensemble** | Kết hợp LightGBM + XGBoost + LR với stacking | +0.01–0.02, phức tạp hơn |
