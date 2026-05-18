# Tổng Quan Machine Learning & Mối Quan Hệ Với RAG — CreditIntel

> **Ngày cập nhật:** 2026-05-17  
> **Phạm vi:** `machinelearning/ml/`, `backend/services/`, `backend/rag/`

> **Lưu ý 18/05/2026:** Một số phần trong tài liệu này vẫn mô tả contract v3 có `credit_score`. Contract ML hiện tại là Stability v2/v4 và không dùng `credit_score` làm model input. Xem `docs/migration_v2_summary.md` để lấy thông tin migration mới nhất.

---

## 1. Tổng Quan Hệ Thống ML

Hệ thống Machine Learning của CreditIntel giải quyết bài toán **đánh giá rủi ro tín dụng** (Credit Risk Scoring) — dự đoán xác suất vỡ nợ (`default_probability`) của khách hàng khi nộp đơn vay. ML đóng vai trò là "bộ não" phân tích rủi ro, trong khi RAG đóng vai trò là "bộ mặt" giao tiếp giải thích kết quả cho khách hàng.

### Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────────────┐
│                      ETL PIPELINE                                │
│  Bronze (CSV gốc) → Silver (cleansed) → Gold (features)         │
│  load_bronze.py     etl_silver.py        etl_gold.py            │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    TRAINING PHASE       │
              │  retrain_customer_model │ → customer_risk_model_*.pkl
              │  train_scorecard        │ → scorecard_model.pkl
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   INFERENCE (Backend)   │
              │  ml_service.predict()   │
              │  model_feature_builder  │
              │  loan_suggestion_service│
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   RAG INTEGRATION       │
              │  context_builder.py     │ → inject ML results vào prompt
              │  chat_service.py        │ → auto-trigger ML trước khi chat
              │  prompts.py             │ → system prompt với user_context
              └─────────────────────────┘
```

---

## 2. Quá Trình Phát Triển Model

### 2.1 Lịch sử phiên bản

| Version | Model | Features | Metric chính | Ghi chú |
|---------|-------|----------|:------------:|---------|
| v1 (gốc) | LightGBM | ~15 core features | ROC-AUC ~0.72 | Baseline ban đầu |
| v2 | LightGBM | 28 features (27 numeric + 1 cat) | ROC-AUC 0.7529, Recall 65% | Thêm bureau + demographics, dùng median imputation |
| v3 (HEAD) | LightGBM | 28 features (26 numeric + 2 cat) | ROC-AUC ↑ | Loại bỏ ext_source_1/3, thêm `years_employed` + `occupation_type`, không còn median imputation |
| v5.3 (origin/hoang) | LightGBM | 28 features | PR-AUC optimized | Thêm `scale_pos_weight` tuning, 4-band risk system, optimal threshold search |

### 2.2 Model hiện tại đang dùng (sau merge)

**File model:** `machinelearning/ml/models/customer_risk_model_2.pkl`  
**Script training:** `machinelearning/ml/retrain_customer_model.py` (version `customer_lgbm_v5.3_spw_tuned`)

**Cải tiến chính của v5.3 so với v2:**

- **Scale Pos Weight Tuning:** Tự động tìm `scale_pos_weight` tối ưu từ danh sách ứng viên `[1.0, 3.0, 5.0, 7.0, 9.0, ratio, sqrt(ratio)]`, chọn theo PR-AUC cao nhất (tie-break bằng ROC-AUC).
- **4-Band Risk System:** Thay vì 3 mức (Low/Medium/High), model mới chia thành 4 band dựa trên optimal threshold:
  - `PRE_APPROVE`: PD < decision_low
  - `MANUAL_REVIEW`: decision_low ≤ PD < decision_high
  - `HIGH_RISK_REVIEW`: decision_high ≤ PD < 0.40
  - `AUTO_REJECT`: PD ≥ 0.40
- **Optimal Threshold Search:** Tìm threshold tối ưu đảm bảo Recall ≥ 75% trên tập default.
- **Calibration Table:** In bảng calibration theo decile để kiểm tra model có well-calibrated không.
- **3-Way Split:** Train/Val/Test = 70/10/20 (thay vì 80/20), dùng validation set cho early stopping.

### 2.3 Model phụ — Credit Scorecard

**File:** `machinelearning/ml/models/scorecard_model.pkl`  
**Script:** `machinelearning/ml/train_scorecard.py`

Chuyển đổi P(default) thành điểm tín dụng kiểu FICO (300–850) với breakdown điểm theo từng feature. Sử dụng Logistic Regression + StandardScaler, công thức PDO (Points to Double the Odds):

```
score = base_score - factor × (model_logit - base_logit)
factor = PDO / ln(2),  base_logit = -ln(base_odds_good)
```

Tham số: `base_score=600`, `base_odds_good=50`, `PDO=20`.

---

## 3. Chi Tiết Features (28 features)

### 3.1 Phân nhóm features

| Nhóm | Số lượng | Features |
|------|:--------:|----------|
| **Core (từ form)** | 8 | `monthly_income`, `loan_amount`, `term`, `employment_status`, `dti`, `is_homeowner`, `listing_category`, `credit_score` |
| **V3 mới** | 2 | `years_employed`, `occupation_type` |
| **Bureau** | 6 | `num_bureau_records`, `num_active_credit`, `total_overdue_amount`, `max_credit_overdue_days`, `has_bad_debt`, `income_verifiable_flag` |
| **Demographics** | 6 | `age_years`, `gender_male_flag`, `education_ordinal`, `cnt_children`, `cnt_fam_members`, `is_married_flag` |
| **Auto-computed** | 4 | `log_monthly_income`, `loan_amount_to_income`, `rating_ordinal`, `high_dti_flag` |
| **DB history** | 2 | `num_previous_loans`, `previous_default_rate` |

### 3.2 Top features theo importance (v2)

| Feature | Importance | Có tại inference? |
|---------|:---------:|:-----------------:|
| `age_years` | 1344 | ❌ Median-fill |
| `credit_score` | 1266 | ✅ |
| `ext_source_3` | 1183 | ❌ (đã loại bỏ ở v3) |
| `loan_amount` | 1103 | ✅ |
| `ext_source_1` | 1092 | ❌ (đã loại bỏ ở v3) |
| `term` | 901 | ✅ |
| `dti` | 876 | ✅ |

> ⚠️ V3 đã loại bỏ `ext_source_1/3` (không thu thập được tại inference) và thay bằng `years_employed` + `occupation_type`.

---

## 4. Pipeline Inference (Runtime)

### 4.1 Luồng xử lý khi khách hàng nộp đơn

```
POST /applications/submit
    │
    ▼
ml_service.predict(payload, db, user_id)
    │
    ├─ model_feature_builder.build_model_input()
    │      ├─ Lấy 8 core fields từ form
    │      ├─ Lấy 2 history fields từ DB (num_previous_loans, previous_default_rate)
    │      ├─ Tính 4 derived features (log_income, loan_to_income, rating, high_dti)
    │      └─ Trả về FeatureBuildResult(features, imputed_features)
    │
    ├─ pipeline.predict_proba() → default_probability
    │
    └─ loan_suggestion_service.compute_suggestion()
           ├─ Binary search: tìm max loan_amount mà PD < LOW threshold
           ├─ Thử 5 kỳ hạn: 12, 24, 36, 48, 60 tháng
           ├─ 20 iterations, precision ~$0.1
           └─ Trả về: suggested_amount, suggested_term, is_perfect_fit
```

### 4.2 Đầu ra ML

| Field | Mô tả |
|-------|--------|
| `default_probability` | Xác suất vỡ nợ (0–1) |
| `risk_level` | `Low` / `Medium` / `High` |
| `risk_score` | Điểm an toàn 0–100 (= (1 - prob) × 100) |
| `suggested_amount` | Hạn mức vay tối đa an toàn (binary search) |
| `suggested_term` | Kỳ hạn tối ưu (12/24/36/48/60 tháng) |
| `is_perfect_fit` | Đơn hiện tại đã tối ưu chưa |
| `model_version` | Phiên bản model (vd: `customer_lgbm_v5.3_spw_tuned`) |
| `feature_snapshot` | Bản chụp feature đưa vào model |
| `imputed_features` | Danh sách feature bị mặc định (v3: luôn rỗng) |

### 4.3 Ngưỡng quyết định

| Điều kiện | Kết quả | Hành động |
|-----------|---------|-----------|
| PD < 20% | **LOW risk** | Đề xuất tối đa $15,000 / 36 tháng |
| 20% ≤ PD < 40% | **MEDIUM risk** | Đề xuất tối đa $8,000 / 24 tháng, cần Admin review |
| PD ≥ 40% | **HIGH risk** | **AUTO_REJECTED** — không qua Admin |

---

## 5. Mối Quan Hệ ML ↔ RAG

### 5.1 Cơ chế tích hợp

ML và RAG trong CreditIntel không phải hai hệ thống độc lập mà có mối quan hệ **cộng sinh**: ML cung cấp dữ liệu phân tích định lượng, RAG chuyển đổi thành ngôn ngữ tự nhiên giải thích cho khách hàng.

```
┌─────────────────────────────────────────────────────────────┐
│                    CHAT REQUEST FLOW                         │
│                                                              │
│  User hỏi: "Tại sao đơn tôi bị từ chối?"                   │
│       │                                                      │
│       ▼                                                      │
│  chat_service._ensure_latest_application_has_prediction()   │
│       │  → Nếu đơn chưa có ML result → auto-trigger predict │
│       │  → Lưu kết quả vào DB (loan_applications)           │
│       ▼                                                      │
│  context_builder.build_user_context(db, user_id)            │
│       │  → Query đơn vay mới nhất từ DB                     │
│       │  → Build 4 blocks context:                          │
│       │     Block 1: Form context (thông tin form)           │
│       │     Block 2: ML context (PD, risk, recommendation)  │
│       │     Block 3: Advisory context (risk factors, advice) │
│       │     Block 4: Data quality (imputed features)         │
│       ▼                                                      │
│  RAG chain.invoke(question, user_context, chat_history)     │
│       │  → Retriever tìm top-4 chunks từ Qdrant            │
│       │  → Prompt = system + user_context + chunks + history│
│       │  → LLM generate câu trả lời cá nhân hóa            │
│       ▼                                                      │
│  "Đơn của bạn bị từ chối vì PD=43.2%, vượt ngưỡng 40%..." │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Context Builder — Cầu nối ML → RAG

File `backend/rag/context_builder.py` là module cầu nối quan trọng nhất. Nó biến dữ liệu thô từ ML thành context có cấu trúc cho LLM:

**Block 1 — Form Context:** Trích xuất thông tin form vay (loan_amount, DTI, credit_score, employment, v.v.)

**Block 2 — ML Context:** Trích xuất kết quả ML prediction:
- `default_probability`, `risk_level`, `risk_score`
- `recommended_amount`, `recommended_term`
- `model_version`, `has_prediction`

**Block 3 — Advisory Context (Derived):** Backend tính sẵn các phân tích:
- So sánh `loan_amount` vs `recommended_amount` (cao/thấp hơn bao nhiêu %)
- So sánh `term` vs `recommended_term`
- DTI band (Tốt / Cần chú ý / Rủi ro cao) và Credit Score band (Kém → Xuất sắc)
- Top 4 yếu tố rủi ro chính (`primary_risk_factors`)
- Top 4 điểm tích cực (`positive_factors`)
- Danh sách khuyến nghị hành động (`suggested_actions`)

**Block 4 — Data Quality:** Đánh giá độ tin cậy dựa trên số feature bị impute.

### 5.3 Ví dụ context inject vào LLM prompt

```
THÔNG TIN ĐƠN VAY GẦN NHẤT
- Trạng thái đơn: PENDING_REVIEW
- Số tiền xin vay: $10,000
- Kỳ hạn: 36 tháng
- Thu nhập hàng tháng: $8,000
- DTI: 28.0% — Tốt (< 30%)
- Điểm tín dụng: 720 — Tốt (670–739)
- Tình trạng việc làm: Employed
- Sở hữu nhà: Có

KẾT QUẢ ML
- Xác suất vỡ nợ dự đoán: 12.3%
- Mức rủi ro: Low
- Risk score: 88/100 (càng cao càng an toàn)
- Hạn mức hệ thống đề xuất: $15,000 / 36 tháng
- So sánh số tiền: Thấp hơn đề xuất 33% ($10,000 so với $15,000)

PHÂN TÍCH TƯ VẤN
- Điểm tích cực:
  • Có sở hữu nhà (tài sản ổn định)
  • DTI thấp (< 30%) — gánh nặng nợ nhẹ
  • Có việc làm ổn định

ĐỘ TIN CẬY DỮ LIỆU
- Mức độ tin cậy: cao
- Tất cả thông tin do khách hàng cung cấp trực tiếp.
```

### 5.4 Nguyên tắc RAG khi sử dụng ML context

| Được phép | Không được phép |
|-----------|-----------------|
| Giải thích yếu tố ảnh hưởng rủi ro | Hứa đơn vay sẽ được duyệt |
| Nêu đề xuất hạn mức/kỳ hạn từ ML | Khẳng định model chắc chắn đúng |
| Khuyên cải thiện DTI/credit score | Tiết lộ cấu trúc model nội bộ |
| So sánh khoản vay với đề xuất | Tiết lộ thông tin khách hàng khác |
| Dùng ngôn ngữ thận trọng khi data bị impute | Đề xuất gói vay lớn hơn khi risk cao |

---

## 6. Kết Quả Benchmark RAG

Benchmark được chạy với 31 câu hỏi trên 6 nhóm (FAQ, Policy, Personalized, Guardrail, Edge case).

### 6.1 Điểm tổng hợp

| Metric | Điểm | Đánh giá |
|--------|:-----:|----------|
| **Faithfulness** | 0.91 | ✅ Tốt (≥ 0.85) |
| **Relevance** | 0.90 | ✅ Tốt (≥ 0.80) |
| **Source Recall** | 0.58 | ⚠️ Cần cải thiện (< 0.60) |
| **Guardrail Rate** | 1.00 | ✅ Hoàn hảo |
| **Overall Score** | **0.86** | ✅ Tốt (≥ 0.82) |

### 6.2 Phân tích theo nhóm

- **FAQ & Policy (18 câu):** Gần như hoàn hảo — faithfulness/relevance đạt 1.0 cho đa số câu.
- **Guardrail (6 câu):** 100% Pass — AI từ chối đúng tất cả các trường hợp (hứa hẹn, privacy, out-of-scope, prompt injection).
- **Personalized (5 câu):** ⚠️ **Điểm yếu chính** — AI không truy cập được ML context cá nhân, trả lời "không có đủ thông tin" thay vì trích dẫn `default_probability` và `recommended_amount` từ hồ sơ.

### 6.3 Nguyên nhân personalized thấp điểm

Trong kịch bản benchmark tự động, `user_context` từ ML chưa được load và inject thành công vào session chat (có thể do đơn vay test chưa có kết quả predict, hoặc session bị khác user). Khi sử dụng thực tế (qua UI), luồng `chat_service → _ensure_latest_application_has_prediction → context_builder` hoạt động đúng.

---

## 7. Đề Xuất Cải Tiến

### 7.1 Cải tiến ML

| Ưu tiên | Hành động | AUC gain ước tính | Effort |
|:-------:|-----------|:-----------------:|:------:|
| 1 | Thêm features từ `application_train.csv` (days_employed, social circle defaults, bureau inquiries) | +0.01 | Thấp |
| 2 | Thêm aggregates từ `previous_application.csv` (credit ratio, yield group) | +0.01 | Thấp |
| 3 | Thêm `bureau_balance.csv` (DPD status, payment discipline) | +0.015 | Trung bình |
| 4 | Thêm `installments_payments.csv` (late payments, underpayments) | +0.015 | Trung bình |
| 5 | Thêm `credit_card_balance.csv` + `POS_CASH_balance.csv` | +0.01 | Trung bình |

> Mục tiêu tổng: đưa ROC-AUC từ ~0.75 lên ~0.815 (benchmark top HC competition: 0.82–0.83).

### 7.2 Cải tiến RAG liên quan đến ML

| # | Cải tiến | Mô tả |
|:-:|----------|--------|
| 1 | **Fix benchmark personalized** | Đảm bảo script test tạo đơn vay + chờ prediction hoàn tất trước khi chat. Kiểm tra `_ensure_latest_application_has_prediction()` trong test flow. |
| 2 | **Thêm feature importance vào context** | Inject top-5 features đóng góp nhiều nhất cho prediction của khách hàng cụ thể (dùng SHAP values hoặc LightGBM `feature_importances_`) vào advisory context. |
| 3 | **Thêm loan package context** | Nếu có package catalog (Gói an toàn, Gói tiêu chuẩn, Gói ưu tiên), inject vào context để RAG tư vấn gói phù hợp. |
| 4 | **Mở rộng knowledge base** | Thêm tài liệu từ `docs/ml/` (FEATURE_CATALOG.md, ML_FEATURES.md) vào Qdrant để RAG có thể giải thích chi tiết hơn về cách model hoạt động (ở mức user-facing). |
| 5 | **Audit trail** | Lưu snapshot context đã inject vào RAG prompt cùng với câu trả lời vào DB để audit chất lượng tư vấn. |

### 7.3 Cải tiến triển khai

| Hành động | Chi tiết |
|-----------|----------|
| **Model versioning** | Dùng MLflow hoặc DVC để track experiment, so sánh metrics giữa các version. Hiện tại chỉ lưu `.pkl` thủ công. |
| **A/B testing** | Cho phép chạy song song 2 model version (vd: v2 vs v5.3) và so sánh kết quả trên production traffic. |
| **Monitoring** | Theo dõi distribution shift trên features (PSI — Population Stability Index) để phát hiện khi model cần retrain. |
| **CI/CD cho ML** | Tự động chạy `validate_data → retrain → evaluate → deploy` khi có dữ liệu mới. |

---

## 8. Cách Chạy

### Training

```bash
# Từ root project (Loan_ETL/)
source .venv/bin/activate
pip install -r machinelearning/requirements.txt

# Chạy ETL pipeline (nếu chưa có data trong DuckDB)
python -m machinelearning.etl.load_bronze
python -m machinelearning.etl.etl_silver
python -m machinelearning.etl.etl_gold

# Train model chính
python -m machinelearning.ml.retrain_customer_model

# Train scorecard (optional)
python -m machinelearning.ml.train_scorecard
```

### Inference (Backend)

```bash
cd backend
uvicorn main:app --reload
# ML predict tự động khi: POST /applications/submit
# ML context tự động inject khi: POST /chat
```

### Benchmark RAG

```bash
cd backend
python tests_local/test_rag_benchmark.py
# Kết quả → docs/rag_benchmark_results.json
```

---

## 9. Cấu Trúc File Liên Quan

```
machinelearning/
├── etl/
│   ├── load_bronze.py           # Load CSV gốc vào DuckDB
│   ├── etl_silver.py            # Transform → silver layer
│   └── etl_gold.py              # Feature engineering → gold layer
├── ml/
│   ├── retrain_customer_model.py  # Training script chính (LightGBM v5.3)
│   ├── train_scorecard.py         # Credit scorecard (Logistic Regression)
│   ├── validate_data.py           # Data validation trước training
│   ├── FEATURE_CATALOG.md         # Catalog 28 features + roadmap
│   └── models/
│       ├── customer_risk_model.pkl    # Model v1
│       ├── customer_risk_model_2.pkl  # Model v5.3 (đang dùng)
│       ├── customer_risk_model_3.pkl  # Model thử nghiệm
│       └── scorecard_model.pkl        # LR scorecard

backend/
├── services/
│   ├── ml_service.py               # Load model + predict()
│   ├── model_feature_builder.py    # Build feature vector cho inference
│   ├── loan_suggestion_service.py  # Binary search hạn mức an toàn
│   └── chat_service.py             # Orchestrate ML + RAG
├── rag/
│   ├── context_builder.py          # ML results → structured text cho prompt
│   ├── prompts.py                  # System prompt (6 quy tắc)
│   ├── chain.py                    # LCEL chain (singleton)
│   ├── retriever.py                # Qdrant vector search
│   └── knowledge/
│       ├── faq.md                  # 17 FAQ
│       └── policy.md               # Chính sách xét duyệt

ml/model_training/                  # Tài liệu training từ nhánh hoang
├── file_goc.md
├── file_goc_cai_tien.md
├── model_lightgbm_hoang.md
└── model_lightgbm_v2_hoang.md
```

---

*Tài liệu phản ánh trạng thái source code sau merge nhánh `origin/hoang` vào `cuong` ngày 2026-05-17.*
