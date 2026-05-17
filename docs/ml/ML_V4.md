# Tài liệu ML Pipeline v4 — Mô hình Chấm điểm Tín dụng Hai Giai đoạn

## 1. Tổng quan

### Vấn đề của v3

Trong v3, form đơn vay yêu cầu người dùng tự nhập `credit_score`. Điểm này sau đó được đưa thẳng vào Stage 1 (Scorecard) với hệ số lớn nhất (+14,5 pts/std), tức là model chỉ "echo" lại số mà người dùng tự điền — không phải tính toán độc lập. Ngoài ra, `high_dti_flag` luôn bằng 0 tại inference do form nhận DTI dạng 0–1 nhưng ngưỡng HC-style p75 = 2,683.

### Giải pháp v4 — Pipeline hai giai đoạn

```
Người dùng nộp form (không nhập credit_score, không nhập DTI)
        │
        ▼
  Stage 1: Scorecard LR (22 features)
        │  → Tính credit_score_computed (thang điểm FICO 300–850)
        │  → Xác suất vỡ nợ sơ bộ P₁
        ▼
  Stage 2: LightGBM (26 features)
        │  → credit_score_computed từ Stage 1 là một trong các features
        │  → Xác suất vỡ nợ cuối P₂
        │  → Mức rủi ro: Thấp / Trung bình / Cao
        ▼
  Kết quả trả về người dùng:
    - credit_score_computed (Stage 1 tính)
    - default_probability   (Stage 2 tính)
    - suggested_amount + suggested_term
```

**Điểm khác biệt cốt lõi so với v3:**

| Hạng mục | v3 | v4 |
|----------|----|----|
| Nguồn credit_score | Người dùng tự nhập | Stage 1 tính độc lập từ 22 features |
| DTI | Người dùng nhập (0–1) | Tự tính HC-style: `(loan_amount/term)/monthly_income` |
| Kiến trúc | Scorecard + LightGBM độc lập | Hai giai đoạn nối tiếp (Stage 1 → Stage 2) |
| Loan purpose | Không có | Dropdown 7 lựa chọn → sinh `loan_type` |

---

## 2. Stage 1 — Scorecard Logistic Regression

**File train:** [machinelearning/ml/train_scorecard.py](../../machinelearning/ml/train_scorecard.py)  
**Artifact:** `machinelearning/ml/models/scorecard_model.pkl`  
**OOF output:** `machinelearning/ml/models/oof_stage1.csv`  
**Model version:** `scorecard_lr_v4`

### Mục tiêu

Stage 1 đóng vai trò **Scorecard độc lập**: nhận các thông tin tài chính và nhân khẩu học thô từ form, tính toán xác suất vỡ nợ P₁, rồi quy đổi sang thang điểm FICO 300–850 (`credit_score_computed`). Điểm này phản ánh mức độ tín nhiệm của khách hàng mà **không** dựa vào bất kỳ thông tin tự khai nào về điểm tín dụng.

### Danh sách features (22 features)

#### Nhóm A — Thông tin khoản vay & thu nhập (4 features)

| Feature | Cách tính | Vai trò trong Stage 1 |
|---------|-----------|----------------------|
| `debt_to_income_ratio` | `(loan_amount / term) / monthly_income` (HC-style) | Đo gánh nặng trả nợ hàng tháng so với thu nhập; ngưỡng HC p75 ≈ 2,683 |
| `loan_amount_to_income` | `loan_amount / (monthly_income × 12)` | Đo tổng khoản vay so với thu nhập năm; phát hiện vay quá khả năng |
| `log_monthly_income` | `ln(1 + monthly_income)` | Log-transform để giảm skew của thu nhập; giúp LR hội tụ tốt hơn |
| `high_dti_flag` | `1` nếu HC-DTI > 2,683 (p75 tập train) | Flag nhị phân báo hiệu DTI vượt ngưỡng rủi ro trung vị cộng đồng |

> **Lưu ý quan trọng:** `debt_to_income_ratio` và `high_dti_flag` đều dùng HC-style DTI, **không** phải giá trị DTI người dùng nhập. Tại inference, backend tự tính: `(loan_amount / term) / monthly_income`.

#### Nhóm B — Lịch sử tín dụng (4 features)

| Feature | Nguồn | Vai trò trong Stage 1 |
|---------|-------|----------------------|
| `num_previous_loans` | DB (đơn vay cũ đã duyệt) | Khách hàng có nhiều lịch sử vay → LR đánh giá thấp rủi ro hơn (tín hiệu tích lũy tín dụng) |
| `previous_default_rate` | DB (tỷ lệ đơn bị từ chối / tổng đơn cũ) | Tỷ lệ từ chối cao → rủi ro cao; feature quan trọng phản ánh lịch sử trực tiếp |
| `num_bureau_records` | Form | Số lần tra cứu tín dụng tích lũy → nhiều hơn thường tốt (tín dụng lâu năm); đóng góp +8,06 pts/std |
| `num_active_credit` | Form | Số dòng tín dụng đang mở; đóng góp −11,66 pts/std — feature có tác động âm mạnh nhất |

#### Nhóm C — Hành vi tín dụng xấu (2 features)

| Feature | Nguồn | Vai trò trong Stage 1 |
|---------|-------|----------------------|
| `total_overdue_amount` | Form | Tổng dư nợ quá hạn (USD); càng cao → điểm càng thấp |
| `max_credit_overdue_days` | Form | Số ngày quá hạn tệ nhất; phản ánh mức độ nghiêm trọng của vi phạm tín dụng trong quá khứ |

#### Nhóm D — Thông tin việc làm (2 features)

| Feature | Nguồn | Vai trò trong Stage 1 |
|---------|-------|----------------------|
| `years_employed` | Form | Thâm niên làm việc; đóng góp +7,20 pts/std — tín hiệu ổn định thu nhập mạnh |
| `income_verifiable_flag` | Form (checkbox) | 1 = có nguồn thu nhập xác minh được; xác minh thu nhập giảm bất định cho LR |

#### Nhóm E — Nhân khẩu học (6 features)

| Feature | Nguồn | Vai trò trong Stage 1 |
|---------|-------|----------------------|
| `age_years` | Form | Tuổi tác; đóng góp +6,23 pts/std — người lớn tuổi thường ổn định tài chính hơn |
| `gender_male_flag` | Form | 1 = nam; đóng góp −4,10 pts/std (dữ liệu HC: nam có tỷ lệ vỡ nợ cao hơn nữ nhẹ) |
| `education_ordinal` | Form | 1 (Tiểu học) → 5 (Học vị); đóng góp +6,85 pts/std — học vấn cao gắn với thu nhập ổn định |
| `cnt_children` | Form | Số con; nhiều con → gánh nặng tài chính hộ gia đình tăng |
| `cnt_fam_members` | Form | Tổng thành viên gia đình; bổ sung ngữ cảnh chi tiêu hộ gia đình |
| `is_married_flag` | Form | 1 = đã kết hôn; thường kèm theo ổn định thu nhập đôi |

#### Nhóm F — Tài sản & Loại khoản vay (2 features)

| Feature | Nguồn | Vai trò trong Stage 1 |
|---------|-------|----------------------|
| `is_homeowner_flag` | Form | 1 = có nhà; tài sản thế chấp tiềm năng, tín hiệu ổn định tài chính |
| `loan_type` | Từ `loan_purpose` (form) | 1 = Cash, 0 = Revolving; vay tiền mặt có rủi ro cao hơn (−3,75 pts/std) |

#### Nhóm G — Categorical (2 features)

| Feature | Encoder | Vai trò trong Stage 1 |
|---------|---------|----------------------|
| `employment_status_grouped` | OrdinalEncoder | Phân nhóm trạng thái việc làm (Employed / Self-employed / Retired / Not employed / Other / Unknown); LR dùng thứ tự để ước lượng rủi ro tương đối |
| `occupation_type` | **TargetEncoder** | Mã hóa theo tỷ lệ vỡ nợ trung bình của từng ngành nghề (19 nhóm HC); giúp LR gán hệ số có ý nghĩa — tốt hơn OrdinalEncoder vì LR nhạy cảm với thứ tự tùy tiện |

> **Tại sao dùng TargetEncoder cho `occupation_type` ở Stage 1?**  
> OrdinalEncoder gán số nguyên tùy ý (ví dụ: IT=3, Nông dân=7) → LR gán hệ số gần 0 vì không có thứ tự thực sự. TargetEncoder thay thế bằng tỷ lệ vỡ nợ trung bình của từng ngành → LR nhận được giá trị liên tục có ý nghĩa thực sự.

### Preprocessing pipeline (Stage 1)

```python
ColumnTransformer([
    ("num",     StandardScaler(),                                  NUMERIC_FEATURES_20),
    ("cat_emp", OrdinalEncoder(handle_unknown="use_encoded_value"), ["employment_status_grouped"]),
    ("cat_occ", TargetEncoder(target_type="binary"),               ["occupation_type"]),
])
→ LogisticRegression(C=0.1, max_iter=500)
```

### Công thức FICO PDO — Quy đổi xác suất → điểm

```
logit = ln(P(vỡ nợ) / (1 − P(vỡ nợ)))
score = 600 − 28,854 × (logit − (−3,912))
score = clip(round(score), 300, 850)
```

| Tham số | Giá trị | Ý nghĩa |
|---------|---------|---------|
| base_score | 600 | Điểm chuẩn tại odds tốt = 50:1 |
| PDO | 20 | Mỗi tăng 20 điểm → odds tốt tăng gấp đôi |
| factor | 28,854 | PDO / ln(2) |
| base_logit | −3,912 | logit tương ứng odds 50:1 |

### Kết quả huấn luyện Stage 1

| Chỉ số | Giá trị |
|--------|---------|
| OOF AUC (5-fold KFold) | **0,6738** |
| Held-out AUC | **0,6821** |
| Khoảng điểm (OOF) | 422 – 723 |
| Tập dữ liệu | 300.360 dòng, tỷ lệ vỡ nợ 8,07% |

**Đóng góp của các features chính (pts/std):**

| Feature | pts/std | Chiều tác động |
|---------|---------|---------------|
| `num_active_credit` | −11,66 | Nhiều tín dụng đang mở → rủi ro cao |
| `num_bureau_records` | +8,06 | Nhiều bản ghi tín dụng → rủi ro thấp |
| `years_employed` | +7,20 | Thâm niên cao → rủi ro thấp |
| `education_ordinal` | +6,85 | Học vấn cao → rủi ro thấp |
| `age_years` | +6,23 | Lớn tuổi hơn → rủi ro thấp |
| `previous_default_rate` | −6,11 | Nhiều lịch sử từ chối → rủi ro cao |
| `gender_male_flag` | −4,10 | Nam → rủi ro cao hơn nhẹ (dữ liệu HC) |
| `loan_type` | −3,75 | Vay tiền mặt → rủi ro cao hơn Revolving |

> **Ghi chú về `occupation_type`:** pts/std hiển thị rất lớn (−69,66) do TargetEncoder xuất ra phạm vi ~0,05 std, không qua StandardScaler → hệ số LR phải bù bằng cách phóng to. Dự đoán của model **hoàn toàn đúng**; chỉ số pts/std của riêng feature này bị misleading về mặt hiển thị.

---

## 3. Stage 2 — Customer Risk Model LightGBM

**File train:** [machinelearning/ml/retrain_customer_model.py](../../machinelearning/ml/retrain_customer_model.py)  
**Artifact:** `machinelearning/ml/models/customer_risk_model.pkl`  
**Model version:** `customer_lgbm_v4`

### Mục tiêu

Stage 2 là **model rủi ro toàn diện**: nhận toàn bộ thông tin của khách hàng cộng thêm `credit_score_computed` từ Stage 1, dự đoán xác suất vỡ nợ cuối cùng P₂ và phân loại mức rủi ro. LightGBM phù hợp hơn LR ở đây vì có thể bắt các tương tác phi tuyến giữa các feature.

### Danh sách features (26 features)

Stage 2 kế thừa toàn bộ 20 numeric features của Stage 1, bổ sung thêm 6 features mới, và dùng OrdinalEncoder (thay vì TargetEncoder) cho `occupation_type` vì LightGBM không cần encoding có ý nghĩa thứ tự.

#### Nhóm A — Thông số khoản vay thô (3 features — MỚI so với Stage 1)

| Feature | Cách tính | Vai trò trong Stage 2 |
|---------|-----------|----------------------|
| `monthly_income` | Từ form (raw) | LightGBM khai thác trực tiếp; tương tác với loan_amount để phát hiện vay vượt khả năng |
| `loan_amount` | Từ form (raw) | Feature có importance cao (#2: 3.101); số tiền vay tuyệt đối là tín hiệu rủi ro mạnh |
| `term` | Từ form (raw) | Kỳ hạn (tháng); tương tác với loan_amount trong các ngưỡng phi tuyến |

> Stage 1 dùng các tỷ số (`debt_to_income_ratio`, `loan_amount_to_income`) thay vì giá trị thô để LR không bị ảnh hưởng bởi đơn vị đo. Stage 2 (LightGBM) dùng cả thô lẫn tỷ số vì tree models tự tìm ngưỡng tốt nhất.

#### Nhóm B — DTI (1 feature — đổi tên so với Stage 1)

| Feature | Cách tính | Vai trò trong Stage 2 |
|---------|-----------|----------------------|
| `dti` | `(loan_amount / term) / monthly_income` (HC-style, giống Stage 1) | Cùng giá trị với `debt_to_income_ratio` ở Stage 1 nhưng đổi tên để khớp naming convention Stage 2; importance #5: 2.865 |

#### Nhóm C — Điểm tín dụng từ Stage 1 (1 feature — KEY feature)

| Feature | Nguồn | Vai trò trong Stage 2 |
|---------|-------|----------------------|
| `credit_score_computed` | **OOF output của Stage 1** (300–850) | Importance #3: 2.898 — tóm tắt toàn bộ thông tin tín dụng của Stage 1 vào một số; Stage 2 dùng nó như một "prior" độc lập để kết hợp với thông tin khoản vay |

> **Tại sao dùng OOF thay vì predict trực tiếp?**  
> Nếu Stage 1 predict trên toàn bộ tập train rồi Stage 2 học từ đó → Stage 1 đã "thấy" dữ liệu khi predict → leakage. OOF đảm bảo mỗi dự đoán được tạo ra bởi Stage 1 **chưa thấy** điểm dữ liệu đó khi train.

#### Nhóm D — Loại khoản vay (1 feature — giống Stage 1)

| Feature | Nguồn | Vai trò trong Stage 2 |
|---------|-------|----------------------|
| `loan_type` | Từ `loan_purpose` (form) | LightGBM có thể khai thác tương tác: Cash + DTI cao = rủi ro rất cao; Revolving + income thấp = pattern khác |

#### Nhóm E — Toàn bộ 20 numeric features từ Stage 1

Stage 2 kế thừa nguyên vẹn tất cả features trong nhóm A–F của Stage 1 (xem Mục 2). Vai trò của chúng trong Stage 2 được LightGBM tái đánh giá theo importance phi tuyến, không dùng hệ số LR.

| Feature | Importance Stage 2 (#) |
|---------|------------------------|
| `age_years` | **#1: 3.518** |
| `loan_amount` | **#2: 3.101** |
| `credit_score_computed` | **#3: 2.898** |
| `years_employed` | **#4: 2.871** |
| `dti` | **#5: 2.865** |

#### Nhóm F — Categorical (2 features — đổi encoder so với Stage 1)

| Feature | Encoder | Vai trò trong Stage 2 |
|---------|---------|----------------------|
| `employment_status` | OrdinalEncoder | LightGBM tự tìm splits tốt nhất theo từng giá trị → OrdinalEncoder đủ dùng |
| `occupation_type` | OrdinalEncoder (19 categories) | Không cần TargetEncoder vì LightGBM không nhạy cảm với thứ tự tùy tiện như LR |

### Ngưỡng phân loại rủi ro (Stage 2)

| P₂ (xác suất vỡ nợ) | Mức rủi ro | Kết quả |
|---------------------|------------|---------|
| < 0,20 | **Low** | PENDING_REVIEW |
| 0,20 – 0,40 | **Medium** | PENDING_REVIEW |
| > 0,40 | **High** | AUTO_REJECTED (lưu DB ngay) |

### Kết quả huấn luyện Stage 2

| Chỉ số | Giá trị |
|--------|---------|
| ROC-AUC (held-out) | **0,7026** |
| Tập dữ liệu | 300.360 dòng (sau OOF merge) |
| Ngưỡng phân loại | low=0,20 / high=0,40 |

---

## 4. So sánh features giữa hai Model

| Feature | Stage 1 (LR) | Stage 2 (LightGBM) | Ghi chú |
|---------|:---:|:---:|---------|
| `debt_to_income_ratio` | ✓ | ✗ | Stage 2 dùng `dti` (cùng giá trị, đổi tên) |
| `dti` | ✗ | ✓ | Cùng giá trị HC-style, naming khác |
| `loan_amount_to_income` | ✓ | ✓ | Tỷ số vay/thu nhập năm |
| `log_monthly_income` | ✓ | ✓ | Log-transform; LR cần, LightGBM không cần nhưng vẫn giữ |
| `high_dti_flag` | ✓ | ✓ | Flag nhị phân DTI vượt p75 |
| `monthly_income` (raw) | ✗ | ✓ | LightGBM dùng giá trị thô; LR dùng log-transform thay thế |
| `loan_amount` (raw) | ✗ | ✓ | LightGBM khai thác trực tiếp |
| `term` (raw) | ✗ | ✓ | LightGBM khai thác trực tiếp |
| `credit_score_computed` | ✗ | ✓ | **Output của Stage 1** → input Stage 2 |
| `loan_type` | ✓ | ✓ | Sinh từ loan_purpose |
| `num_previous_loans` | ✓ | ✓ | Lịch sử vay cũ |
| `previous_default_rate` | ✓ | ✓ | Tỷ lệ từ chối lịch sử |
| `num_bureau_records` | ✓ | ✓ | Số bản ghi tín dụng |
| `num_active_credit` | ✓ | ✓ | Dòng tín dụng đang mở |
| `total_overdue_amount` | ✓ | ✓ | Tổng dư nợ quá hạn |
| `max_credit_overdue_days` | ✓ | ✓ | Số ngày quá hạn tệ nhất |
| `years_employed` | ✓ | ✓ | Thâm niên việc làm |
| `income_verifiable_flag` | ✓ | ✓ | Xác minh thu nhập |
| `is_homeowner_flag` | ✓ | ✓ | Có nhà |
| `age_years` | ✓ | ✓ | Tuổi |
| `gender_male_flag` | ✓ | ✓ | Giới tính |
| `education_ordinal` | ✓ | ✓ | Học vấn |
| `cnt_children` | ✓ | ✓ | Số con |
| `cnt_fam_members` | ✓ | ✓ | Thành viên gia đình |
| `is_married_flag` | ✓ | ✓ | Tình trạng hôn nhân |
| `employment_status_grouped` | ✓ (OrdinalEnc) | ✗ | Stage 1 dùng grouped |
| `employment_status` | ✗ | ✓ (OrdinalEnc) | Stage 2 dùng tên gốc |
| `occupation_type` | ✓ (**TargetEnc**) | ✓ (OrdinalEnc) | Encoder khác nhau vì LR vs LightGBM |
| **Tổng** | **22** | **26** | |

### Features đã xóa so với v3

| Feature xóa | Lý do |
|-------------|-------|
| `credit_score_midpoint` | Người dùng tự khai → Stage 1 chỉ echo lại; đóng góp +14,5 pts/std gây circular |
| `rating_ordinal` | Dẫn xuất từ `credit_score_midpoint` → đa cộng tuyến |
| `payment_to_income` | Giống hệt `debt_to_income_ratio` (duplicate chính xác) |
| `has_bad_debt` | Chỉ 18/300.000 mẫu dương → phương sai gần 0, không có tín hiệu |
| `listing_category` | Hằng số = 1 trong toàn bộ tập train → gain = 0 |

---

## 5. Quy trình Inference (Backend)

```
POST /applications/evaluate  hoặc  POST /applications/confirm
        │
        ▼
build_stage1_input(payload, stage1_artifact, previous_applications)
  → dict 22 features cho Stage 1
        │
        ▼
_run_stage1(features, stage1_artifact)
  → credit_score_computed (int, 300–850)
  → stage1_prob (float)
        │
        ▼
build_model_input(payload, stage2_artifact,
                  credit_score_computed=...,
                  previous_applications=...)
  → FeatureBuildResult với 26 features cho Stage 2
        │
        ▼
stage2_pipeline.predict_proba(row)[0, 1]
  → default_probability (P₂)
  → risk_level: "Low" / "Medium" / "High"
        │
        ▼
compute_suggestion(payload, stage1, stage2, prev_apps)
  [Binary search: mỗi bước chạy cả 2 stage vì DTI thay đổi theo loan_amount]
  → suggested_amount, suggested_term
```

**Tính DTI tại inference:**
```python
hc_dti = (loan_amount / term) / monthly_income
# Ví dụ: income=5.000, amount=10.000, term=36 → DTI = (10000/36)/5000 = 0,0556
```

---

## 6. Ánh xạ loan_purpose → loan_type

| loan_purpose (form) | loan_type (model) | Lý do phân loại |
|--------------------|:-----------------:|-----------------|
| Education | 1 (Cash) | Thanh toán một lần, kỳ hạn cố định |
| Home | 1 (Cash) | Thanh toán một lần, kỳ hạn cố định |
| Car | 1 (Cash) | Thanh toán một lần, kỳ hạn cố định |
| Business | 1 (Cash) | Thanh toán một lần, kỳ hạn cố định |
| Medical | 1 (Cash) | Thanh toán một lần, kỳ hạn cố định |
| Personal | 1 (Cash) | Thanh toán một lần, kỳ hạn cố định |
| **Revolving** | **0 (Revolving)** | Hạn mức tín dụng quay vòng |

---

## 7. Quy trình Huấn luyện OOF (Tránh Data Leakage)

```
Tập gold (300.360 dòng)
        │
        ▼  Chia 5 folds (KFold, shuffle=True, seed=42)
        │
  Với mỗi fold k (k = 1..5):
    ├─ Train Stage 1 trên 4 folds còn lại
    └─ Predict P₁ trên fold k → OOF[k]  (Stage 1 chưa thấy fold k)
        │
        ▼
  Tổng hợp: OOF = concat(OOF[1..5]) — 300.360 dự đoán
  Quy đổi OOF probs → credit_score_computed (FICO PDO)
  Lưu: oof_stage1.csv (listing_key, oof_prob, credit_score_computed)
        │
        ▼
  Train Stage 1 CUỐI trên toàn bộ dữ liệu → scorecard_model.pkl
        │
        ▼
  Merge OOF vào gold theo listing_key
  Train Stage 2 trên [26 features + credit_score_computed từ OOF]
  → customer_risk_model.pkl
```

**Tại inference:** Stage 1 cuối (train trên toàn dữ liệu) predict `credit_score_computed` → Stage 2 dùng ngay.

---

## 8. Hướng dẫn Retraining

**Điều kiện:** ETL đã chạy, bảng `gold.hc_features_v1` đã có cột `loan_type`.

```bash
# Từ thư mục gốc dự án
source venv/bin/activate

# Bước 1 (chỉ cần nếu cần rebuild bảng gold)
python -m machinelearning.etl.etl_gold

# Bước 2 — Train Stage 1, sinh OOF predictions
python -m machinelearning.ml.train_scorecard

# Bước 3 — Train Stage 2 (yêu cầu oof_stage1.csv từ Bước 2)
python -m machinelearning.ml.retrain_customer_model
```

**Artifacts sinh ra:**
- `machinelearning/ml/models/scorecard_model.pkl` — Stage 1
- `machinelearning/ml/models/oof_stage1.csv` — dùng để train Stage 2, không dùng lúc inference
- `machinelearning/ml/models/customer_risk_model.pkl` — Stage 2

**Sau khi retrain:** Restart backend — artifacts được load lazy lần đầu tiên có request.
