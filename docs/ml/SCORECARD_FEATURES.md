# SCORECARD_FEATURES.md — LR Scorecard v3: Đặc trưng & Phân tích kết quả

> **Lưu ý 18/05/2026:** Tài liệu này là bản v3 legacy. Scorecard hiện tại dùng Stability v2, bỏ `credit_score_midpoint` và `rating_ordinal`, đồng thời train lại đạt ROC-AUC 0.7367. Xem `docs/migration_v2_summary.md` để lấy thông tin mới nhất.

> **Phiên bản model:** scorecard_v3 (Logistic Regression)
> **Ngày cập nhật:** Tháng 5 năm 2026
> **File artifact:** `machinelearning/ml/models/scorecard_model.pkl`
> **Script huấn luyện:** `machinelearning/ml/train_scorecard.py`
> **Dữ liệu (v2 / hiện hành):** 1,526,659 rows từ `gold.hc_features_v2` | Tỷ lệ vỡ nợ: 3.14%
> **ROC-AUC re-verified trên 305,332 test rows (2026-05-22):** **0.7367**
> **Score distribution v2:** min=300, max=850 (toán học); thực tế **99.92% rơi vào 500–669** (Fair + Good band)
> **Median:** 596 · **p5–p95:** 556–624 (phổ rất hẹp do default rate thấp 3.14%)
> **Khách hàng đạt ≥ 600:** 43.21% · **≥ 670:** 0.04% · **≥ 740:** <0.01%
>
> _(Số liệu cũ "300,360 rows · 8.07%" của v1 trong các section bên dưới được giữ làm tham chiếu lịch sử — không còn áp dụng cho production.)_

---

## Mục lục

1. [Tổng quan & Vai trò](#1-tổng-quan--vai-trò)
2. [Phương pháp FICO PDO](#2-phương-pháp-fico-pdo)
3. [Bảng đặc trưng (25 features)](#3-bảng-đặc-trưng-25-features)
4. [Phân tích đóng góp từng đặc trưng](#4-phân-tích-đóng-góp-từng-đặc-trưng)
5. [Kết quả huấn luyện](#5-kết-quả-huấn-luyện)
6. [Phân phối điểm thực tế](#6-phân-phối-điểm-thực-tế)
7. [Phân tích ngưỡng từ chối theo điểm](#7-phân-tích-ngưỡng-từ-chối-theo-điểm)
8. [Hành vi theo nhóm employment_status](#8-hành-vi-theo-nhóm-employment_status)
9. [So sánh với LightGBM v3](#9-so-sánh-với-lightgbm-v3)
10. [Hạn chế & Hướng cải thiện](#10-hạn-chế--hướng-cải-thiện)

---

## 1. Tổng quan & Vai trò

Scorecard **không** là mô hình phán quyết chính. Nó song song với LightGBM trong pipeline:

| Thành phần | Vai trò |
|-----------|---------|
| **LightGBM v3** | Phân loại rủi ro, AUTO_REJECT (P > 0.40), loan suggestion |
| **LR Scorecard v3** | Chuyển P(default) → điểm 300–850 để **hiển thị cho khách hàng** |

Lý do dùng LR cho scorecard:
- **Giải thích được**: mỗi feature có hệ số cố định → có thể giải thích "điểm của bạn thấp vì X"
- **Tuyến tính trong log-odds**: tương thích trực tiếp với công thức FICO PDO
- **Không dùng `class_weight="balanced"`**: để xác suất LR gần với tỷ lệ vỡ nợ thực (8%), giúp điểm FICO phân tán đúng

---

## 2. Phương pháp FICO PDO

### 2.1 Công thức

```
score = base_score - factor × (logit - base_logit)

factor     = PDO / ln(2)                     = 20 / 0.6931 = 28.854
base_logit = -ln(base_odds_good)             = -ln(50)     = -3.912
base_score = 600

logit = ln(P(default) / (1 - P(default)))   # từ output của LR

score ∈ [300, 850]  (clamp)
```

### 2.2 Tham số hiện tại

| Tham số | Giá trị | Ý nghĩa |
|---------|---------|---------|
| `base_score` | 600 | Điểm khi odds = 50:1 (P ≈ 2%) |
| `base_odds_good` | 50 | Tỷ lệ good:bad tham chiếu |
| `PDO` | 20 | Mỗi 20 điểm, odds tốt tăng gấp đôi |
| `factor` | 28.854 | Hệ số chuyển đổi logit → điểm |
| `score_min / max` | 300 / 850 | Khoảng cứng |

### 2.3 Bảng tra nhanh P(default) → Score

| P(default) | Score | Mức rủi ro |
|-----------|-------|-----------|
| 0.10 | 551 | Cao |
| 0.15 | 537 | Cao |
| 0.20 | 527 | Cao (ngưỡng LOW) |
| 0.25 | 519 | Cao |
| 0.30 | 512 | Rất cao |
| 0.35 | 505 | Rất cao |
| 0.40 | 499 | Rất cao (ngưỡng AUTO_REJECT) |
| 0.50 | 487 | Cực kỳ cao |

> **Nhận xét (số liệu lịch sử v1, 8.07% default rate):** Với tập dữ liệu Home Credit, điểm thực tế của phần lớn khách hàng rơi vào 471–676. Ngưỡng 600 trên lý thuyết tương đương P ≈ 2%, còn thực tế hiếm đạt được.
>
> **Cập nhật v2 (re-evaluated 2026-05-22):** Phân phối **dịch lên phía cao và hẹp lại** vì default rate giảm còn 3.14%. Thực tế **99.92% khách hàng rơi vào 500–669** (Fair + Good band):
> - Poor (300–499): chỉ 0.05% — default rate 13.1%
> - Fair (500–579): **23.74%** — default rate 7.66%
> - Good (580–669): **76.18%** — default rate 1.81%
> - Very Good (670–739): 0.03% — default rate 0%
> - Excellent + Exceptional: tổng <0.01%
>
> Ngưỡng **600 KHÔNG còn "hiếm đạt"**: **43.21% khách hàng đạt ≥ 600** trên v2. Ngược lại, ngưỡng **670 cực hiếm — chỉ 0.04%** (không tăng theo tỉ lệ như band Good).

---

## 3. Bảng đặc trưng (25 features)

### 3.1 Cấu hình pipeline

```
ColumnTransformer:
  ├── StandardScaler        → 23 numeric features
  └── OrdinalEncoder        → 2 categorical features
      (handle_unknown="use_encoded_value", unknown_value=-1)

LogisticRegression:
  C=0.1 (L2 regularization), max_iter=500, solver=lbfgs
  class_weight=None  ← quan trọng: KHÔNG dùng balanced
```

### 3.2 Nhóm A — Tài chính cá nhân (6 features)

| Feature | Hệ số LR | Điểm/std | Nguồn | Ý nghĩa |
|---------|----------|---------|-------|---------|
| `credit_score_midpoint` | **-0.504** | **+14.54** | Form → tính toán | Midpoint của dải FICO (300–850). Tín hiệu tổng hợp mạnh nhất |
| `loan_amount_to_income` | -0.068 | +1.96 | Form → tính toán | loan_amount / (monthly_income × 12). Thấp = an toàn |
| `rating_ordinal` | +0.040 | -1.16 | Form → tính toán | Điểm nội bộ 0–10. Cao → rủi ro (LR học nghịch chiều — xem mục 10) |
| `is_homeowner_flag` | +0.013 | -0.36 | Form | Sở hữu nhà. Hệ số dương bất thường — xem mục 10 |
| `income_verifiable_flag` | +0.191 | **-5.50** | Form | Không xác minh được thu nhập → rủi ro cao |
| `high_dti_flag` | +0.005 | -0.15 | Form → tính toán | DTI > 43%. Tín hiệu phụ (DTI liên tục đã trong feature khác) |

### 3.3 Nhóm B — Thu nhập & Nợ (3 features)

| Feature | Hệ số LR | Điểm/std | Nguồn | Ý nghĩa |
|---------|----------|---------|-------|---------|
| `debt_to_income_ratio` | +0.083 | -2.38 | Form → tính toán | DTI. Càng cao → càng mất điểm |
| `payment_to_income` | +0.083 | -2.38 | Form → tính toán | Số tiền trả nợ hàng tháng / thu nhập |
| `log_monthly_income` | +0.026 | -0.74 | Form → tính toán | Log tự nhiên thu nhập. Hệ số dương nhỏ — xem mục 10 |

### 3.4 Nhóm C — Lịch sử tín dụng (Bureau, 5 features)

| Feature | Hệ số LR | Điểm/std | Nguồn | Ý nghĩa |
|---------|----------|---------|-------|---------|
| `num_bureau_records` | **-0.264** | **+7.62** | DB bureau | Số hồ sơ tín dụng. Nhiều = lịch sử lâu dài = tốt hơn |
| `num_active_credit` | **+0.393** | **-11.33** | DB bureau | Số khoản đang vay. Quá nhiều = rủi ro cao nhất trong model |
| `total_overdue_amount` | +0.013 | -0.39 | DB bureau | Tổng số tiền quá hạn (USD) |
| `max_credit_overdue_days` | +0.013 | -0.36 | DB bureau | Ngày quá hạn tệ nhất trong lịch sử |
| `has_bad_debt` | +0.008 | -0.23 | DB bureau | Có nợ xấu. Hệ số nhỏ — xem mục 10 |

### 3.5 Nhóm D — Lịch sử trong hệ thống CreditIntel (2 features)

| Feature | Hệ số LR | Điểm/std | Nguồn | Ý nghĩa |
|---------|----------|---------|-------|---------|
| `num_previous_loans` | -0.086 | +2.48 | DB internal | Số đơn vay trước. Nhiều = đã trải qua thẩm định thành công |
| `previous_default_rate` | +0.199 | -5.75 | DB internal | Tỷ lệ đơn bị AUTO_REJECT trước đây. Tín hiệu mạnh thứ 3 |

### 3.6 Nhóm E — Nhân khẩu học (7 features)

| Feature | Hệ số LR | Điểm/std | Nguồn | Ý nghĩa |
|---------|----------|---------|-------|---------|
| `age_years` | -0.125 | +3.61 | Form | Tuổi. Nhiều tuổi hơn → ổn định tài chính hơn |
| `years_employed` | **-0.239** | **+6.90** | Form → tính toán | Năm kinh nghiệm. Thâm niên = thu nhập ổn định |
| `education_ordinal` | **-0.208** | **+6.01** | Form | Học vấn (1=Tiểu học → 5=Sau đại học) |
| `gender_male_flag` | +0.150 | -4.32 | Form | Nam trong dataset HC có rủi ro vỡ nợ cao hơn |
| `is_married_flag` | -0.052 | +1.49 | Form | Đã kết hôn → thu nhập kép |
| `cnt_children` | +0.011 | -0.32 | Form | Số con. Ít ảnh hưởng |
| `cnt_fam_members` | -0.017 | +0.48 | Form | Số người trong gia đình. Tương quan ngược với cnt_children |

### 3.7 Nhóm F — Việc làm (2 features categorical)

| Feature | Hệ số LR | Điểm/std | Nguồn | Ý nghĩa |
|---------|----------|---------|-------|---------|
| `employment_status_grouped` | -0.028 | +0.81 | Form | Nhóm trạng thái việc làm (5 nhóm, xem mục 8) |
| `occupation_type` | +0.001 | -0.04 | Form | Nghề nghiệp (19 loại). Gần như không ảnh hưởng — LR không phân biệt được các nhóm tốt qua 1 chiều ordinal |

---

## 4. Phân tích đóng góp từng đặc trưng

### 4.1 Xếp hạng theo mức độ ảnh hưởng (|điểm/std|)

```
Tác động TÍCH CỰC (tăng điểm ↑)           Tác động TIÊU CỰC (giảm điểm ↓)
─────────────────────────────────────      ──────────────────────────────────
credit_score_midpoint  +14.54 / std        num_active_credit    -11.33 / std
num_bureau_records      +7.62 / std        income_verifiable_flag -5.50 / std
years_employed          +6.90 / std        previous_default_rate  -5.75 / std
education_ordinal       +6.01 / std        gender_male_flag       -4.32 / std
age_years               +3.61 / std        debt_to_income_ratio   -2.38 / std
num_previous_loans      +2.48 / std        payment_to_income      -2.38 / std
loan_amount_to_income   +1.96 / std        rating_ordinal         -1.16 / std
is_married_flag         +1.49 / std        log_monthly_income     -0.74 / std
employment_status_grouped +0.81 / std      total_overdue_amount   -0.39 / std
cnt_fam_members         +0.48 / std        is_homeowner_flag      -0.36 / std
                                           max_credit_overdue_days -0.36 / std
                                           has_bad_debt           -0.23 / std
                                           cnt_children           -0.32 / std
                                           high_dti_flag          -0.15 / std
                                           occupation_type        -0.04 / std
```

### 4.2 Top 5 tăng điểm mạnh nhất

1. **credit_score_midpoint (+14.54/std)** — Điểm FICO đầu vào cao → xác suất vỡ nợ thấp → điểm scorecard cao. Std = 122.5 điểm, nên 1 std-dev tăng = ~15 điểm scorecard.
2. **num_bureau_records (+7.62/std)** — Có lịch sử tín dụng phong phú (nhiều hồ sơ) là tín hiệu tích cực. Std ≈ 4.5 hồ sơ.
3. **years_employed (+6.90/std)** — Thâm niên làm việc cao. Std ≈ 6.3 năm, nên 6 năm thêm = ~7 điểm scorecard.
4. **education_ordinal (+6.01/std)** — Mỗi bậc học (1–5) ứng với ~4 điểm scorecard.
5. **age_years (+3.61/std)** — Mỗi 12 năm tuổi (1 std) thêm ≈ 3.6 điểm.

### 4.3 Top 3 giảm điểm mạnh nhất

1. **num_active_credit (-11.33/std)** — Feature tác động mạnh nhất theo chiều ngược. Đang vay 2 nơi đồng thời (≈ 1 std từ 1.77) → mất ~11 điểm.
2. **income_verifiable_flag (-5.50/std)** — Là binary (0/1), nên hệ số = toàn bộ ảnh hưởng khi không xác minh được thu nhập.
3. **previous_default_rate (-5.75/std)** — Từng bị AUTO_REJECT 1/4 số đơn (std≈0.26) → mất ~1.5 điểm mỗi % tăng thêm.

---

## 5. Kết quả huấn luyện

### 5.1 Cấu hình huấn luyện

| Tham số | Giá trị |
|---------|---------|
| Algorithm | Logistic Regression (scikit-learn) |
| Regularization | L2 (Ridge), C=0.1 |
| max_iter | 500 |
| solver | lbfgs |
| class_weight | None (không balanced) |
| Preprocessing numeric | StandardScaler |
| Preprocessing categorical | OrdinalEncoder (unknown_value=-1) |
| Train/Test split | 80% / 20% stratified (random_state=42) |
| Train rows | 240,288 |
| Test rows | 60,072 |
| Missing value fill | Median (numeric), "Other/Unknown" (categorical) |

### 5.2 Chỉ số đánh giá (test set)

| Chỉ số | Giá trị | Ghi chú |
|--------|---------|--------|
| **ROC-AUC** | **0.7110** | Đo khả năng phân biệt rủi ro |
| Accuracy | 0.92 | Cao nhưng misleading (class imbalance) |
| **Score range thực tế** | **471 – 676** | Hẹp hơn nhiều so với lý thuyết 300–850 |
| Score mean | 564 | Phần lớn nằm ở vùng "kém – trung bình thấp" |
| Score median | 566 | |
| Score std | 22.4 | Rất hẹp — xem mục 6 |

### 5.3 Báo cáo phân loại ở ngưỡng P=0.5 (mặc định)

| Nhãn | Precision | Recall | F1 |
|------|-----------|--------|-----|
| No Default | 0.92 | 1.00 | 0.96 |
| **Default** | **0.44** | **0.00** | **0.00** |

> **Lý giải:** Ở ngưỡng 0.5, LR không dự báo được default nào. Đây là hệ quả tất yếu khi không dùng `class_weight="balanced"` và default rate chỉ 8%. Đây là đánh đổi **chủ ý**: ưu tiên xác suất calibrated đúng để FICO score có ý nghĩa thực tế.

### 5.4 Báo cáo phân loại ở ngưỡng P=0.2 (ngưỡng LOW)

| Nhãn | Precision | Recall | F1 |
|------|-----------|--------|-----|
| No Default | 0.93 | 0.95 | 0.94 |
| **Default** | **0.27** | **0.19** | **0.22** |

> Ở ngưỡng LOW (P=0.20, score ≈ 527), recall vẫn chỉ đạt 19%. Dùng LightGBM cho quyết định phán quyết, không phải scorecard.

---

## 6. Phân phối điểm thực tế

### 6.1 Khoảng điểm thực so với lý thuyết

| Thông số | Lý thuyết | Thực tế (test set) |
|---------|-----------|-------------------|
| Khoảng | 300 – 850 | **471 – 676** |
| Trung bình | 600 (base) | **564** |
| Median | — | **566** |
| Std | — | **22.4** |

**Nguyên nhân khoảng hẹp:**
- Regularization L2 mạnh (C=0.1) giữ hệ số nhỏ, hạn chế log-odds dao động lớn
- Phần lớn khách hàng có P(default) trong khoảng 5%–25%, tương ứng score 527–553
- Ít khách hàng ở đuôi (P<2% hoặc P>40%) để có điểm cực đoan

### 6.2 Phân phối theo dải điểm FICO

| Dải điểm | Nhãn | Số khách (test) | Tỷ lệ | Default rate |
|----------|------|-----------------|-------|-------------|
| 300–579 | Kém | 44,521 | **74.1%** | 9.97% |
| 580–669 | Trung bình thấp | 15,550 | **25.9%** | 2.62% |
| 670–739 | Trung bình | 1 | ~0% | 0.00% |
| 740–799 | Tốt | 0 | 0% | — |
| 800–850 | Xuất sắc | 0 | 0% | — |

> **Quan trọng:** Với dữ liệu Home Credit, 74% khách hàng có điểm < 580 theo model này. Dải "Tốt" và "Xuất sắc" **gần như không thể đạt được** trừ khi bổ sung thêm dữ liệu ngoài (xem mục 10). Cần điều chỉnh `base_score` hoặc `base_odds_good` khi deploy production.

### 6.3 Mối quan hệ điểm – xác suất vỡ nợ

```
Score 471 → P(default) ≈ 56%  (rủi ro cực kỳ cao)
Score 487 → P(default) ≈ 50%
Score 499 → P(default) ≈ 40%  ← ngưỡng AUTO_REJECT
Score 527 → P(default) ≈ 20%  ← ngưỡng LOW
Score 551 → P(default) ≈ 10%
Score 564 → P(default) ≈  8%  ← trung bình tập dữ liệu
Score 600 → P(default) ≈  2%  ← base_score lý thuyết
Score 676 → P(default) ≈  0.3%
```

---

## 7. Phân tích ngưỡng từ chối theo điểm

Bảng dưới đây cho thấy nếu từ chối tất cả hồ sơ có score < ngưỡng:

| Ngưỡng | % bị từ chối | % default bị bắt | Nhận xét |
|--------|-------------|-----------------|---------|
| score < 500 | 0.3% | 1.5% | Quá ít — hầu hết pass |
| score < 520 | 3.0% | 11.7% | Chỉ bắt được 1/10 vỡ nợ |
| score < 540 | 13.8% | 35.1% | Bắt được 1/3 vỡ nợ |
| **score < 560** | **39.4%** | **67.4%** | Cân bằng tốt |
| score < 580 | 74.1% | 91.6% | Từ chối 3/4 tất cả đơn |
| score < 600 | 95.3% | 98.9% | Gần như từ chối tất cả |
| score < 620 | 99.6% | 99.9% | Không còn ý nghĩa thực tế |

> **Khuyến nghị:** Nếu dùng scorecard để từ chối độc lập (không có LightGBM), ngưỡng score < 560 là điểm cân bằng tốt nhất. Tuy nhiên, hệ thống hiện tại đúng đắn hơn khi dùng **LightGBM** để AUTO_REJECT và scorecard chỉ để **hiển thị điểm số** cho khách hàng.

---

## 8. Hành vi theo nhóm employment_status

| Nhóm | Số mẫu | Tỷ lệ vỡ nợ | Đóng góp điểm |
|------|--------|------------|--------------|
| Not employed | 30 | **16.7%** | Thấp nhất |
| Employed | 176,575 | 9.1% | Trung bình |
| Other/Unknown | 13 | 7.7% | Trung bình |
| Self-employed | 70,591 | 7.5% | Tốt hơn |
| **Retired** | 53,151 | **5.3%** | Tốt nhất |

> Người về hưu (Retired) có tỷ lệ vỡ nợ thấp nhất — thu nhập hưu trí ổn định, không phụ thuộc thị trường lao động. LR gán hệ số -0.028 cho nhóm này (sau OrdinalEncoding).

---

## 9. So sánh với LightGBM v3

| Tiêu chí | LightGBM v3 | LR Scorecard v3 |
|---------|-------------|----------------|
| **ROC-AUC** | **0.7306** | 0.7110 |
| Số features | 28 | **25** |
| Recall default (P=0.40) | **73.76%** | ~0% |
| Recall default (P=0.20) | 94.22% | 19% |
| Interpretability | Thấp (cây quyết định) | **Cao (tuyến tính)** |
| Hỗ trợ non-linear | **Có** | Không |
| Feature interaction | **Có** | Không |
| Mục đích chính | AUTO_REJECT + Risk level | **Điểm 300–850** |
| Output quan trọng | risk_level, recommended_amount | **risk_score** |
| Sử dụng trong API | `ml_service.predict()` | `credit_score_service.compute()` |

**Sự khác biệt 3 features (25 vs 28):**
Scorecard loại bỏ 3 features so với LightGBM:
- `listing_category` — gain LightGBM = 0, ít ý nghĩa
- `has_bad_debt` → vẫn có trong scorecard (coef +0.008, nhỏ)
- Thực tế: cả 2 model dùng cùng 25 numeric features; scorecard thêm `employment_status_grouped` và `occupation_type` thay vì `listing_category`

---

## 10. Hạn chế & Hướng cải thiện

### 10.1 Hạn chế hiện tại

| Vấn đề | Biểu hiện | Nguyên nhân |
|--------|-----------|------------|
| **Khoảng điểm quá hẹp** | Chỉ 471–676 thay vì 300–850 | C=0.1 regularize mạnh; data imbalanced |
| **Hệ số bất thường** | `log_monthly_income` dương (+0.026), `is_homeowner_flag` dương (+0.013), `rating_ordinal` dương (+0.040) | Multicollinearity: các feature tương quan cao khiến LR phân bổ hệ số sai chiều |
| **occupation_type gần vô nghĩa** | Điểm/std = -0.04 | OrdinalEncoder mã hóa 19 nghề thành 1 con số → mất thông tin phân loại |
| **Recall default ≈ 0 ở P=0.5** | Model không dự báo được default | Không dùng class_weight, xác suất hiếm khi vượt 0.5 |
| **Phụ thuộc vào credit_score_midpoint** | 1 feature chiếm 14.54/std, gấp đôi feature tiếp theo | Feature này đã là tổng hợp của nhiều thông tin |

### 10.2 Hướng cải thiện ngắn hạn

| Thay đổi | Tác động dự kiến | Phức tạp |
|---------|-----------------|---------|
| **Tăng C** (0.1 → 0.5–1.0) | Mở rộng khoảng điểm; hệ số phản ánh thực hơn | Thấp |
| **Điều chỉnh base_score** (600 → 500) hoặc **PDO** (20 → 30) | Dịch chuyển điểm thực tế vào dải 500–700 | Thấp |
| **Thay OrdinalEncoder bằng OneHotEncoder** cho occupation_type | Cho phép LR phân biệt từng nghề | Trung bình |
| **Thêm feature cross** (`credit_score × num_active_credit`) | Bắt interaction mà LR đang bỏ sót | Trung bình |
| **Target encoding** cho occupation_type (mean default rate) | Tốt hơn OrdinalEncoding về thứ tự | Trung bình |
| **WOE binning** cho features liên tục | Tiêu chuẩn scorecard ngân hàng truyền thống | Cao |

### 10.3 Hướng cải thiện dài hạn (từ CSV bổ sung)

Theo `docs/ml/ML_FEATURES.md` mục 5, bổ sung features từ:
- `installments_payments.csv` → `avg_payment_delay_days`, `late_payment_rate` → est. +0.02–0.03 AUC
- `previous_application.csv` → `prev_approval_rate`, `days_since_last_app` → est. +0.015–0.025 AUC
- `bureau_balance.csv` → `bureau_recent_dpd_3m` → est. +0.01–0.02 AUC

Với P1+P2, scorecard ước tính đạt ROC-AUC **0.73–0.75** (tương đương LightGBM hiện tại).

---

## Phụ lục: Hệ số đầy đủ từ model

```
Intercept: -2.6539

Feature                   Coef      Điểm/std
─────────────────────────────────────────────
credit_score_midpoint   -0.5040    +14.54  ← tích cực mạnh nhất
num_bureau_records      -0.2640     +7.62
years_employed          -0.2392     +6.90
education_ordinal       -0.2083     +6.01
age_years               -0.1251     +3.61
num_previous_loans      -0.0858     +2.48
loan_amount_to_income   -0.0680     +1.96
is_married_flag         -0.0515     +1.49
employment_status_grp   -0.0281     +0.81
cnt_fam_members         -0.0168     +0.48
occupation_type         +0.0014     -0.04
high_dti_flag           +0.0051     -0.15
has_bad_debt            +0.0081     -0.23
cnt_children            +0.0110     -0.32
is_homeowner_flag       +0.0126     -0.36
max_credit_overdue_days +0.0126     -0.36
total_overdue_amount    +0.0134     -0.39
log_monthly_income      +0.0257     -0.74
rating_ordinal          +0.0403     -1.16
debt_to_income_ratio    +0.0826     -2.38
payment_to_income       +0.0826     -2.38
gender_male_flag        +0.1497     -4.32
income_verifiable_flag  +0.1907     -5.50
previous_default_rate   +0.1994     -5.75
num_active_credit       +0.3927    -11.33  ← tiêu cực mạnh nhất
```
