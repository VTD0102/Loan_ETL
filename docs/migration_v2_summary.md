# Migration v2: Credit Risk Model Stability Dataset

> **Ngày**: 18/05/2026  
> **Mục tiêu**: Loại bỏ `credit_score_midpoint` (gameable) khỏi pipeline, thay dataset cũ (Home Credit Default Risk 2018) bằng dataset mới (Home Credit Credit Risk Model Stability 2024).

---

## 1. Vấn đề cần giải quyết

| Vấn đề | Mô tả |
|---|---|
| **Train/Inference Gap** | Train dùng `EXT_SOURCE_2` (bureau score), inference dùng `credit_score` (user tự điền) |
| **Gameable** | `credit_score_midpoint` là feature dominant (+14.54 pts/std) — user tự khai = dễ gian lận |
| **Multicollinearity** | `rating_ordinal` derived từ `credit_score` → hệ số bất ổn |

## 2. Giải pháp

Dataset mới **không có `EXT_SOURCE_2`** → loại bỏ root cause. Thay bằng 466 raw behavioral features từ nhiều nguồn verifiable.

---

## 3. Files thay đổi

### ETL Pipeline

| File | Thay đổi |
|---|---|
| `machinelearning/etl/load_bronze.py` | **Viết lại** — load 6 bảng parquet (DuckDB native, không pandas) |
| `machinelearning/database/transform_silver_hcv2.sql` | **MỚI** — JOIN 6 bảng bronze (depth 0/1 aggregation) |
| `machinelearning/etl/etl_silver.py` | Cập nhật chạy SQL mới → `silver.hc_v2_cleansed` |
| `machinelearning/database/transform_gold_hcv2.sql` | **MỚI** — Feature engineering không có credit_score |
| `machinelearning/etl/etl_gold.py` | Cập nhật chạy SQL mới → `gold.hc_features_v2` |
| `machinelearning/etl/pipeline.py` | Cập nhật docstring |

### ML Training

| File | Thay đổi |
|---|---|
| `machinelearning/ml/validate_data.py` | Cập nhật validation cho v2 schema (bỏ credit_score checks) |
| `machinelearning/ml/train_scorecard.py` | **Bỏ** `credit_score_midpoint` + `rating_ordinal`, thêm 10+ features mới |
| `machinelearning/ml/retrain_customer_model.py` | **Bỏ** `credit_score`, cập nhật feature list v4 |

### Backend

| File | Thay đổi |
|---|---|
| `backend/services/credit_score_service.py` | **Viết lại** `_build_features()` — không dùng `app.credit_score` làm model input |
| `backend/schemas/application.py` | `credit_score`: **required → optional** (nullable) |
| `backend/models/application.py` | `credit_score`: `Mapped[int]` → `Mapped[Optional[int]]` (nullable) |

---

## 4. Kết quả ETL

```
Bronze: 6 tables loaded (30.6s total)
├── train_base:              1,526,659 rows ×   5 cols
├── train_static_0:          1,526,659 rows × 168 cols
├── train_static_cb_0:       1,500,476 rows ×  53 cols
├── train_person_1:          2,973,991 rows ×  37 cols
├── train_credit_bureau_a_1: 15,940,537 rows ×  79 cols
└── train_applprev_1:         6,525,979 rows ×  41 cols

Silver: silver.hc_v2_cleansed
├── 1,526,659 rows
├── Default rate: 3.10%
└── Income null rate: 33.49%

Gold: gold.hc_features_v2
├── 1,526,659 rows
├── 53 features
└── Default rate: 3.10%
```

## 5. Kết quả Model

### Scorecard (Logistic Regression)

| Metric | Cũ (có credit_score) | Cũ (bỏ credit_score) | **Mới v2** |
|---|---|---|---|
| **ROC-AUC** | 0.7110 | 0.6684 | **0.7367** ✅ |
| Features | 25 (gameable) | 23 (safe) | **30** (safe + rich) |
| Dataset size | 307K | 307K | **1.015M** (3.4x) |
| Score range | 300–850 | 300–850 | 300–850 |

> Sau khi sửa mapping `employment_length` và bỏ `cb_rejections_3y` gần như toàn 0, scorecard v2 retrain đạt **ROC-AUC 0.7367**.

### Top Features (Scorecard v2)

```
Feature                    Points/Std    Direction
─────────────────────────  ──────────    ─────────
previous_default_rate        -11.31      ⬆ Risk (quan trọng nhất)
num_bureau_records            +8.20      ⬇ Risk
age_years                     +7.34      ⬇ Risk
num_installs_dpd10            -6.01      ⬆ Risk
income_verifiable_flag        -5.66      ⬆ Risk khi không xác minh được
has_bad_debt                  -4.95      ⬆ Risk
high_dti_flag                 -4.73      ⬆ Risk
cb_queries_30d                -3.69      ⬆ Risk (credit hunger)
```

> **Không còn `credit_score_midpoint`** trong danh sách features — train/inference gap đã được loại bỏ.

### Customer Model (LightGBM)

| Metric | **Mới v4** |
|---|---:|
| ROC-AUC | **0.8065** |
| Features | 35 |
| Dataset size | 1,526,659 |
| Model version | `customer_lgbm_v4_stability` |

---

## 6. Features bị loại bỏ vs thêm mới

### Bỏ (5 features)

| Feature | Lý do |
|---|---|
| `credit_score_midpoint` | **ROOT CAUSE** — gameable user input |
| `rating_ordinal` | Derived từ credit_score → multicollinear |
| `gender_male_flag` | 0.8% coverage trong dataset mới |
| `cnt_children` | ~0% coverage |
| `cnt_fam_members` | Không có trong dataset mới |

### Thêm (10+ features)

| Feature | Nguồn | Ý nghĩa |
|---|---|---|
| `current_debt_ratio` | static_0 | Nợ hiện tại / khoản vay |
| `total_debt_to_income` | static_0 | Tổng nợ / thu nhập năm |
| `avg_dpd_recent` | static_0 | DPD trung bình 3 tháng gần nhất |
| `num_installs_dpd10` | static_0 | Số kỳ trả chậm >10 ngày |
| `total_prolongations` | bureau_a | Số lần gia hạn tín dụng |
| `cb_queries_30d` | static_cb | Số truy vấn bureau 30 ngày (credit hunger) |
| `num_cb_queries` | static_cb | Tổng truy vấn bureau |
| `income_missing_flag` | derived | Flag thu nhập bị null (33%) |
| `dti_missing_flag` | derived | Flag DTI bị null |

### Bỏ thêm sau kiểm tra coverage

| Feature | Lý do |
|---|---|
| `cb_rejections_3y` | Gần như toàn 0 trong `train_static_cb_0` nên không thân thiện và không có tín hiệu ổn định |

---

## 7. Cách chạy pipeline mới

```bash
# Từ root project
source .venv/bin/activate

# ETL: Bronze → Silver → Gold
python -m machinelearning.etl.load_bronze
python -m machinelearning.etl.etl_silver
python -m machinelearning.etl.etl_gold

# Hoặc chạy cả pipeline
python -m machinelearning.etl.pipeline

# Train models
python -m machinelearning.ml.train_scorecard
python -m machinelearning.ml.retrain_customer_model
```

---

## 8. Lưu ý Backend

- `credit_score` trong form application **vẫn giữ nhưng optional** — user có thể điền hoặc không
- **Model KHÔNG dùng** `credit_score` làm input — score hiển thị cho user là "stated score"
- FICO score hiển thị trên dashboard là **hệ thống tự tính** từ P(default) của model
- Các features không có tại inference (avg_dpd_recent, cb_queries, etc.) dùng giá trị mặc định = 0
