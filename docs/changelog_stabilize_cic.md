# CreditIntel — Changelog: Stabilization + CIC Integration

> **Ngày thực hiện**: 19/05/2026  
> **Branch**: `phi`  
> **Người thực hiện**: Team CreditIntel

---

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [Phần 1: Stabilization — Sửa lỗi core system](#phần-1-stabilization)
3. [Phần 2: CIC/Bureau Integration](#phần-2-cic-integration)
4. [Danh sách file thay đổi](#danh-sách-file-thay-đổi)
5. [Hướng dẫn chạy migration](#hướng-dẫn-chạy-migration)
6. [Kiểm chứng](#kiểm-chứng)

---

## Tổng quan

Đợt commit này gồm **2 phần chính**:

| Phần | Mục đích | Số file |
|------|----------|---------|
| **Stabilization** | Sửa bugs nghiêm trọng, chống data corruption, transaction safety | 5 files sửa |
| **CIC Integration** | Thêm hệ thống CIC giả lập (Credit Information Center) | 4 files mới + 6 files sửa |

---

## Phần 1: Stabilization

### 1.1 Fix `_load_both()` — Core flow crash

**File**: `backend/services/application_service.py`

**Vấn đề**: Hàm `confirm()` (xác nhận đơn vay — Phase 2 của flow nộp đơn) gọi `ml_service._load_both()` nhưng function này **không tồn tại** → crash 100% khi user xác nhận đơn.

**Sửa**: Đổi sang `ml_service._load()` (đã tồn tại) và sửa lại tham số cho đúng signature của `validate_confirmed_values()`.

**Ý nghĩa**: Trước khi sửa, **toàn bộ flow nộp đơn vay bị chặn** — user chỉ có thể xem preview ML nhưng không thể submit đơn thật.

---

### 1.2 Unique Partial Index — Chống duplicate applications

**File**: `backend/init_db.py`

**Vấn đề**: Không có cơ chế DB-level ngăn 1 user tạo nhiều đơn vay cùng lúc (race condition khi double-click hoặc network retry).

**Sửa**: Thêm unique partial index:
```sql
CREATE UNIQUE INDEX idx_one_active_app_per_user
ON loan_applications(user_id)
WHERE status NOT IN ('AUTO_REJECTED','ADMIN_REJECTED','REJECTED');
```

**Ý nghĩa**: Database tự động chặn duplicate — dù 2 request chạy song song, chỉ 1 cái commit thành công. Cái còn lại nhận lỗi `IntegrityError` → trả 400 cho user.

**Lưu ý**: Đã clean 3 records duplicate có sẵn trong DB trước khi tạo index.

---

### 1.3 Transaction Safety — Rollback khi lỗi

**Files**: `application_service.py`, `chat_service.py`, `admin_service.py`

**Vấn đề**: Toàn bộ services **không có `db.rollback()`**. Khi exception xảy ra giữa chừng (ví dụ: RAG timeout, DB constraint fail), database có thể ở trạng thái nửa-commit.

**Sửa**: Wrap tất cả `db.commit()` trong `try/except`:
- `application_service`: evaluate, confirm, submit_personal_info → bắt `IntegrityError` trả lỗi có nghĩa
- `chat_service`: assistant message commit → rollback + log nếu fail
- `admin_service`: approve, reject → rollback + trả 500

**Ý nghĩa**: Đảm bảo **tính toàn vẹn dữ liệu** — mỗi operation hoặc thành công hoàn toàn, hoặc rollback hoàn toàn. Không có trạng thái "nửa chừng".

---

### 1.4 Fix document_service — Không tạo fake PersonalInfo

**File**: `backend/services/document_service.py`

**Vấn đề**: Khi upload documents mà chưa có PersonalInfo, code tạo record với dữ liệu giả (`full_name=""`, `id_card_number=uuid4()`) → block `submit_personal_info()` vĩnh viễn vì "đã tồn tại".

**Sửa**: Nếu PersonalInfo chưa có, chỉ lưu document URLs tạm vào `feature_snapshot._pending_document_urls` trên LoanApplication. Không tạo fake PersonalInfo, không đổi status sang INFO_SUBMITTED.

**Ý nghĩa**: User có thể upload docs trước hoặc sau khi submit personal info, không bị conflict. Và CIC lookup sẽ không tìm thấy CCCD giả (UUID) trong database.

---

### 1.5 Security: .env.example

**File**: `backend/.env.example` (MỚI)

Tạo file mẫu `.env.example` với placeholder values để team members biết cần set những biến môi trường nào mà không lộ secrets thật.

---

## Phần 2: CIC Integration

### CIC là gì?

**CIC (Credit Information Center)** — trong thực tế là bên thứ 3 (ví dụ: CIC Việt Nam) lưu trữ lịch sử tín dụng của công dân. Mỗi CCCD (Căn cước công dân, 12 số) gắn với:
- Điểm tín dụng CIC (300-900)
- Số khoản vay đang có
- Tổng dư nợ, tiền quá hạn
- Có nợ xấu không
- Có nằm trong blacklist không
- Lịch sử chi tiết từng khoản vay

Hệ thống CreditIntel **giả lập** bên thứ 3 này bằng bảng `cic_credit_records`.

---

### 2.1 Bảng `cic_credit_records` — Database

**File mới**: `backend/models/cic.py`

| Column | Kiểu | Ý nghĩa |
|--------|------|---------|
| `id` | UUID PK | Primary key |
| `cccd` | VARCHAR(12) UNIQUE | Số CCCD — lookup key |
| `full_name` | VARCHAR | Họ tên |
| `cic_score` | INT | Điểm CIC (300-900) |
| `total_active_loans` | INT | Số khoản vay đang hoạt động |
| `total_outstanding_debt` | NUMERIC | Tổng dư nợ |
| `total_overdue_amount` | NUMERIC | Tổng tiền quá hạn |
| `max_dpd_12m` | INT | Ngày trễ hạn tối đa (12 tháng gần nhất) |
| `num_credit_inquiries` | INT | Số lần hỏi tín dụng |
| `bad_debt_flag` | BOOLEAN | Có nợ xấu |
| `blacklist_flag` | BOOLEAN | Nằm trong blacklist → cấm vay |
| `blacklist_reason` | TEXT | Lý do blacklist |
| `loan_history` | JSON | Mảng chi tiết từng khoản vay cũ |
| `created_at` | TIMESTAMP | Ngày tạo |
| `updated_at` | TIMESTAMP | Ngày cập nhật |

**Đặc điểm**: Bảng này **ĐỘC LẬP** với `users` — giống CIC thật, bất kỳ CCCD nào cũng có thể có record dù chưa đăng ký tài khoản CreditIntel.

---

### 2.2 CCCD trên Users — Đăng ký tài khoản

**Files sửa**: `models/user.py`, `schemas/user.py`, `services/auth_service.py`

- Bảng `users` thêm column `cccd VARCHAR(12) UNIQUE`
- Khi đăng ký, bắt buộc nhập CCCD (đúng 12 chữ số)
- Check unique: không cho 2 tài khoản dùng cùng 1 CCCD
- CCCD là cầu nối giữa `users` → `cic_credit_records`

---

### 2.3 CIC Service — Logic tra cứu & enrichment

**File mới**: `backend/services/cic_service.py`

3 functions chính:

| Function | Mô tả |
|----------|-------|
| `lookup_by_cccd(db, cccd)` | Tra cứu CIC record theo CCCD. Return `None` nếu không tìm thấy. |
| `enrich_from_cic(cic)` | Map CIC fields → bureau fields dùng trong ML model |
| `apply_cic_to_payload(payload, cic)` | **Quan trọng nhất**: Lưu giá trị user tự khai → ghi đè bằng data CIC → trả comparison dict |

**`apply_cic_to_payload`** hoạt động:

```
Input:  payload (user tự khai: num_bureau_records=0, has_bad_debt=false)
        cic    (CIC verified: total_active_loans=3, bad_debt_flag=true)

Output: {
  "cic_applied": true,
  "cic_score": 580,
  "self_num_bureau_records": 0,     ← user khai
  "self_has_bad_debt": false,       ← user khai
  ...
}

Side effect: payload.num_bureau_records = 3     ← đã ghi đè
             payload.has_bad_debt = true        ← đã ghi đè
```

Sau đó ML model nhận `payload` đã được enrich → predict chính xác hơn.

---

### 2.4 CIC API Endpoints

**File mới**: `backend/api/routers/cic.py`

| Endpoint | Auth | Mô tả |
|----------|------|-------|
| `GET /cic/me` | Customer | Xem CIC record của mình (dựa trên CCCD đã đăng ký) |
| `GET /cic/lookup/{cccd}` | Admin | Tra cứu CIC bất kỳ CCCD (để xem trước khi duyệt đơn) |

---

### 2.5 Tích hợp CIC vào loan evaluation flow

**File sửa**: `backend/services/application_service.py`

Cả `evaluate()` và `confirm()` đều thêm logic CIC:

```
User nộp đơn
  ↓
Lấy user.cccd
  ↓
CIC lookup (cic_credit_records)
  ↓
├── blacklist_flag = true  → AUTO_REJECTED ngay lập tức (không cần ML)
├── CIC tìm thấy          → ghi đè bureau fields → chạy ML với data CIC thật
└── CIC không tìm thấy    → chạy ML với data user tự khai (fallback)
  ↓
feature_snapshot lưu cả comparison {self_has_bad_debt vs has_bad_debt}
  → Admin thấy user có khai sai không
```

---

## Danh sách file thay đổi

### Files MỚI (5)

| File | Mô tả |
|------|-------|
| `backend/models/cic.py` | ORM model bảng `cic_credit_records` |
| `backend/schemas/cic.py` | Pydantic schemas cho CIC API |
| `backend/services/cic_service.py` | Business logic: lookup, enrich, apply |
| `backend/api/routers/cic.py` | REST endpoints: `/cic/me`, `/cic/lookup/{cccd}` |
| `backend/.env.example` | Template biến môi trường (không chứa secrets) |

### Files SỬA (7)

| File | Thay đổi |
|------|----------|
| `backend/models/user.py` | Thêm `cccd` column |
| `backend/models/__init__.py` | Export `CICRecord` |
| `backend/schemas/user.py` | Thêm `cccd` vào UserCreate (validator 12 số) + UserRead |
| `backend/services/auth_service.py` | Lưu cccd khi register + check unique |
| `backend/services/application_service.py` | Fix `_load_both()`, thêm CIC enrichment, IntegrityError handling |
| `backend/services/chat_service.py` | Rollback guard cho assistant message commit |
| `backend/services/admin_service.py` | Rollback guard cho approve/reject |
| `backend/services/document_service.py` | Không tạo fake PersonalInfo nữa |
| `backend/init_db.py` | Migration: cccd column + unique partial index |
| `backend/main.py` | Mount CIC router |

---

## Hướng dẫn chạy migration

Sau khi pull code mới, chạy:

```bash
# Từ thư mục gốc project
source venv/bin/activate
cd backend
python init_db.py
```

Kết quả mong đợi:
```
✅ THÀNH CÔNG! Đã tạo xong các bảng
✅ Column migrations hoàn tất.     (bao gồm users.cccd)
✅ Index migrations hoàn tất.      (idx_one_active_app_per_user)
```

Bảng `cic_credit_records` được tạo tự động bởi `Base.metadata.create_all()`.

---

## Kiểm chứng

Sau khi chạy migration, verify:

```bash
# Server khởi động OK
uvicorn main:app --reload

# CIC endpoints hiện trong Swagger
# Mở http://localhost:8000/docs → thấy section "CIC Bureau"
```

### Test nhanh:
1. **Register**: POST `/auth/register` phải gửi thêm `cccd` (12 chữ số)
2. **CIC Lookup**: GET `/cic/me` (cần JWT token)
3. **Apply**: POST `/applications/evaluate` — nếu user có CIC record, bureau fields sẽ bị ghi đè tự động

---

> **Ghi chú**: Bảng `cic_credit_records` hiện đang trống. Dữ liệu CIC sẽ được seed ở bước tiếp theo (Synthetic Data Generator).
