# APP DEVELOPMENT PLAN — CreditIntel Web Application

> Tài liệu này ghi lại toàn bộ hướng đi, quyết định thiết kế, luồng hệ thống và thông tin quan trọng được thảo luận trong phiên lên kế hoạch dự án.

---

## 1. Bối cảnh dự án hiện tại

### Hệ thống CreditIntel (đã có)

CreditIntel là hệ thống Data Engineering + Machine Learning phục vụ **quản lý rủi ro tín dụng và dự đoán vỡ nợ khoản vay**, xây dựng trên Prosper Loan Dataset (~113K khoản vay, 2005–2014).

**Kiến trúc Data Pipeline (4 lớp):**

| Lớp | Schema | Mục đích |
|-----|--------|----------|
| Bronze | `bronze.*` | Raw data — load CSV thô |
| Silver | `silver.prosper_loans_cleansed` | Làm sạch, chuẩn hóa |
| Core | `core.loans`, `core.borrowers`, `core.credit_profiles`, dim tables | Schema business normalized |
| Gold | `gold.loan_features_v1` + 5 views | Feature engineering cho ML & Dashboard |

**ML Model hiện tại:**
- **Risk model**: LightGBM trained by `machinelearning/ml/retrain_customer_model.py`
- **Risk artifact**: `machinelearning/ml/models/customer_risk_model.pkl`
- **Scorecard model**: Logistic Regression trained by `machinelearning/ml/train_scorecard.py`
- **Scorecard artifact**: `machinelearning/ml/models/scorecard_model.pkl`
- **Ngưỡng rủi ro**: Low < 0.2, Medium 0.2–0.4, High > 0.4
- **Output**: Risk level (Low/Medium/High), risk score, đề xuất hạn mức & kỳ hạn; scorecard trả FICO-style credit score.

**Tech stack hiện tại:**
- Database: PostgreSQL (Supabase)
- ETL: Python, Pandas, SQLAlchemy
- ML: scikit-learn
- UI hiện tại: Streamlit + Plotly

---

## 2. Mục tiêu phát triển ứng dụng mới

Xây dựng một **web application** cho phép:
- **Khách hàng** đăng nhập, nộp đơn vay, nhận kết quả xét duyệt và đề xuất khoản vay hợp lý
- **Admin** xem dashboard tổng quan, xét duyệt đơn vay, yêu cầu thông tin cá nhân từ khách hàng
- **RAG Chatbot** hỗ trợ khách hàng đã đăng nhập hiểu kết quả và tư vấn tài chính

---

## 3. Phương án kiến trúc đã chọn

**Phương án 2: React + FastAPI (Tách biệt hoàn toàn)**

```
React App (Frontend)
├── Customer routes  (/apply, /dashboard, /result,...)
└── Admin routes     (/admin/dashboard, /admin/applications,...)
           │
           │ HTTP / REST + JWT Auth
           ▼
FastAPI Backend
├── /auth/*           JWT Authentication
├── /applications/*   CRUD đơn vay
├── /admin/*          Admin APIs
├── /credit-score     Scorecard API
└── /chat             RAG Model
           │
           ▼
PostgreSQL (Supabase — tái sử dụng instance hiện có)
├── Schema mới: users, loan_applications, personal_info
└── Schema cũ:  core.*, gold.*, silver.*
```

**Lý do chọn phương án này:**
- Kiến trúc chuẩn, production-ready
- React hoàn toàn tự do về UX/UI cho customer-facing app
- FastAPI nhanh, có auto-docs (Swagger)
- Dễ tách biệt customer và admin
- RAG tích hợp sạch qua dedicated endpoint
- Bỏ toàn bộ Streamlit — rebuild dashboard bằng Recharts/Chart.js trong React

---

## 4. Vai trò người dùng

### Khách hàng (Customer)
- Tự đăng ký tài khoản bằng **email + username + password**
- Đăng nhập để nộp đơn vay
- Chỉ được có **1 đơn active** tại 1 thời điểm
- Nếu đơn bị từ chối (AUTO hoặc ADMIN) → được nộp đơn mới
- Theo dõi trạng thái đơn trong app
- Nộp thông tin cá nhân chi tiết khi được duyệt
- Sử dụng RAG chatbot khi đã đăng nhập

### Admin
- Đăng nhập riêng (tài khoản do hệ thống tạo sẵn)
- Xem dashboard tổng quan với biểu đồ phân tích
- Xem và xét duyệt các đơn `PENDING_REVIEW`
- Xem toàn bộ lịch sử đơn (filter theo status, ngày, risk)
- Approve / Reject từng đơn
- Xem thông tin cá nhân khách hàng đã nộp sau khi được duyệt

---

## 5. Luồng trạng thái đơn vay

### Customer Side

```
Đăng ký / Đăng nhập
        ↓
Điền form vay
(thu nhập, số tiền, kỳ hạn, nghề nghiệp, DTI, có nhà không,...)
        ↓
   ML Model chạy tự động
        ↓
┌───────────────────────────────┐
│  P(default) > 0.4?            │
│  YES → AUTO_REJECTED          │ → Khách thấy ngay, có thể nộp đơn mới
│  NO  → PENDING_REVIEW         │ → Chờ Admin xét duyệt
└───────────────────────────────┘
        ↓ (nếu PENDING_REVIEW)
Khách vào app check trạng thái
        ↓
┌───────────────────────────────┐
│  Admin quyết định             │
│  REJECT → ADMIN_REJECTED      │ → Khách thấy khi check, có thể nộp mới
│  APPROVE → AWAITING_INFO      │ → Khách thấy thông báo trong app
└───────────────────────────────┘
        ↓ (nếu AWAITING_INFO)
Khách nộp thông tin cá nhân
(Họ tên đầy đủ, CCCD, SĐT, email, ngày sinh, địa chỉ,...)
        ↓
   INFO_SUBMITTED
(Xử lý tiếp theo nằm ngoài hệ thống)
```

### Admin Side

```
Admin đăng nhập
        ↓
┌─────────────────────────────────────────────────────────┐
│                   Admin Dashboard                        │
│                                                          │
│  [Tổng quan — Cards]      [Biểu đồ phân tích]           │
│  • Tổng đơn hôm nay       • Phân bố Risk Level          │
│  • Đang chờ duyệt         • Xu hướng đơn theo thời gian │
│  • Đã duyệt               • Tỉ lệ Auto-reject vs Pending│
│  • Đã từ chối             • Phân bố thu nhập / kỳ hạn   │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
Xem danh sách       Xem danh sách
PENDING_REVIEW      toàn bộ lịch sử
(cần xét duyệt)     (filter theo status/ngày)
       ↓
Vào chi tiết 1 đơn
• Thông tin form khách điền
• Kết quả ML (probability, risk score, biểu đồ gauge)
• So sánh với đề xuất của model
       ↓
┌─────────────────────────┐
│  Admin quyết định        │
│  [APPROVE] → AWAITING_INFO│
│  [REJECT]  → ADMIN_REJECTED│
└─────────────────────────┘
       ↓ (sau khi khách nộp info)
Xem thông tin cá nhân khách
(CCCD, SĐT, họ tên,...)
→ Chuyển xử lý ra ngoài hệ thống
```

### 5 Trạng thái đơn vay

| Status | Ý nghĩa | Ai thấy |
|--------|---------|---------|
| `AUTO_REJECTED` | ML tự động từ chối (HIGH risk > 0.4) | Khách thấy ngay sau submit |
| `PENDING_REVIEW` | Đang chờ Admin xét duyệt | Khách thấy khi check status |
| `ADMIN_REJECTED` | Admin từ chối | Khách thấy khi check status |
| `AWAITING_INFO` | Được duyệt, chờ nộp CCCD/SĐT... | Khách thấy thông báo trong app |
| `INFO_SUBMITTED` | Đã nộp thông tin, xử lý ngoài | Khách thấy khi check status |

---

## 6. Danh sách màn hình

### Customer App

| Route | Màn hình | Mô tả |
|-------|----------|-------|
| `/` | Landing page | Giới thiệu dịch vụ, nút Login/Register |
| `/register` | Đăng ký | Email + username + password |
| `/login` | Đăng nhập | Email + password |
| `/dashboard` | Trang chủ | Nếu chưa có đơn → nút "Nộp đơn vay"; nếu có đơn → hiển thị trạng thái hiện tại |
| `/apply` | Form vay | Chỉ mở khi không có đơn active |
| `/application/:id` | Chi tiết đơn | Trạng thái đơn + timeline + kết quả |
| `/submit-info/:id` | Nộp thông tin cá nhân | Chỉ mở khi status = `AWAITING_INFO` |
| `/chat` | RAG Chatbot | Chỉ khi đã đăng nhập |

### Admin App

| Route | Màn hình | Mô tả |
|-------|----------|-------|
| `/admin/login` | Admin đăng nhập | |
| `/admin/dashboard` | Dashboard tổng quan | Cards + biểu đồ phân tích |
| `/admin/pending` | Danh sách chờ duyệt | Các đơn `PENDING_REVIEW` |
| `/admin/applications` | Toàn bộ lịch sử | Filter theo status/ngày/risk level |
| `/admin/application/:id` | Chi tiết đơn | Thông tin ML + nút Approve/Reject |
| `/admin/personal-info/:id` | Thông tin cá nhân | Xem CCCD, SĐT, họ tên khách đã nộp |

---

## 7. Database — Bảng mới cần thêm

```sql
-- Tài khoản người dùng
users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR UNIQUE NOT NULL,
    username      VARCHAR NOT NULL,
    password_hash VARCHAR NOT NULL,
    role          VARCHAR DEFAULT 'customer',  -- 'customer' | 'admin'
    created_at    TIMESTAMP DEFAULT NOW()
)

-- Đơn vay
loan_applications (
    id                   SERIAL PRIMARY KEY,
    user_id              INT REFERENCES users(id),
    status               VARCHAR NOT NULL,
    -- Input từ form customer
    monthly_income       NUMERIC,
    loan_amount          NUMERIC,
    term                 INT,
    employment_status    VARCHAR,
    dti                  NUMERIC,
    is_homeowner         BOOLEAN,
    listing_category     VARCHAR,
    credit_score         NUMERIC,
    -- Output từ ML
    default_probability  NUMERIC,
    risk_level           VARCHAR,
    risk_score           NUMERIC,
    recommended_amount   NUMERIC,
    recommended_term     INT,
    -- Metadata
    submitted_at         TIMESTAMP DEFAULT NOW(),
    reviewed_at          TIMESTAMP,
    reviewed_by          INT REFERENCES users(id),
    admin_note           TEXT
)

-- Thông tin cá nhân (chỉ thu thập sau khi được duyệt)
personal_info (
    id                SERIAL PRIMARY KEY,
    application_id    INT REFERENCES loan_applications(id),
    user_id           INT REFERENCES users(id),
    full_name         VARCHAR,
    id_card_number    VARCHAR,
    phone             VARCHAR,
    email             VARCHAR,
    date_of_birth     DATE,
    address           TEXT,
    submitted_at      TIMESTAMP DEFAULT NOW()
)
```

---

## 8. Ứng dụng RAG Chatbot

**Vị trí**: Chỉ phục vụ khách hàng đã đăng nhập (route `/chat`)

**Mục đích chính**: Giải thích kết quả dự đoán và tư vấn tài chính

**Luồng hoạt động:**
```
Khách hàng xem kết quả → đặt câu hỏi tự nhiên
        ↓
"Tại sao tôi bị đánh giá rủi ro CAO?"
"Tôi cần làm gì để tăng khả năng được duyệt?"
"Mức thu nhập X thì nên vay bao nhiêu là hợp lý?"
        ↓
RAG tìm trong knowledge base → trả lời cá nhân hóa
```

**Knowledge base của RAG:**

| Nguồn | Nội dung |
|-------|----------|
| File chính sách tự viết | Tiêu chí phê duyệt, mức rủi ro |
| Tài liệu ML hiện có (`docs/ml/`) | Giải thích các chỉ số tài chính, feature và kết quả model |
| FAQ tự tổng hợp | Câu hỏi thường gặp về khoản vay |
| Kết quả prediction của chính khách hàng | Giải thích cá nhân hóa theo profile |

---

## 9. Vấn đề cần xử lý trước khi code — Retrain ML Model

**Vấn đề**: Model hiện tại được train trên 34 features của `gold.loan_features_v1`, nhiều features là dữ liệu nội bộ Prosper mà khách hàng mới không có (ví dụ: `prosper_score`, `prosper_rating_alpha`, `borrower_apr`).

**Giải pháp**: Retrain model mới chỉ với features khách hàng có thể cung cấp qua form:

| Feature | Nguồn |
|---------|-------|
| `stated_monthly_income` | Khách điền |
| `loan_original_amount` | Khách điền |
| `term` | Khách chọn (12/24/36/48/60) |
| `employment_status` | Khách chọn |
| `debt_to_income_ratio` | Khách điền hoặc tính toán |
| `is_homeowner` | Khách chọn |
| `listing_category` | Khách chọn (mục đích vay) |
| `credit_score` | Khách tự khai báo |

**Ưu tiên**: Retrain model là bước đầu tiên trước khi build app vì đây là nền tảng của toàn bộ hệ thống.

---

## 10. Kế hoạch 2 tuần

### Tuần 1 — Backend + Core Customer Flow

- [ ] Setup FastAPI project, cấu trúc thư mục
- [ ] Setup JWT Authentication (register, login)
- [ ] Tạo bảng mới trong PostgreSQL (users, loan_applications, personal_info)
- [ ] Retrain ML model với features từ customer form
- [ ] API: submit application → chạy ML → auto-reject hoặc pending
- [ ] API: customer xem trạng thái đơn
- [ ] API: customer nộp thông tin cá nhân
- [ ] React: Landing, Register, Login, Dashboard, Apply Form, Status Page

### Tuần 2 — Admin + RAG + Hoàn thiện

- [ ] API: admin get pending applications, approve/reject
- [ ] API: admin get all applications (với filter)
- [ ] API: admin xem personal info
- [ ] React Admin: Dashboard (cards + charts), Pending list, Application detail, Personal info view
- [ ] Tích hợp RAG chatbot vào React + FastAPI endpoint `/chat`
- [ ] React Customer: Personal info form, chi tiết đơn với timeline
- [ ] Test toàn bộ luồng end-to-end
- [ ] UI polish

---

## 11. Tính năng KHÔNG thêm (tránh phức tạp)

| Tính năng | Lý do bỏ |
|-----------|----------|
| Email/SMS notification | Cần external service, tốn thời gian setup |
| Export PDF báo cáo | Nice-to-have nhưng không cần thiết trong 2 tuần |
| Multi-role admin (super admin, reviewer,...) | 1 role admin là đủ |
| Real-time update (WebSocket) | Overkill cho quy mô này |
| Xác thực OTP cho khách hàng | Phức tạp không cần thiết |
| RAG cho Admin | Admin dùng SQL + charts đủ tin cậy hơn |

---

> Tài liệu được tạo ngày 2026-04-09, ghi lại kết quả phiên thảo luận lên kế hoạch dự án.
