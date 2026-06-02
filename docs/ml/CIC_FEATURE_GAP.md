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
| ✅ Đã kết nối sau fix | 5 | Trước đây hardcode/thiếu schema — đã sửa |
| ⚠️ Xấp xỉ từ CIC | 1 | Dùng `max_dpd_12m` thay cho window 24m |
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

### 2.4 ✅ Features trước đây hardcode = 0 — đã fix

`_build_features()` dùng `bf.get(..., default)` thay hardcode;
`_score_application()` nhận `bureau_db` và gọi `derive_bureau_features()` trước khi build vector.

| Feature model | Nguồn CIC | Trạng thái |
|---|---|---|
| `avg_dpd_recent` | `mean(loan_history[].dpd_max)` cửa sổ 3m | ✅ Đã kết nối |
| `num_installs_dpd10` | `count(loan_history[].dpd_max > 10)` | ✅ Đã kết nối |
| `num_cb_queries` | `num_credit_inquiries` (trực tiếp) | ✅ Đã kết nối |

### 2.5 ✅ Features trước đây thiếu trong CIC schema — đã bổ sung

| Feature model | Nguồn training (Home Credit) | Ý nghĩa | Trạng thái |
|---|---|---|---|
| `total_prolongations` | `prolongationcount_599L` | Số lần xin gia hạn khoản vay | ✅ Cột có trong `models/cic.py`, `derive_bureau_features()` đọc |
| `cb_queries_30d` | `days30_165L` | Số query tín dụng 30 ngày qua | ✅ Cột có trong `models/cic.py`, `derive_bureau_features()` đọc |

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

- **LightGBM v4** và **Scorecard LR** đều tận dụng đầy đủ dữ liệu CIC có sẵn sau khi các fix được áp dụng.
- Cả hai model dùng cùng `derive_bureau_features()` — kết quả nhất quán giữa quyết định phê duyệt (LightGBM) và điểm FICO (Scorecard).
- Sai lệch window thời gian nhỏ còn lại: `max_dpd_24m` dùng `max_dpd_12m` từ CIC — acceptable tradeoff vì window 24m không có trong schema CIC.

### Trạng thái fix

| Ưu tiên | Việc làm | Trạng thái | Chi tiết |
|---|---|---|---|
| 🔴 Cao | Scorecard: gọi `derive_bureau_features()` thay vì hardcode 0 | ✅ Hoàn thành | `_score_application()` nhận `bureau_db`, gọi `lookup_by_cccd()` + `derive_bureau_features()`; `_build_features()` dùng `bf.get()` thay hardcode |
| 🟡 Trung bình | Thêm `cb_queries_30d` + `total_prolongations` vào CIC schema | ✅ Hoàn thành | Cả hai cột có trong `models/cic.py`; `derive_bureau_features()` đọc và trả về; `synthetic_service.py` sinh giá trị realistic |
| 🟢 Thấp | Thêm `opened_at`/`closed_at` vào `loan_history` entries | ✅ Hoàn thành | `synthetic_service.py` sinh timestamps; `derive_bureau_features()` dùng cửa sổ 3m/24m khi có timestamps, fallback toàn lịch sử cho record cũ |

---

## Phần 4 — Phân tích nguyên nhân: tại sao Scorecard hardcode = 0?

### 4.1 Giả thuyết của bạn

> *"Phải chăng vì giao diện web CIC không cung cấp các feature đó, nên khi khách hàng
> điền đơn vay xong nhấn nộp thì mặc định hardcode = 0?"*

**Đúng một nửa** — cần phân biệt hai nhóm feature riêng biệt.

---

### 4.2 Nhóm 1 — Feature CIC có nhưng Scorecard bỏ qua (lỗi implementation)

| Feature | Giá trị cứng | Dữ liệu CIC |
|---|---|---|
| `avg_dpd_recent` | `0.0` | `mean(loan_history[].dpd_max)` — đã có trong `derive_bureau_features()` |
| `num_installs_dpd10` | `0` | `count(loan_history[].dpd_max > 10)` — đã có trong `derive_bureau_features()` |
| `num_cb_queries` | `0` | `cic_credit_records.num_credit_inquiries` — đã có trong `derive_bureau_features()` |

**Những feature này KHÔNG phải do khách hàng nhập trên giao diện web.**
Chúng được backend tự động tra cứu từ `cic_credit_records` theo CCCD khi khách nộp đơn,
cùng lúc với `total_active_loans`, `total_overdue_amount`, v.v. (flow dưới đây):

```
Khách nhấn "Nộp đơn"
    │
    ▼
application_service.evaluate()
    │
    ├─► apply_cic_to_payload()  ← ghi bureau fields vào payload + DB
    │       ├ num_active_credit, total_overdue_amount, has_bad_debt, ...
    │       └ total_monthly_installment → cộng vào DTI
    │
    ├─► [LightGBM] ml_service.predict()
    │       └─► build_model_input()
    │               └─► cic_service.derive_bureau_features(cic_record)
    │                       ├ avg_dpd_recent       ✅ được dùng
    │                       ├ num_installs_dpd10   ✅ được dùng
    │                       └ num_cb_queries       ✅ được dùng
    │
    └─► [Scorecard] credit_score_service._score_application(app, db)
            └─► _build_features(app, ...)
                    ├ avg_dpd_recent     → hardcode 0.0  ❌  ← KHÔNG gọi derive_bureau_features()
                    ├ num_installs_dpd10 → hardcode 0    ❌
                    └ num_cb_queries     → hardcode 0    ❌
```

**Nguyên nhân thực sự:** `_build_features()` được viết trước khi `derive_bureau_features()`
tồn tại. Khi LightGBM pipeline được cập nhật để gọi hàm này, `credit_score_service.py`
không được cập nhật theo — đây là **implementation gap**, không phải data unavailability.

Dữ liệu CIC đã có sẵn trong database. Không cần thay đổi form, không cần retrain model.

---

### 4.3 Nhóm 2 — Feature CIC thực sự không có (hardcode đúng)

| Feature | Giá trị cứng | Lý do |
|---|---|---|
| `total_prolongations` | `0` | CIC schema (`cic_credit_records`) không có cột track số lần gia hạn |
| `cb_queries_30d` | `0` | CIC chỉ có tổng `num_credit_inquiries`, không phân chia theo window 30 ngày |

**Đây mới là trường hợp "web CIC không cung cấp"** — không phải do giao diện, mà do
hệ thống CIC mô phỏng chưa lưu granularity đó. Hardcode = 0 là fallback đúng (median
training cũng ≈ 0 cho cả hai feature này).

---

### 4.4 Phương án xử lý — Fix Scorecard (không cần retrain)

**Mục tiêu:** `_score_application()` lấy CIC record và truyền `bureau_features` vào
`_build_features()` — giống cách LightGBM pipeline đã làm.

**Bước 1** — Sửa `_build_features()` nhận thêm `bureau_features` dict:

```python
def _build_features(app, num_previous_loans: int, previous_default_rate: float,
                    dti_p75: float, bureau_features: dict | None = None) -> pd.DataFrame:
    bf = bureau_features or {}
    ...
    return pd.DataFrame([{
        ...
        "avg_dpd_recent":     bf.get("avg_dpd_recent", 0.0),   # ← thay hardcode
        "num_installs_dpd10": bf.get("num_installs_dpd10", 0),  # ← thay hardcode
        "num_cb_queries":     bf.get("num_cb_queries", 0),      # ← thay hardcode
        ...
    }])
```

**Bước 2** — Sửa `_score_application()` để fetch CIC và gọi `derive_bureau_features()`:

```python
def _score_application(app, db: Session) -> dict:
    from services.cic_service import get_cic_record, derive_bureau_features
    ...
    bureau_features = {}
    try:
        cic_record = get_cic_record(str(app.user_id), bureau_db=...)
        if cic_record:
            bureau_features = derive_bureau_features(cic_record)
    except Exception:
        pass  # graceful fallback — dùng 0 nếu CIC không có

    df = _build_features(app, num_prev_loans, prev_default_rate, dti_p75, bureau_features)
    ...
```

> **Lưu ý:** `_score_application()` hiện nhận `db: Session` (Supabase DB). Để fetch
> CIC cần thêm `bureau_db: Session` hoặc dùng một connection riêng — xem cách
> `application_service.evaluate()` xử lý hai session.

**Kết quả sau fix:**
- Scorecard không còn inflate điểm FICO cho khách hàng có DPD xấu
- Ba feature `avg_dpd_recent`, `num_installs_dpd10`, `num_cb_queries` nhất quán
  giữa LightGBM và Scorecard
- Không cần retrain bất kỳ model nào

---

*Cập nhật lần cuối: 2026-06-02*
*Tham chiếu: `backend/services/cic_service.py`, `backend/services/credit_score_service.py`,
`backend/models/cic.py`, `machinelearning/ml/retrain_customer_model.py`,
`machinelearning/ml/train_scorecard.py`, `machinelearning/database/transform_silver_hcv2.sql`*
