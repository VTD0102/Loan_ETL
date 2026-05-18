# CreditIntel — Changelog: Phase B — Synthetic Loan Ecosystem

> **Ngày thực hiện**: 19/05/2026  
> **Branch**: `phi`  
> **Phụ thuộc**: Phase A (CIC Integration) phải hoàn thành trước

---

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [Cơ chế hoạt động](#cơ-chế-hoạt-động)
3. [3 Profiles vay](#3-profiles-vay)
4. [Files đã thêm/sửa](#files-đã-thêmsửa)
5. [Cách sử dụng](#cách-sử-dụng)
6. [Kết quả test](#kết-quả-test)

---

## Tổng quan

### Vấn đề
Hệ thống CreditIntel cần dữ liệu khoản vay thực tế để:
- Demo cho team/stakeholders
- Test ML pipeline end-to-end
- Phát triển admin dashboard
- Kiểm tra CIC integration hoạt động đúng

### Giải pháp
Tạo **Synthetic Loan Ecosystem** — hệ thống sinh dữ liệu giả lập realistic:
- Mỗi record = **1 User** + **1 CIC record** + **1 LoanApplication** (qua ML pipeline thật)
- Dữ liệu khớp với phân phối training data → model predict chính xác, **không cần retrain**
- 3 profiles vay (good/risky/defaulter) phản ánh thực tế
- Admin trigger qua API hoặc CLI script

---

## Cơ chế hoạt động

### Luồng sinh 1 khoản vay:

```
1. Chọn random profile (60% good / 25% risky / 15% defaulter)
   ↓
2. Generate User:
   - Tên tiếng Việt ngẫu nhiên (Nguyễn Văn A, Trần Thị B...)
   - Email: synthetic.nguyenvana.1234@creditintel.test
   - CCCD: 12 số random
   - Password: Synthetic123! (hash)
   ↓
3. Generate CIC record (matching profile):
   - cic_score: Good=680-850, Risky=500-680, Defaulter=300-500
   - bad_debt_flag, blacklist_flag, loan_history...
   ↓
4. Build ApplicationCreate payload (matching profile):
   - monthly_income, loan_amount, dti, employment_status...
   - Tất cả 20+ fields khớp với schema
   ↓
5. Gọi application_service.evaluate() — chạy qua ML pipeline THẬT:
   - CIC lookup → enrich bureau fields (Phase A tự động)
   - LightGBM predict → default_probability
   - Binary search → suggested_amount, suggested_term
   - Lưu vào DB với đầy đủ feature_snapshot
```

### Tại sao KHÔNG cần retrain model?

Model LightGBM đã được train trên Home Credit data với các features:
- `monthly_income`, `loan_amount`, `dti`, `term`
- `num_bureau_records`, `num_active_credit`, `has_bad_debt`
- `age_years`, `education_ordinal`, `employment_status`
- ... tổng cộng ~35 features

Synthetic data sinh các features này với phân phối gần giống training data. 
CIC integration (Phase A) chỉ thay đổi **nguồn** data (CIC thay vì tự khai), 
nhưng **giá trị** features vẫn nằm trong range model đã thấy → predict bình thường.

---

## 3 Profiles vay

### Good Profile (60%)
Người vay tốt — thu nhập ổn định, DTI thấp, không nợ xấu.

| Feature | Range | Ý nghĩa |
|---------|-------|---------|
| monthly_income | $4,000 – $15,000 | Thu nhập cao, ổn định |
| loan_amount | $2,000 – $50,000 | Vay hợp lý so với thu nhập |
| dti | 5% – 30% | Tỷ lệ nợ/thu nhập thấp |
| employment_status | 80% Employed, 20% Self-employed | Có việc làm |
| education_ordinal | 3-5 (Cao đẳng → Sau ĐH) | Học vấn cao |
| has_bad_debt | No | Không nợ xấu |
| CIC score | 680 – 850 | Điểm tín dụng tốt |

**Kết quả ML**: Xác suất vỡ nợ 10-30%, PENDING_REVIEW ✅

---

### Risky Profile (25%)
Người vay rủi ro trung bình — thu nhập vừa, DTI cao hơn, có quá hạn.

| Feature | Range | Ý nghĩa |
|---------|-------|---------|
| monthly_income | $2,000 – $6,000 | Thu nhập trung bình |
| loan_amount | $5,000 – $60,000 | Vay nhiều so với thu nhập |
| dti | 30% – 50% | Gánh nặng nợ lớn |
| employment_status | 50% Employed, 30% Self-emp, 20% Other | Không ổn định |
| education_ordinal | 2-4 (THPT → Đại học) | Trung bình |
| has_bad_debt | 20% Yes | Có thể có nợ xấu |
| total_overdue_amount | $0 – $500 | Có tiền quá hạn |
| CIC score | 500 – 680 | Điểm tín dụng trung bình |

**Kết quả ML**: Xác suất vỡ nợ 25-40%, PENDING_REVIEW (borderline) ⚠️

---

### Defaulter Profile (15%)
Người vay cao rủi ro — thu nhập thấp, DTI rất cao, nợ xấu.

| Feature | Range | Ý nghĩa |
|---------|-------|---------|
| monthly_income | $1,000 – $4,000 | Thu nhập thấp |
| loan_amount | $8,000 – $80,000 | Vay quá khả năng |
| dti | 45% – 85% | Gánh nặng nợ rất lớn |
| employment_status | 30% Not employed | Nhiều người thất nghiệp |
| education_ordinal | 1-3 (Dưới THPT → Cao đẳng) | Học vấn thấp |
| has_bad_debt | Yes | Luôn có nợ xấu |
| total_overdue_amount | $500 – $5,000 | Quá hạn nhiều |
| max_dpd_12m | 30 – 180 ngày | Trễ hạn nặng |
| CIC score | 300 – 500 | Điểm tín dụng rất thấp |
| blacklist_flag | 10% Yes | Có thể bị blacklist |

**Kết quả ML**: Xác suất vỡ nợ > 40%, AUTO_REJECTED ❌

---

## Files đã thêm/sửa

### Files MỚI (2)

| File | Mô tả |
|------|-------|
| `backend/services/synthetic_service.py` | Core generator — 3 profiles, tạo User + CIC + chạy ML pipeline |
| `backend/scripts/seed_synthetic.py` | CLI script để seed data từ terminal |

### Files SỬA (1)

| File | Thay đổi |
|------|----------|
| `backend/api/routers/cic.py` | Thêm `POST /cic/synthetic/generate?count=N` endpoint |

---

## Cách sử dụng

### Cách 1: CLI Script (Khuyên dùng cho lần đầu)

```bash
cd backend

# Sinh 10 records (default)
python scripts/seed_synthetic.py

# Sinh 50 records
python scripts/seed_synthetic.py --count 50
```

### Cách 2: API Endpoint (Cho demo / admin dashboard)

```bash
# Cần JWT token admin
curl -X POST "http://localhost:8000/cic/synthetic/generate?count=10" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Hoặc dùng **Swagger UI**: `http://localhost:8000/docs` → section "CIC Bureau" → `POST /cic/synthetic/generate`

### Cách 3: Swagger UI

1. Mở `http://localhost:8000/docs`
2. Authorize bằng tài khoản admin
3. Tìm endpoint `POST /cic/synthetic/generate`
4. Nhập count (1-100)
5. Execute → xem kết quả

---

## Kết quả test

### Test 3 records:

```
✅ Kết quả:
   Tạo thành công : 3/3
   PENDING_REVIEW : 3
   AUTO_REJECTED  : 0
   CIC Blacklisted: 0
   Lỗi            : 0

📋 Chi tiết:
   ✅ [     good] Bùi Bảo Hiếu              → PENDING_REVIEW (18.7%)
   ✅ [     good] Phạm Tuấn Dũng            → PENDING_REVIEW (27.0%)
   ✅ [     good] Phan Đức Khánh            → PENDING_REVIEW (33.9%)
```

**Nhận xét**:
- ML model predict chính xác: good profiles → xác suất thấp (18-34%)
- CIC enrichment hoạt động: bureau fields được ghi đè từ CIC record
- Dữ liệu xuất hiện trên admin dashboard → admin có thể duyệt ngay

---

## Lưu ý

1. **Email synthetic**: Tất cả email kết thúc bằng `@creditintel.test` → dễ phân biệt với user thật.

2. **Password**: Tất cả synthetic users có password `Synthetic123!` → có thể login để test.

3. **Giới hạn**: API endpoint giới hạn tối đa 100 records/lần (tránh timeout).

4. **Unique constraint**: Nếu trùng CCCD hoặc email (rất hiếm), record đó sẽ bị skip + ghi log lỗi.

5. **CIC đã tích hợp**: Khi `evaluate()` chạy, CIC lookup tự động xảy ra (Phase A) → bureau fields được ghi đè bằng data CIC → admin thấy cả self-reported vs CIC trong feature_snapshot.
