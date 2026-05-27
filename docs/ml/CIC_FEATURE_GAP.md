# CIC Feature Gap Analysis — LightGBM v4 vs `cic_credit_records`

Tài liệu này đối chiếu **35 features** của model LightGBM v4 (`customer_risk_model.pkl`) với
schema hiện tại của bảng `cic_credit_records` (bureau DB), chỉ rõ từng feature đã khớp,
đang dùng xấp xỉ, hoặc chưa có dữ liệu tương ứng.

---

## Tổng quan

| Trạng thái | Số feature | Ghi chú |
|---|---|---|
| ✅ Khớp trực tiếp | 5 | CIC có field tương đương, map 1-1 |
| ⚠️ Xấp xỉ từ `loan_history` | 4 | Tính được nhưng thiếu cửa sổ thời gian |
| ❌ Chưa có trong CIC | 2 | Schema CIC không có dữ liệu tương ứng |
| 🔵 Không liên quan CIC | 24 | Từ form khách hàng / tính nội bộ |

---

## ✅ Features khớp trực tiếp với CIC

| Feature model | Cột CIC | Cách map | File |
|---|---|---|---|
| `num_active_credit` | `total_active_loans` | Trực tiếp | `cic_service.enrich_from_cic()` |
| `num_active_credit_bureau` | `total_active_loans` | Alias của `num_active_credit` | `model_feature_builder.py` |
| `total_overdue_amount` | `total_overdue_amount` | Trực tiếp | `cic_service.enrich_from_cic()` |
| `max_credit_overdue_days` | `max_dpd_12m` | Trực tiếp (12m window) | `cic_service.enrich_from_cic()` |
| `has_bad_debt` | `bad_debt_flag` | Trực tiếp | `cic_service.enrich_from_cic()` |
| `num_bureau_records` | `loan_history` (JSON) | `len(loan_history)` | `cic_service.enrich_from_cic()` |
| `num_cb_queries` | `num_credit_inquiries` | Trực tiếp | `cic_service.derive_bureau_features()` |

> `num_active_credit_bureau` là alias của `num_active_credit` trong SQL training
> (`num_active_credit AS num_active_credit_bureau`), nên cùng giá trị.

---

## ⚠️ Features xấp xỉ từ `loan_history` (thiếu cửa sổ thời gian)

Các feature này được tính trong `cic_service.derive_bureau_features()` từ mảng JSON
`loan_history` (mỗi entry gồm: `lender`, `amount`, `status`, `dpd_max`).

**Vấn đề:** `loan_history` không có `opened_at` / `closed_at`, nên không thể lọc theo
cửa sổ thời gian (24 tháng, 3 tháng gần nhất). Các feature này tính trên **toàn bộ lịch sử**,
không chỉ giai đoạn gần nhất như trong training data.

| Feature model | Nguồn training (Home Credit) | Tính xấp xỉ từ CIC | Sai lệch |
|---|---|---|---|
| `avg_dpd_recent` | `avgdbddpdlast3m_4187120P` — trung bình DPD 3 tháng gần nhất | `mean(loan_history[].dpd_max)` toàn lịch sử | Có thể thấp hơn thực tế nếu các khoản cũ ít lỗi |
| `max_dpd_24m` | `maxdpdlast24m_143P` — DPD tối đa 24 tháng | `max(loan_history[].dpd_max)` toàn lịch sử | Có thể cao hơn nếu có khoản cũ quá hạn nhiều |
| `num_installs_dpd10` | `numinstlswithdpd10_728L` — số kỳ quá hạn >10 ngày | `count(loan_history[].dpd_max > 10)` | Overcount nếu khoản cũ đã đóng lâu |
| `max_overdue_amount` | Từ gold transform, max số tiền quá hạn | `max(amount where status="overdue")` | Dùng tổng khoản vay, không phải số tiền quá hạn thực tế |

---

## ❌ Features chưa có trong CIC — dùng artifact default (median training)

Hai features này **không xuất hiện** trong `derive_bureau_features()` và không có
trường tương ứng trong `cic_credit_records`. Chúng fall-through xuống
`artifact["feature_defaults"]` (median của training data = giá trị cố định tại inference).

| Feature model | Nguồn training (Home Credit) | Ý nghĩa | Tại sao CIC thiếu | Giá trị hiện tại |
|---|---|---|---|---|
| `total_prolongations` | `prolongationcount_599L` (applprev) — tổng số lần gia hạn khoản vay | Số lần khách đã xin gia hạn/rollover | CIC không track số lần gia hạn | Median training ≈ 0 |
| `cb_queries_30d` | `days30_165L` (credit_bureau) — số query tín dụng 30 ngày qua | Tần suất bị tra cứu gần đây (nhiều = đang vay nhiều nơi) | CIC chỉ có `num_credit_inquiries` tổng, không chia theo cửa sổ 30 ngày | Median training ≈ 0–1 |

### Tác động

- `total_prolongations`: Feature có feature importance **thấp** trong model — ít ảnh hưởng.
- `cb_queries_30d`: Feature có feature importance **trung bình** — nếu khách đang apply
  vay nhiều nơi cùng lúc, model sẽ không phát hiện được qua kênh này.

### Cách fix (không cần retrain)

Thêm 2 cột vào `cic_credit_records`:

```sql
ALTER TABLE cic_credit_records
  ADD COLUMN total_prolongations   INT     NOT NULL DEFAULT 0,
  ADD COLUMN cb_queries_30d        INT     NOT NULL DEFAULT 0;
```

Sau đó map trong `cic_service.derive_bureau_features()`:

```python
out["total_prolongations"] = cic.total_prolongations
out["cb_queries_30d"]      = cic.cb_queries_30d
```

---

## 🔵 Features không liên quan CIC

Các feature này đến từ form khách hàng hoặc được tính nội bộ — CIC không cần cung cấp.

| Nhóm | Features |
|---|---|
| Thu nhập & khoản vay | `monthly_income`, `loan_amount`, `term`, `dti`, `loan_amount_to_income`, `log_monthly_income`, `high_dti_flag`, `payment_to_income` |
| Gánh nặng nợ (tính từ form) | `current_debt_ratio`, `total_debt_to_income` |
| Lịch sử đơn vay nội bộ | `num_previous_loans`, `previous_default_rate` |
| Nhân khẩu học | `age_years`, `years_employed`, `education_ordinal`, `is_homeowner`, `income_verifiable_flag`, `is_married_flag` |
| Missing flags | `income_missing_flag`, `dti_missing_flag` |
| Categorical | `employment_status`, `occupation_type` |

> `dti` từ phiên bản sau fix (commit `39d0856`) đã bao gồm `total_monthly_installment`
> từ CIC: `dti = (loan_amount/term + cic_monthly) / monthly_income`.

---

## Sơ đồ luồng feature tại inference

```
Khách điền form
    │
    ├─► Form fields ──────────────────────────────────► model_feature_builder.py
    │                                                         │
    └─► CCCD lookup → cic_credit_records                      │
            │                                                 │
            ├─ total_active_loans      → num_active_credit ──►│
            ├─ total_overdue_amount    → total_overdue_amount ►│
            ├─ max_dpd_12m             → max_credit_overdue ──►│
            ├─ bad_debt_flag           → has_bad_debt ─────────►│
            ├─ num_credit_inquiries    → num_cb_queries ────────►│
            ├─ total_monthly_installment → cic_monthly (DTI) ──►│
            │                                                 │
            ├─ loan_history[].dpd_max  → avg_dpd_recent  ⚠️ ──►│
            │                          → max_dpd_24m      ⚠️ ──►│
            │                          → num_installs_dpd10 ⚠️►│
            │                                                 │
            ├─ (thiếu) total_prolongations  → artifact default ❌
            └─ (thiếu) cb_queries_30d       → artifact default ❌
```

---

*Cập nhật lần cuối: 2026-05-21*
*Tham chiếu: `backend/services/cic_service.py`, `backend/models/cic.py`,
`machinelearning/ml/retrain_customer_model.py`, `machinelearning/database/transform_silver_hcv2.sql`*
