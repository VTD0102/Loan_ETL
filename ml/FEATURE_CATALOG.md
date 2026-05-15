# Feature Catalog — Customer Risk Model (LightGBM v2)

> **Model:** `customer_lgbm_v2` | **ROC-AUC:** 0.7529 | **Recall (Default):** 65%  
> **Nguồn importance:** LightGBM `feature_importances_` (split-based) trên test set  
> **Tổng số features:** 28 (27 numeric + 1 categorical)

---

## Phân hạng features hiện tại

Thang điểm importance: **Cực cao** ≥ 900 | **Cao** 400–899 | **Trung bình** 60–399 | **Thấp** < 60

---

### ⬛ Cực cao (importance ≥ 900)

| Feature | Importance | Nguồn dữ liệu | Có tại inference? | Mô tả |
|---------|-----------|--------------|:-----------------:|-------|
| `age_years` | 1344 | `application_train.csv` → DAYS_BIRTH | ❌ Median-fill | Tuổi khách hàng (ngày, chuyển đổi từ DAYS_BIRTH âm). Tuổi trẻ hơn → default rate cao hơn đáng kể |
| `credit_score` | 1266 | `application_train.csv` → EXT_SOURCE_2 | ✅ Có | Điểm tín dụng quy đổi 300–850 từ EXT_SOURCE_2. Feature quan trọng nhất **thực sự dùng được** tại inference |
| `ext_source_3` | 1183 | `application_train.csv` → EXT_SOURCE_3 | ❌ Median-fill | Điểm từ tổ chức tín dụng bên ngoài thứ 3. Rất predictive nhưng không thu thập tại inference |
| `loan_amount` | 1103 | Payload | ✅ Có | Số tiền vay gốc. Feature hạt nhân của bài toán cho vay |
| `ext_source_1` | 1092 | `application_train.csv` → EXT_SOURCE_1 | ❌ Median-fill | Điểm từ tổ chức tín dụng bên ngoài thứ 1. Tương tự ext_source_3 |

> ⚠️ **3/5 features cực cao bị median-fill tại inference** → AUC production thực tế thấp hơn 0.7529

---

### 🟫 Cao (importance 400–899)

| Feature | Importance | Nguồn dữ liệu | Có tại inference? | Mô tả |
|---------|-----------|--------------|:-----------------:|-------|
| `term` | 901 | Payload (tính từ AMT_CREDIT/AMT_ANNUITY) | ✅ Có | Số kỳ hạn trả nợ (tháng). Vay dài hạn hơn → risk tích lũy cao hơn |
| `dti` | 876 | Payload | ✅ Có | Debt-to-income ratio = monthly_payment / monthly_income. Chỉ số gánh nặng nợ cơ bản nhất |
| `loan_amount_to_income` | 717 | Tính từ payload | ✅ Có | loan_amount / (monthly_income × 12). Đo mức độ vay so với thu nhập năm |
| `num_bureau_records` | 618 | `bureau.csv` | ⚠️ Luôn = 0 | Số bản ghi tín dụng tại các ngân hàng khác. Nhiều hơn → lịch sử tín dụng phong phú hơn |
| `monthly_income` | 579 | Payload | ✅ Có | Thu nhập hàng tháng. Nền tảng tính khả năng trả nợ |
| `previous_default_rate` | 506 | DB (previous_applications) | ✅ Có | Tỉ lệ đơn vay trước bị từ chối/hủy. Proxy mạnh cho credit history |
| `num_previous_loans` | 495 | DB (previous_applications) | ✅ Có | Tổng số đơn vay từng nộp. Kinh nghiệm vay vốn của khách |

---

### 🟦 Trung bình (importance 60–399)

| Feature | Importance | Nguồn dữ liệu | Có tại inference? | Mô tả |
|---------|-----------|--------------|:-----------------:|-------|
| `num_active_credit` | 333 | `bureau.csv` | ⚠️ Luôn = 0 | Số khoản tín dụng đang active tại ngân hàng khác. Nhiều active credit → overleverage risk |
| `education_ordinal` | 214 | `application_train.csv` | ❌ Median-fill | Trình độ học vấn mã hóa 1–5. Học vấn cao hơn → thu nhập ổn định hơn → risk thấp hơn |
| `gender_male_flag` | 139 | `application_train.csv` | ❌ Median-fill | Giới tính (1=Nam, 0=Nữ). Trong HC dataset, nữ có default rate thấp hơn |
| `cnt_fam_members` | 115 | `application_train.csv` | ❌ Median-fill | Số thành viên gia đình. Gánh nặng gia đình ảnh hưởng khả năng trả nợ |
| `employment_status` | 100 | Payload | ✅ Có | Loại hình việc làm (Employed/Self-employed/Retired/Not employed/Other) |
| `is_married_flag` | 93 | `application_train.csv` | ❌ Median-fill | Tình trạng hôn nhân (1=Kết hôn). Ổn định gia đình liên quan đến ổn định tài chính |
| `is_homeowner` | 78 | Payload | ✅ Có | Có sở hữu bất động sản không. Tài sản thế chấp tiềm năng |
| `cnt_children` | 78 | `application_train.csv` | ❌ Median-fill | Số con. Gánh nặng nuôi con ảnh hưởng dòng tiền |
| `max_credit_overdue_days` | 71 | `bureau.csv` | ⚠️ Luôn = 0 | Số ngày quá hạn tệ nhất trong lịch sử bureau. Direct signal của bad payment behavior |
| `total_overdue_amount` | 63 | `bureau.csv` | ⚠️ Luôn = 0 | Tổng số tiền overdue trong bureau. Quy mô nợ xấu |

---

### 🟩 Thấp (importance < 60)

| Feature | Importance | Nguồn dữ liệu | Có tại inference? | Mô tả |
|---------|-----------|--------------|:-----------------:|-------|
| `income_verifiable_flag` | 28 | Tính từ payload | ✅ Có | 1 nếu Employed/Self-employed (thu nhập có thể xác minh) |
| `rating_ordinal` | 8 | Tính từ credit_score | ✅ Có | Xếp hạng 1–7 (HR→AA) từ credit_score. Redundant với credit_score, model học ít từ feature này |
| `listing_category` | 0 | Hardcoded = 1 | ❌ Mismatch | **⚠️ Zero variance trong training** (luôn = 1 với HC data). Mismatch với inference (1–8) |
| `has_bad_debt` | 0 | `bureau.csv` | ⚠️ Luôn = 0 | Flag có khoản "Bad debt" trong bureau. Zero variance vì 0 tại cả training lẫn inference |
| `high_dti_flag` | 0 | Tính từ dti | ✅ Có | 1 nếu dti > p75 training. Redundant với dti, model không học thêm được |
| `log_monthly_income` | 0 | Tính từ payload | ✅ Có | ln(1 + monthly_income). Redundant với monthly_income vì LightGBM không cần log transform |

---

## Features tiềm năng — Có khả năng tăng ROC-AUC + duy trì Recall

### Nhóm A — Từ `application_train.csv` (đã có trong Bronze, effort thấp nhất)

| Feature | Tên cột gốc | AUC gain ước tính | Lý do |
|---------|------------|:----------------:|-------|
| `def_30_cnt_social_circle` | `DEF_30_CNT_SOCIAL_CIRCLE` | ⭐⭐⭐ cao | Số người quen bị default 30 ngày — mạng xã hội chia sẻ rủi ro tài chính |
| `def_60_cnt_social_circle` | `DEF_60_CNT_SOCIAL_CIRCLE` | ⭐⭐⭐ cao | Tương tự nhưng ngưỡng 60 ngày — complementary signal |
| `amt_req_credit_bureau_year` | `AMT_REQ_CREDIT_BUREAU_YEAR` | ⭐⭐⭐ cao | Số lần hỏi credit bureau trong năm qua — hard inquiry count cao → đang cần tiền gấp |
| `amt_req_credit_bureau_qrt` | `AMT_REQ_CREDIT_BUREAU_QRT` | ⭐⭐ trung bình | Số lần hỏi bureau trong quý — trend gần hơn |
| `days_employed` | `DAYS_EMPLOYED` | ⭐⭐⭐ cao | Thâm niên làm việc — ổn định nghề nghiệp trực tiếp |
| `region_rating_client` | `REGION_RATING_CLIENT` | ⭐⭐ trung bình | Đánh giá rủi ro vùng 1/2/3 do Home Credit xếp hạng |
| `days_last_phone_change` | `DAYS_LAST_PHONE_CHANGE` | ⭐⭐ trung bình | Đổi SĐT gần đây → instability signal |
| `flag_own_car` | `FLAG_OWN_CAR` | ⭐ thấp | Có ô tô → tài sản bổ sung |
| `occupation_type` | `OCCUPATION_TYPE` | ⭐⭐ trung bình | 18 loại nghề — default rate khác biệt rõ theo nhóm (laborers vs managers) |

**Cách thêm vào:** Bổ sung vào `COLS` trong `etl/load_bronze.py` → thêm transform trong `database/transform_silver_homecredit.sql` → thêm pass-through trong Gold SQL → thêm vào `NUMERIC_FEATURES` trong training script.

---

### Nhóm B — Từ `previous_application.csv` (đã có trong Bronze, thêm aggregate trong Gold SQL)

| Feature aggregate | Cột gốc cần thêm | AUC gain ước tính | Lý do |
|------------------|-----------------|:----------------:|-------|
| `prev_avg_credit_ratio` | `AMT_APPLICATION`, `AMT_CREDIT` | ⭐⭐⭐ cao | mean(AMT_CREDIT / AMT_APPLICATION) — nếu < 1 → HC từng cắt giảm hạn mức → đã từng bị đánh giá là risk cao |
| `prev_high_yield_rate` | `NAME_YIELD_GROUP` | ⭐⭐⭐ cao | Tỉ lệ app trước ở nhóm lãi suất cao — HC tự xếp loại risk bằng yield |
| `days_since_last_app` | `DAYS_DECISION` | ⭐⭐ trung bình | -min(DAYS_DECISION) = số ngày từ lần nộp đơn gần nhất. Nộp liên tục → stress tài chính |
| `prev_avg_term` | `CNT_PAYMENT` | ⭐ thấp | Kỳ hạn trung bình các khoản vay trước |
| `prev_reject_reason_hc` | `CODE_REJECT_REASON` | ⭐⭐ trung bình | Tỉ lệ từng bị HC reject vì lý do nội bộ (HC = Home Credit reject) |

**Cách thêm vào:** Thêm cột vào `PREV_COLS` trong `etl/load_bronze.py` → mở rộng `prev_stats` CTE trong `database/transform_gold_homecredit.sql`.

---

### Nhóm C — Từ `bureau_balance.csv` (file mới, tác động lớn nhất)

> **27.3M rows** — join chain: `bureau_balance` → `bureau` (SK_ID_BUREAU) → `application` (SK_ID_CURR)

| Feature aggregate | Cách tính | AUC gain ước tính | Lý do |
|------------------|----------|:----------------:|-------|
| `max_dpd_status` | MAX(STATUS numeric) per customer | ⭐⭐⭐ cực cao | Mức quá hạn tệ nhất từng có trong lịch sử. STATUS=5 (120+ ngày) là dấu hiệu cực mạnh |
| `num_months_dpd_1plus` | COUNT(STATUS IN '1','2','3','4','5') | ⭐⭐⭐ cực cao | Tổng số tháng có quá hạn bất kỳ — tần suất vi phạm |
| `num_months_dpd_2plus` | COUNT(STATUS IN '2','3','4','5') | ⭐⭐⭐ cực cao | Số tháng quá hạn ≥ 31 ngày — serious delinquency |
| `pct_months_on_time` | COUNT(STATUS='0') / COUNT(*) | ⭐⭐⭐ cao | Tỉ lệ % tháng trả đúng hạn — payment discipline score |
| `has_recent_dpd_12m` | MAX(STATUS!='0' AND STATUS!='C' WHERE MONTHS_BALANCE >= -12) | ⭐⭐⭐ cao | Có quá hạn trong 12 tháng gần nhất — recency effect mạnh hơn lịch sử xa |

**Cách thêm vào:** Thêm load `bureau_balance.csv` vào `etl/load_bronze.py` → tạo thêm CTE `bureau_balance_stats` trong Gold SQL (join qua `bureau.csv`).

---

### Nhóm D — Từ `installments_payments.csv` (file mới, behavioral features)

> **13.6M rows** — join trực tiếp qua SK_ID_CURR

| Feature aggregate | Cách tính | AUC gain ước tính | Lý do |
|------------------|----------|:----------------:|-------|
| `avg_days_late` | mean(DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT) khi > 0 | ⭐⭐⭐ cao | Trung bình ngày trễ thanh toán tại HC — hành vi thanh toán thực tế |
| `max_days_late` | max(DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT) | ⭐⭐ trung bình | Lần trễ tệ nhất |
| `num_late_payments` | COUNT(DAYS_ENTRY_PAYMENT > DAYS_INSTALMENT) | ⭐⭐⭐ cao | Tổng số lần trễ — tần suất vi phạm tại HC |
| `avg_payment_ratio` | mean(AMT_PAYMENT / AMT_INSTALMENT) | ⭐⭐⭐ cao | < 1 = thường xuyên trả thiếu — trực tiếp predict default |
| `num_underpayments` | COUNT(AMT_PAYMENT < AMT_INSTALMENT × 0.95) | ⭐⭐ trung bình | Số lần trả thiếu 5%+ |
| `recent_late_count_12m` | COUNT late payments WHERE DAYS_INSTALMENT >= -365 | ⭐⭐⭐ cao | Số lần trễ trong 12 tháng gần nhất — recency |

**Cách thêm vào:** Thêm load `installments_payments.csv` vào `etl/load_bronze.py` → tạo CTE `installments_stats` trong Gold SQL.

---

### Nhóm E — Từ `credit_card_balance.csv` + `POS_CASH_balance.csv` (incremental)

| Feature aggregate | File | AUC gain | Lý do |
|------------------|------|:--------:|-------|
| `max_cc_dpd` | credit_card | ⭐⭐ trung bình | DPD tệ nhất trên thẻ tín dụng HC |
| `avg_cc_utilization` | credit_card | ⭐⭐ trung bình | AMT_BALANCE / AMT_CREDIT_LIMIT — credit utilization rate |
| `max_pos_dpd` | POS_CASH | ⭐ thấp | DPD tệ nhất trên khoản vay POS/tiền mặt |
| `num_pos_active` | POS_CASH | ⭐ thấp | Số khoản POS/cash đang còn dư |

---

## Tóm tắt AUC gain ước tính theo giai đoạn

| Giai đoạn | Nguồn | AUC hiện tại → dự kiến | Effort |
|-----------|-------|:---------------------:|--------|
| **Baseline** | v2 hiện tại | **0.7529** | — |
| **Phase 1** | + cols từ `application_train.csv` | → **~0.765** | Thấp |
| **Phase 2** | + better aggregates `previous_application.csv` | → **~0.775** | Thấp |
| **Phase 3** | + `bureau_balance.csv` | → **~0.790** | Trung bình |
| **Phase 4** | + `installments_payments.csv` | → **~0.805** | Trung bình |
| **Phase 5** | + `credit_card_balance` + `POS_CASH` | → **~0.815** | Trung bình |

> Benchmark: Top solutions HC Default Risk competition đạt **0.82–0.83** với đầy đủ 6 file CSV.
