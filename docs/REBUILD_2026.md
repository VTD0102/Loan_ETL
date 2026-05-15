# REBUILD_2026 — CreditIntel Cải Tổ Toàn Diện

> **Ngày:** Tháng 5 năm 2026 | **Branch:** huy | **Phiên bản model:** customer_lgbm_v3

---

## 1. Tổng quan thay đổi

Tài liệu này mô tả toàn bộ quá trình cải tổ hệ thống vay vốn CreditIntel, bao gồm:

- Luồng nộp đơn hai giai đoạn mới (đánh giá → xác nhận)
- Model ML được huấn luyện lại với 28 đặc trưng (v3 — loại bỏ ext_source_1/3, thêm occupation_type + years_employed)
- Tất cả các trường trong form đều bắt buộc (không còn điền median tại inference)
- Modal từ chối hiển thị gợi ý khoản vay + nút chat AI
- Modal xác nhận trước duyệt cho phép người dùng điều chỉnh thông số vay
- Luồng tải lên tài liệu (Supabase Storage hoặc lưu local nếu không cấu hình)
- Pipeline ETL được cập nhật thêm các cột mới

---

## 2. Danh sách file đã thay đổi

### Tầng ETL

| File | Thay đổi |
|------|---------|
| `etl/load_bronze.py` | Thêm `OCCUPATION_TYPE`; xóa `EXT_SOURCE_1`, `EXT_SOURCE_3`; giữ `DAYS_EMPLOYED` |
| `database/transform_silver_homecredit.sql` | Thêm `years_employed` (ABS(DAYS_EMPLOYED)/365.25, 365243→0) và `occupation_type` (COALESCE với 'Unknown') |
| `database/transform_gold_homecredit.sql` | Thêm `s.years_employed`, `s.occupation_type` vào SELECT chính |
| `ml/validate_data.py` | Thêm `years_employed` và `occupation_type` vào `REQUIRED_COLUMNS` |

### Tầng ML

| File | Thay đổi |
|------|---------|
| `ml/retrain_customer_model.py` | Viết lại toàn bộ — 28 đặc trưng, OrdinalEncoder cho 2 đặc trưng phân loại, n_estimators=500, num_leaves=63 |

### Tầng Backend

| File | Thay đổi |
|------|---------|
| `backend/models/application.py` | Xóa ext_source_1/3; thêm occupation_type, years_employed |
| `backend/schemas/application.py` | Tất cả trường từng là Optional nay bắt buộc; thêm ApplicationConfirm, ApplicationEvaluateResponse |
| `backend/services/model_feature_builder.py` | Xóa logic điền median; 22 đầu vào người dùng ánh xạ trực tiếp; thêm occupation_type, years_employed |
| `backend/services/loan_suggestion_service.py` | **MỚI** — tìm kiếm nhị phân khoản vay tối đa an toàn, phát hiện "perfect fit" |
| `backend/services/ml_service.py` | Tích hợp loan_suggestion_service; trả về is_perfect_fit, suggested_amount, suggested_term |
| `backend/services/application_service.py` | Thay `submit()` bằng `evaluate()` + `confirm()`; không lưu DB khi evaluate (trừ AUTO_REJECTED) |
| `backend/services/document_service.py` | **MỚI** — tải lên Supabase Storage với fallback lưu local |
| `backend/api/routers/applications.py` | Thay `/submit` bằng `/evaluate` + `/confirm`; thêm `/{app_id}/documents` |
| `backend/models/personal_info.py` | Thêm bank_account_number, document_urls |
| `backend/schemas/personal_info.py` | Thêm bank_account_number, document_urls |
| `requirements.txt` | Thêm python-multipart, httpx |

### Tầng Frontend

| File | Thay đổi |
|------|---------|
| `frontend/src/services/applications.js` | Thay submitApplication bằng evaluateApplication + confirmApplication; thêm uploadDocuments |
| `frontend/src/pages/customer/Apply/index.jsx` | Viết lại hoàn toàn — 22 trường bắt buộc, SuggestionModal, ChatWidget, luồng nộp đơn hai giai đoạn |

---

## 3. Luồng nộp đơn mới

```
Người dùng điền form (22 trường bắt buộc)
        │
        ▼
POST /applications/evaluate
  ML dự đoán default_prob
        │
  ┌─────┴──────────┐
  │  prob > 0.4    │
  │  AUTO_REJECTED │──► Lưu DB (status=AUTO_REJECTED)
  └─────┬──────────┘     Hiển thị modal từ chối:
        │                - Xác suất vỡ nợ
        │                - Lý do từ chối
        │                - Gợi ý khoản vay phù hợp hơn (nếu có)
        │                - Nút "Chat với AI"
        │
  ┌─────┴──────────────────────────────────┐
  │ prob ≤ 0.4 — PENDING_REVIEW            │
  │                                         │
  │ is_perfect_fit?                         │
  │ (prob < 0.2 VÀ số tiền/kỳ hạn khớp)   │
  └─────┬───────────────────────────────────┘
        │
   CÓ  ├──► Tự động gọi POST /applications/confirm
        │    (không hiện modal)
   KHÔNG└──► Hiển thị SuggestionModal:
               - Badge mức rủi ro (Thấp/Trung bình)
               - Xác suất vỡ nợ
               - Số tiền/kỳ hạn gốc so với gợi ý
               - Người dùng có thể điều chỉnh (giới hạn tại max_safe)
               - Nút "Chat với AI"
               - Nút "Xác nhận gửi đơn"
                       │
                       ▼
               POST /applications/confirm
               (kiểm tra số tiền ≤ max_safe)
                       │
                       ▼
               status = PENDING_REVIEW
```

**Sau khi admin duyệt (AWAITING_INFO):**

```
Khách hàng điền form thông tin cá nhân:
  - Họ tên, số CCCD, số điện thoại, email, ngày sinh, địa chỉ
  - Số tài khoản ngân hàng
  - Tải lên tài liệu (PDF/DOC/DOCX/JPG/PNG, tối đa 10 MB/file)
        │
        ▼
POST /applications/{id}/personal-info
POST /applications/{id}/documents
        │
        ▼
status = INFO_SUBMITTED → admin xem xét → APPROVED / REJECTED
```

---

## 4. Model ML v3 — Bộ đặc trưng (28 tổng cộng)

### Đặc trưng người dùng nhập (22, tất cả bắt buộc)

| Đặc trưng | Kiểu dữ liệu | Nguồn |
|-----------|-------------|-------|
| monthly_income | float | Nhập form |
| loan_amount | float | Nhập form |
| term | int (12/36/60) | Nhập form |
| employment_status | phân loại (5 giá trị) | Dropdown form |
| occupation_type | phân loại (19 giá trị) | Dropdown form |
| years_employed | float | Nhập form (năm, không phải ngày) |
| dti | float | Nhập form |
| is_homeowner | int (0/1) | Toggle form |
| listing_category | int | Nhập form |
| credit_score | int (300-850) | Nhập form |
| income_verifiable_flag | int | Toggle form |
| high_dti_flag | int | Toggle form |
| rating_ordinal | int | Nhập form |
| log_monthly_income | float | Nhập form |
| loan_amount_to_income | float | Nhập form |
| age_years | float | Nhập form |
| gender_male_flag | int | Toggle form |
| education_ordinal | int (1-5) | Dropdown form |
| cnt_children | int | Nhập form |
| cnt_fam_members | int | Nhập form |
| is_married_flag | int | Toggle form |
| has_bad_debt | int | Toggle form |

### Đặc trưng tự tính (4)

| Đặc trưng | Cách tính |
|-----------|----------|
| num_bureau_records | COUNT(*) từ bảng bureau |
| num_active_credit | COUNT(*) tín dụng đang hoạt động |
| total_overdue_amount | SUM(số tiền quá hạn) từ bureau |
| max_credit_overdue_days | MAX(số ngày quá hạn) từ bureau |

### Đặc trưng lịch sử từ DB (2)

| Đặc trưng | Cách tính |
|-----------|----------|
| num_previous_loans | COUNT đơn vay đã nộp trước đây của người dùng |
| previous_default_rate | Tỷ lệ AUTO_REJECTED / tổng đơn trước đây |

### Đặc trưng đã xóa (so với v2)

| Đặc trưng | Lý do |
|-----------|-------|
| ext_source_1 | Điểm từ bên thứ ba — không có tại thời điểm inference |
| ext_source_3 | Điểm từ bên thứ ba — không có tại thời điểm inference |

### Danh mục nghề nghiệp (19 giá trị)

```
Laborers, Core staff, Managers, Drivers, Sales staff,
Accountants, High skill tech staff, Medicine staff, Cooking staff,
Security staff, Cleaning staff, Private service staff, Low-skill Laborers,
Waiters/barmen staff, Secretaries, Realty agents, HR staff, IT staff,
Unknown
```

### Danh mục tình trạng việc làm (5 giá trị)

```
Working, Commercial associate, Pensioner, State servant, Unemployed
```

---

## 5. Hướng dẫn Train / Retrain Model

### Điều kiện tiên quyết

```bash
# Kích hoạt môi trường ảo
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

### Bước 1 — Migration cơ sở dữ liệu (chỉ cần làm lần đầu)

Chạy các câu lệnh ALTER TABLE trong Supabase SQL editor hoặc psql:

```sql
-- Thêm cột mới vào bảng loan_applications
ALTER TABLE loan_applications
  ADD COLUMN IF NOT EXISTS occupation_type  VARCHAR,
  ADD COLUMN IF NOT EXISTS years_employed   NUMERIC(6,2);

-- Thêm cột mới vào bảng personal_info
ALTER TABLE personal_info
  ADD COLUMN IF NOT EXISTS bank_account_number VARCHAR,
  ADD COLUMN IF NOT EXISTS document_urls       JSONB;
```

### Bước 2 — Chạy pipeline ETL

```bash
# Cách A: Chạy toàn bộ pipeline
python -m etl.pipeline

# Cách B: Chạy từng bước thủ công
python -m etl.load_bronze      # → tầng bronze DuckDB (thêm OCCUPATION_TYPE)
python -m etl.etl_silver       # → tầng silver (thêm years_employed, occupation_type)
python -m etl.etl_gold         # → tầng gold (bảng đặc trưng cuối cùng)
```

Kiểm tra kết quả:

```bash
python -c "
import duckdb
con = duckdb.connect('data/etl.duckdb')
print(con.execute('SELECT COUNT(*) FROM gold.hc_features_v1').fetchone())
print(con.execute('SELECT occupation_type, COUNT(*) FROM gold.hc_features_v1 GROUP BY 1 ORDER BY 2 DESC LIMIT 5').fetchdf())
"
```

### Bước 3 — Kiểm tra dữ liệu

```bash
python ml/validate_data.py
```

Kết quả mong đợi: tất cả REQUIRED_COLUMNS có mặt, không có NULL ở cột quan trọng.

### Bước 4 — Huấn luyện lại model

```bash
python -m ml.retrain_customer_model
```

Script sẽ thực hiện:
1. Kết nối DuckDB (hoặc Supabase PostgreSQL nếu `USE_SUPABASE=true` trong `.env`)
2. Tải 28 đặc trưng từ `gold.hc_features_v1`
3. Loại bỏ hàng thiếu `is_default`, `monthly_income`, `loan_amount`, `credit_score`
4. Mã hóa `employment_status` + `occupation_type` bằng OrdinalEncoder (danh mục tường minh)
5. Huấn luyện LightGBM với n_estimators=500, num_leaves=63, subsample=0.8, colsample_bytree=0.8, is_unbalance=True
6. Lưu artifact vào `backend/customer_risk_model.pkl` (MODEL_VERSION="customer_lgbm_v3")
7. In các chỉ số đánh giá (AUC-ROC, precision, recall, F1)

### Bước 5 — Khởi động lại Backend

```bash
cd backend
source ../venv/bin/activate
python -m uvicorn main:app --reload
```

Kiểm tra model đã tải:

```bash
curl http://localhost:8000/docs
# Kiểm tra endpoint POST /applications/evaluate
```

### Bước 6 — Huấn luyện lại Scorecard (tùy chọn)

Model scorecard LR độc lập và dùng đặc trưng khác. Chỉ cần retrain khi có yêu cầu:

```bash
python ml/train_scorecard.py
```

---

## 6. Thuật toán Gợi ý Khoản Vay

Backend sử dụng tìm kiếm nhị phân để tìm khoản vay tối đa an toàn cho mỗi trong 3 kỳ hạn chuẩn (12, 36, 60 tháng):

```
Với mỗi kỳ hạn trong [12, 36, 60]:
    lo = 500, hi = 150_000
    Lặp 20 lần:
        mid = (lo + hi) / 2
        prob = model.predict(payload với amount=mid, term=kỳ_hạn)
        nếu prob < LOW_THRESHOLD (0.2):
            lo = mid   # có thể vay thêm
        ngược lại:
            hi = mid   # quá rủi ro
    max_safe[kỳ_hạn] = round(lo / 100) * 100
```

Gợi ý chọn tổ hợp (số tiền, kỳ hạn) có max_safe cao nhất.

**Định nghĩa "perfect fit":**
- `default_prob < 0.2` VÀ
- `kỳ hạn người dùng chọn == kỳ hạn gợi ý` VÀ
- `số tiền người dùng chọn >= 90% max_safe_amount`

Khi thỏa "perfect fit" → đơn được xác nhận tự động, không hiện modal xác nhận trước.

---

## 7. Tải lên Tài liệu

Tài liệu được lưu vào **Supabase Storage** nếu các biến môi trường sau được cấu hình:

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>   # KHÔNG dùng anon key
```

Nếu không cấu hình, file sẽ được lưu local tại `uploads/{app_id}/{uuid}_{filename}`.

**Định dạng cho phép:** PDF, DOC, DOCX, JPG, JPEG, PNG  
**Kích thước tối đa:** 10 MB mỗi file

Tên bucket là `loan-documents` — cần tạo thủ công trong Supabase Storage trước khi dùng lần đầu:

```sql
-- Trong Supabase SQL editor:
INSERT INTO storage.buckets (id, name, public)
VALUES ('loan-documents', 'loan-documents', false);
```

---

## 8. Các Phương án Cooldown cho Đơn Bị AUTO_REJECTED

Khi đơn vay bị model ML tự động từ chối (AUTO_REJECTED), cần có chính sách quy định thời gian chờ trước khi người dùng được nộp lại. Dưới đây là 4 phương án kèm ưu nhược điểm:

### Phương án A — Cooldown cố định (Đơn giản nhất)

**Cách hoạt động:** Sau khi bị AUTO_REJECTED, người dùng không thể nộp đơn mới trong N ngày (ví dụ: 30 ngày).

**Triển khai:**
- Thêm trường `last_rejected_at` (timestamp) vào bảng `users`
- Kiểm tra tại `POST /applications/evaluate`: nếu `now() - last_rejected_at < 30 ngày`, trả về lỗi 429

**Ưu điểm:** Đơn giản, dễ dự đoán, dễ giải thích cho người dùng  
**Nhược điểm:** Cứng nhắc — người dùng có tình hình tài chính thực sự cải thiện vẫn phải chờ

---

### Phương án B — Cooldown thích ứng theo mức rủi ro

**Cách hoạt động:** Thời gian chờ tỷ lệ thuận với mức độ rủi ro của đơn bị từ chối:
- `prob > 0.8` → 90 ngày
- `0.6 < prob ≤ 0.8` → 60 ngày
- `0.4 < prob ≤ 0.6` → 30 ngày

**Triển khai:**
- Lưu `default_probability` vào hàng `LoanApplication` bị từ chối
- Khi có yêu cầu evaluate mới, kiểm tra hàng AUTO_REJECTED gần nhất

**Ưu điểm:** Cân đối hơn; người dùng rủi ro cao phải chờ lâu hơn  
**Nhược điểm:** Phức tạp hơn một chút; người dùng có thể không hiểu tại sao thời gian chờ dài hơn

---

### Phương án C — Không cooldown, nhưng theo dõi số lần nộp lại

**Cách hoạt động:** Cho phép nộp lại không giới hạn, nhưng ghi lại mỗi lần. Admin thấy cờ "từ chối nhiều lần" trên đơn đã bị từ chối từ 2 lần trở lên.

**Triển khai:**
- Không cần logic cooldown
- Thêm trường `rejection_count` dạng computed vào ApplicationSummary

**Ưu điểm:** Tối đa tự do cho người dùng; không có người dùng bị khóa ngoài ý muốn  
**Nhược điểm:** Người dùng có thể spam nộp đơn với hy vọng kết quả khác; gây áp lực lên model

---

### Phương án D — Mở khóa qua Chat với AI

**Cách hoạt động:** Sau khi bị AUTO_REJECTED, người dùng phải tương tác với chatbot AI ít nhất 1 lần trước khi được nộp lại. Chatbot tư vấn cách cải thiện hồ sơ.

**Triển khai:**
- Thêm flag `chat_required_before_resubmit` vào bảng `users`
- Xóa flag khi người dùng gửi ≥ 1 tin nhắn tới POST /chat sau khi bị từ chối
- Kiểm tra flag tại POST /applications/evaluate

**Ưu điểm:** Khuyến khích người dùng hiểu lý do bị từ chối; có thể cải thiện chất lượng đơn lần sau  
**Nhược điểm:** Phức tạp hơn; có thể gây khó chịu; cần frontend thực thi kiểm tra

---

**Khuyến nghị:** Bắt đầu với **Phương án A** (cooldown cố định 30 ngày). Đơn giản nhất để triển khai và giải thích. Chuyển sang **Phương án B** ở sprint sau khi đã có dữ liệu về số lần từ chối thực tế.

---

## 9. Biến môi trường

### Backend `.env` (bắt buộc)

```bash
# PostgreSQL (Supabase)
DB_HOST=xxx.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=<mật-khẩu>

# JWT
SECRET_KEY=<chuỗi-bí-mật-ngẫu-nhiên>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# RAG (OpenRouter + Pinecone)
OPENROUTER_API_KEY=<key>
RAG_LLM_MODEL=google/gemini-flash-1.5
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
PINECONE_API_KEY=<key>
PINECONE_INDEX_NAME=creditintel-kb
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Supabase Storage (tùy chọn — dùng cho tải lên tài liệu)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
```

### Frontend `.env`

```bash
VITE_API_URL=http://localhost:8000
```

---

## 10. Hạn chế đã biết

1. **Migration DB phải thực hiện thủ công** — `init_db.py` dùng `CREATE TABLE IF NOT EXISTS` và không tự thêm cột mới vào bảng đã tồn tại. Chạy các câu ALTER TABLE ở Bước 1 phần 5 một lần duy nhất.

2. **Bucket Supabase phải tạo thủ công** — backend không tự tạo bucket `loan-documents`. Xem hướng dẫn ở phần 7.

3. **Tìm kiếm nhị phân chạy ~63 lần gọi model** — 20 lần lặp × 3 kỳ hạn. Nhanh với LightGBM (~100ms tổng), nhưng nên thêm rate limiting nếu endpoint `/evaluate` có lượng truy cập cao.

4. **occupation_type OrdinalEncoder unknown_value=-1** — nếu người dùng gửi loại nghề nghiệp mới không có trong tập huấn luyện, nó được ánh xạ về -1. LightGBM xử lý qua NaN propagation. Cần theo dõi đầu vào bất thường.

5. **URL tài liệu trong trạng thái INFO_SUBMITTED** — sau khi tải lên, `personal_info.document_urls` lưu danh sách URL. Nếu dùng Supabase Storage, URL có thể công khai tùy policy. Cân nhắc thêm row-level security nếu tài liệu nhạy cảm.
