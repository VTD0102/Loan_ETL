# CIC Feature Gap Analysis — LightGBM v4 & Scorecard vs `cic_credit_records`

Tài liệu này đối chiếu features của **hai model** với schema bảng `cic_credit_records`
(bureau DB), chỉ rõ từng feature đã khớp, đang dùng xấp xỉ, hoặc chưa có dữ liệu tương ứng.

| Model | File artifact | Số features | Mục đích |
|---|---|---|---|
| **LightGBM v4** | `customer_risk_model.pkl` | 35 | Xác suất vỡ nợ P(default) |
| **Scorecard LR** | `scorecard_model.pkl` | 30 | FICO-style score 300–850 |

---

## Phần 1 — LightGBM v4

### 1.1 Tổng quan

| Trạng thái | Số feature | Ghi chú |
|---|---|---|
| ✅ Khớp trực tiếp | 7 | CIC có field tương đương, map 1-1 |
| ⚠️ Xấp xỉ từ `loan_history` | 4 | Tính được nhưng thiếu cửa sổ thời gian |
| ❌ Chưa có trong CIC | 2 | Schema CIC không có dữ liệu tương ứng |
| 🔵 Không liên quan CIC | 22 | Từ form khách hàng / tính nội bộ |

### 1.2 ✅ Features khớp trực tiếp với CIC

| Feature model | Cột CIC | Cách map | File |
|---|---|---|---|
| `num_active_credit` | `total_active_loans` | Trực tiếp | `cic_service.enrich_from_cic()` |
| `num_active_credit_bureau` | `total_active_loans` | Alias của `num_active_credit` | `model_feature_builder.py` |
| `total_overdue_amount` | `total_overdue_amount` | Trực tiếp | `cic_service.enrich_from_cic()` |
| `max_credit_overdue_days` | `max_dpd_12m` | Trực tiếp (window 12m) | `cic_service.enrich_from_cic()` |
| `has_bad_debt` | `bad_debt_flag` | Trực tiếp | `cic_service.enrich_from_cic()` |
| `num_bureau_records` | `loan_history` (JSON) | `len(loan_history)` | `cic_service.enrich_from_cic()` |
| `num_cb_queries` | `num_credit_inquiries` | Trực tiếp | `cic_service.derive_bureau_features()` |

> `num_active_credit_bureau` là alias SQL training: `num_active_credit AS num_active_credit_bureau` — cùng giá trị.

### 1.3 ⚠️ Features xấp xỉ từ `loan_history` (thiếu cửa sổ thời gian)

Tính trong `cic_service.derive_bureau_features()` từ mảng JSON `loan_history`
(mỗi entry: `lender`, `amount`, `status`, `dpd_max`).

**Vấn đề:** `loan_history` không có `opened_at` / `closed_at` nên không lọc được
theo cửa sổ thời gian. Các feature tính trên **toàn bộ lịch sử**, không chỉ giai đoạn
gần nhất như trong training data.

| Feature model | Nguồn training (Home Credit) | Tính xấp xỉ từ CIC | Sai lệch |
|---|---|---|---|
| `avg_dpd_recent` | `avgdbddpdlast3m_4187120P` — trung bình DPD 3 tháng gần nhất | `mean(loan_history[].dpd_max)` toàn lịch sử | Thấp hơn thực tế nếu khoản cũ ít lỗi |
| `max_dpd_24m` | `maxdpdlast24m_143P` — DPD tối đa 24 tháng | `max(loan_history[].dpd_max)` toàn lịch sử | Cao hơn nếu có khoản cũ quá hạn nhiều |
| `num_installs_dpd10` | `numinstlswithdpd10_728L` — số kỳ quá hạn >10 ngày | `count(loan_history[].dpd_max > 10)` | Overcount nếu khoản cũ đã đóng lâu |
| `max_overdue_amount` | Max số tiền quá hạn từ gold transform | `max(amount where status="overdue")` | Dùng tổng khoản vay, không phải phần quá hạn thực tế |

### 1.4 ❌ Features chưa có trong CIC — dùng artifact default (median training)

Không xuất hiện trong `derive_bureau_features()`, fall-through xuống `artifact["feature_defaults"]`.

| Feature model | Nguồn training (Home Credit) | Ý nghĩa | Tại sao CIC thiếu | Giá trị hiện tại |
|---|---|---|---|---|
| `total_prolongations` | `prolongationcount_599L` (applprev) | Số lần khách xin gia hạn/rollover | CIC không track số lần gia hạn | Median training ≈ 0 |
| `cb_queries_30d` | `days30_165L` (credit_bureau) | Số lần bị tra cứu tín dụng trong 30 ngày | CIC chỉ có tổng `num_credit_inquiries`, không chia theo window 30 ngày | Median training ≈ 0–1 |

### 1.5 🔵 Features không liên quan CIC

| Nhóm | Features |
|---|---|
| Thu nhập & khoản vay | `monthly_income`, `loan_amount`, `term`, `dti`, `loan_amount_to_income`, `log_monthly_income`, `high_dti_flag`, `payment_to_income` |
| Gánh nặng nợ | `current_debt_ratio`, `total_debt_to_income` |
| Lịch sử đơn vay nội bộ | `num_previous_loans`, `previous_default_rate` |
| Nhân khẩu học | `age_years`, `years_employed`, `education_ordinal`, `is_homeowner`, `income_verifiable_flag`, `is_married_flag` |
| Missing flags | `income_missing_flag`, `dti_missing_flag` |
| Categorical | `employment_status`, `occupation_type` |

> `dti` sau fix commit `39d0856` bao gồm `total_monthly_installment` từ CIC:
> `dti = (loan_amount/term + cic_monthly) / monthly_income`.

### 1.6 Sơ đồ luồng feature tại inference

```
Khách điền form
    │
    ├─► Form fields ──────────────────────────────────► model_feature_builder.py
    │                                                         │
    └─► CCCD lookup → cic_credit_records                      │
            │                                                 │
            ├─ total_active_loans       → num_active_credit ─►│
            ├─ total_overdue_amount     → total_overdue ──────►│
            ├─ max_dpd_12m              → max_credit_overdue ─►│
            ├─ bad_debt_flag            → has_bad_debt ────────►│
            ├─ num_credit_inquiries     → num_cb_queries ──────►│
            ├─ total_monthly_installment → dti (cộng thêm) ───►│
            │                                                 │
            ├─ loan_history[].dpd_max   → avg_dpd_recent  ⚠️ ►│
            │                           → max_dpd_24m     ⚠️ ►│
            │                           → num_installs_dpd10 ⚠►│
            │                                                 │
            ├─ (thiếu) total_prolongations → artifact default ❌
            └─ (thiếu) cb_queries_30d      → artifact default ❌
```

---

## Phần 2 — Scorecard LR (FICO-style)

### 2.1 Tổng quan

| Trạng thái | Số feature | Ghi chú |
|---|---|---|
| ✅ Khớp trực tiếp | 6 | CIC có field tương đương, map 1-1 |
| ⚠️ Xấp xỉ từ CIC | 1 | Dùng `max_dpd_12m` thay cho window 24m |
| ❌ Hardcoded = 0 (CIC có nhưng không dùng) | 3 | Gap lớn hơn LightGBM |
| ❌ Chưa có trong CIC | 2 | Schema CIC không có dữ liệu tương ứng |
| 🔵 Không liên quan CIC | 18 | Từ form / tính nội bộ |

### 2.2 ✅ Features khớp trực tiếp với CIC

Scorecard đọc từ `app` object — các trường này đã được ghi đè bởi `cic_service.apply_cic_to_payload()`
trước khi lưu vào DB.

| Feature model | Cột CIC (nguồn gốc) | Cách map | File |
|---|---|---|---|
| `num_bureau_records` | `loan_history` (JSON) | `len(loan_history)` → `app.num_bureau_records` | `cic_service.enrich_from_cic()` |
| `num_active_credit` | `total_active_loans` | Trực tiếp → `app.num_active_credit` | `cic_service.enrich_from_cic()` |
| `total_overdue_amount` | `total_overdue_amount` | Trực tiếp → `app.total_overdue_amount` | `cic_service.enrich_from_cic()` |
| `max_credit_overdue_days` | `max_dpd_12m` | Trực tiếp → `app.max_credit_overdue_days` | `cic_service.enrich_from_cic()` |
| `has_bad_debt` | `bad_debt_flag` | Trực tiếp → `app.has_bad_debt` | `cic_service.enrich_from_cic()` |
| `debt_to_income_ratio` | `total_monthly_installment` | `(loan/term + cic_monthly) / income` | `credit_score_service._build_features()` |

### 2.3 ⚠️ Features xấp xỉ từ CIC

| Feature model | Nguồn training | Tính xấp xỉ | Sai lệch |
|---|---|---|---|
| `max_dpd_24m` | `maxdpdlast24m_143P` — window 24 tháng | `app.max_credit_overdue_days` = `max_dpd_12m` (window 12m) | Undercount — bỏ sót sự kiện quá hạn từ tháng 13-24 |

### 2.4 ❌ Hardcoded = 0 — CIC có dữ liệu nhưng Scorecard không dùng

Đây là gap **lớn hơn LightGBM**. `credit_score_service._build_features()` hardcode cứng
3 features này về 0 thay vì gọi `cic_service.derive_bureau_features()`.

| Feature model | Giá trị cứng | CIC có thể cung cấp | Ghi chú |
|---|---|---|---|
| `avg_dpd_recent` | `0.0` | `mean(loan_history[].dpd_max)` | LightGBM đã dùng — Scorecard bỏ qua |
| `num_installs_dpd10` | `0` | `count(loan_history[].dpd_max > 10)` | LightGBM đã dùng — Scorecard bỏ qua |
| `num_cb_queries` | `0` | `num_credit_inquiries` (trực tiếp) | LightGBM đã dùng — Scorecard **bỏ qua hoàn toàn** |

> **Tác động:** Scorecard luôn tính điểm như thể khách hàng không có kỳ quá hạn gần đây
> và không có query tín dụng nào — ngay cả khi CIC nói khác. Điểm FICO bị inflate
> cho các khách hàng có lịch sử DPD xấu.

### 2.5 ❌ Features chưa có trong CIC — hardcoded = 0

Giống LightGBM, hai feature này CIC chưa có column tương ứng.

| Feature model | Nguồn training (Home Credit) | Ý nghĩa | Giá trị hiện tại |
|---|---|---|---|
| `total_prolongations` | `prolongationcount_599L` | Số lần xin gia hạn khoản vay | `0` (hardcoded) |
| `cb_queries_30d` | `days30_165L` | Số query tín dụng 30 ngày qua | `0` (hardcoded) |

### 2.6 🔵 Features không liên quan CIC

| Nhóm | Features |
|---|---|
| Thu nhập & khoản vay | `debt_to_income_ratio`, `loan_amount_to_income`, `log_monthly_income`, `payment_to_income`, `high_dti_flag` |
| Gánh nặng nợ | `current_debt_ratio`, `total_debt_to_income` |
| Lịch sử đơn vay nội bộ | `num_previous_loans`, `previous_default_rate` |
| Nhân khẩu học | `age_years`, `years_employed`, `education_ordinal`, `is_homeowner_flag`, `income_verifiable_flag`, `is_married_flag` |
| Missing flags | `income_missing_flag`, `dti_missing_flag` |
| Categorical | `employment_status_grouped`, `occupation_type` |

### 2.7 Sơ đồ luồng feature tại inference

```
Khách điền form → application_service → LoanApplication lưu DB
    │
    └─► CCCD lookup → cic_credit_records → apply_cic_to_payload()
            │                                      │
            ├─ total_active_loans  → app.num_active_credit ──────────────►│
            ├─ total_overdue_amount → app.total_overdue_amount ───────────►│
            ├─ max_dpd_12m         → app.max_credit_overdue_days ─────────►│ credit_score_service
            ├─ bad_debt_flag       → app.has_bad_debt ────────────────────►│ ._build_features()
            ├─ total_monthly_inst. → debt_to_income_ratio (DTI fix) ──────►│
            │                                                              │
            ├─ max_dpd_12m         → max_dpd_24m ⚠️ (window lệch 12→24) ─►│
            │                                                              │
            ├─ loan_history[].dpd_max → avg_dpd_recent   ❌ hardcode=0.0  │
            ├─ loan_history[].dpd_max → num_installs_dpd10 ❌ hardcode=0  │
            ├─ num_credit_inquiries   → num_cb_queries    ❌ hardcode=0   │
            │                                                              │
            ├─ (thiếu) total_prolongations → hardcode=0 ❌               │
            └─ (thiếu) cb_queries_30d      → hardcode=0 ❌               │
```

---

## Phần 3 — So sánh tổng hợp hai model

| Feature CIC | LightGBM v4 | Scorecard LR | Ghi chú |
|---|---|---|---|
| `total_active_loans` | ✅ Dùng | ✅ Dùng | Cả hai khớp |
| `total_overdue_amount` | ✅ Dùng | ✅ Dùng | Cả hai khớp |
| `max_dpd_12m` | ✅ Dùng | ⚠️ Dùng (nhưng label 24m) | Scorecard sai window |
| `bad_debt_flag` | ✅ Dùng | ✅ Dùng | Cả hai khớp |
| `loan_history` → `num_bureau_records` | ✅ Dùng | ✅ Dùng | Cả hai khớp |
| `num_credit_inquiries` → `num_cb_queries` | ✅ Dùng | ❌ Hardcode=0 | **Scorecard thua** |
| `total_monthly_installment` → DTI | ✅ Dùng | ✅ Dùng | Fix commit `39d0856` |
| `loan_history` → `avg_dpd_recent` | ⚠️ Xấp xỉ | ❌ Hardcode=0 | **Scorecard thua** |
| `loan_history` → `max_dpd_24m` | ⚠️ Xấp xỉ | ⚠️ Xấp xỉ (12m) | Cả hai thiếu window |
| `loan_history` → `num_installs_dpd10` | ⚠️ Xấp xỉ | ❌ Hardcode=0 | **Scorecard thua** |
| `loan_history` → `max_overdue_amount` | ⚠️ Xấp xỉ | ❌ Không có feature này | LightGBM có thêm |
| `total_prolongations` | ❌ Không có trong CIC | ❌ Không có trong CIC | Cả hai thiếu |
| `cb_queries_30d` | ❌ Không có trong CIC | ❌ Không có trong CIC | Cả hai thiếu |

### Kết luận

- **LightGBM v4** tận dụng CIC tốt hơn Scorecard nhờ gọi `cic_service.derive_bureau_features()`.
- **Scorecard LR** hardcode `avg_dpd_recent`, `num_installs_dpd10`, `num_cb_queries` = 0 dù CIC có thể cung cấp — điểm FICO bị inflate cho khách hàng xấu.
- Cả hai thiếu `total_prolongations` và `cb_queries_30d` do CIC chưa có cột tương ứng.

### Ưu tiên fix

| Ưu tiên | Việc cần làm | Ảnh hưởng | Cần retrain? |
|---|---|---|---|
| 🔴 Cao | Scorecard: gọi `derive_bureau_features()` thay vì hardcode 0 | Điểm FICO chính xác hơn cho khách hàng có DPD | Không |
| 🟡 Trung bình | Thêm `cb_queries_30d` + `total_prolongations` vào CIC schema | Cả hai model có thêm signal | Không (dùng default=0 nếu chưa có data) |
| 🟢 Thấp | Thêm `opened_at`/`closed_at` vào `loan_history` JSON entries | Xóa sai lệch window thời gian cho `avg_dpd_recent`, `max_dpd_24m` | Không |

---

*Cập nhật lần cuối: 2026-05-21*
*Tham chiếu: `backend/services/cic_service.py`, `backend/services/credit_score_service.py`,
`backend/models/cic.py`, `machinelearning/ml/retrain_customer_model.py`,
`machinelearning/ml/train_scorecard.py`, `machinelearning/database/transform_silver_hcv2.sql`*
