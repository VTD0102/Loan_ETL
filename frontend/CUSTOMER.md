# Chức năng Customer — Luồng hoạt động chi tiết

Tài liệu này mô tả toàn bộ các tính năng dành cho **Khách hàng (Customer)** trong hệ thống CreditIntel, bao gồm luồng chạy từng bước, trạng thái đơn vay và các hành động khả dụng.

---

## Tổng quan luồng chính

```
[Trang chủ]
     │
     ├──► Đăng ký tài khoản ──► Đăng nhập
     │                               │
     │                               ▼
     │                         [Dashboard]
     │                         │         │
     │                         │         └──► [Chat AI]
     │                         │
     │                         ▼
     │                   Nộp đơn vay
     │                         │
     │           ┌─────────────┴─────────────┐
     │           ▼                           ▼
     │    AI: Rủi ro CAO              AI: Rủi ro THẤP/TRUNG BÌNH
     │    AUTO_REJECTED               PENDING_REVIEW
     │           │                           │
     │           │                    Admin xét duyệt
     │           │                    │             │
     │           │               Từ chối        Phê duyệt
     │           │            ADMIN_REJECTED   AWAITING_INFO
     │           │                  │               │
     │           │                  │         Nộp thông tin
     │           │                  │         cá nhân
     │           │                  │               │
     │           │                  │         INFO_SUBMITTED
     │           │                  │               │
     └───────────┴──────────────────┴─── Nộp đơn mới
```

---

## 1. Trang chủ (Landing Page)

**Route:** `/`  
**Quyền truy cập:** Public (không cần đăng nhập)

### Nội dung
- **Hero section:** Tiêu đề, mô tả ngắn về dịch vụ, số liệu nổi bật (113K+ khoản vay, ROC-AUC 0.864, phân tích < 3s)
- **Quy trình 3 bước:** Nộp đơn → AI đánh giá → Kết quả nhanh
- **Ưu điểm:** Minh bạch, xử lý tức thì, AI-Powered, Chatbot 24/7
- **CTA:** Nút "Đăng ký ngay" và "Đăng nhập"

### Hành động
| Nút              | Chuyển đến |
|-----------------|-----------|
| Đăng ký ngay    | `/register` |
| Đăng nhập       | `/login`    |

---

## 2. Đăng ký tài khoản

**Route:** `/register`  
**Quyền truy cập:** Public

### Form fields
| Field              | Validation                              |
|--------------------|-----------------------------------------|
| Email              | Bắt buộc, định dạng email hợp lệ        |
| Tên đăng nhập      | Bắt buộc, tối thiểu 3 ký tự            |
| Mật khẩu           | Bắt buộc, tối thiểu 6 ký tự            |
| Xác nhận mật khẩu  | Phải trùng với mật khẩu                |

### Luồng xử lý
1. Người dùng điền form → nhấn "Đăng ký"
2. Client validate tại chỗ (react-hook-form)
3. Gọi `POST /auth/register` với `{ email, username, password }`
4. **Thành công:** Toast "Đăng ký thành công!" → redirect `/login`
5. **Thất bại:** Toast error (email đã tồn tại, v.v.)

---

## 3. Đăng nhập

**Route:** `/login`  
**Quyền truy cập:** Public

### Form fields
| Field    | Validation                   |
|----------|------------------------------|
| Email    | Bắt buộc, định dạng email    |
| Mật khẩu | Bắt buộc                    |

### Luồng xử lý
1. Người dùng nhập email + mật khẩu → nhấn "Đăng nhập"
2. Gọi `POST /auth/login`
3. **Thành công:**
   - JWT token lưu vào `localStorage` (key: `token`)
   - Thông tin user lưu vào `localStorage` (key: `user`) và Zustand store
   - Toast chào mừng
   - Redirect đến trang trước đó (nếu bị chặn bởi ProtectedRoute) hoặc `/dashboard`
4. **Thất bại:** Toast "Sai email hoặc mật khẩu"

> **Tự động đăng xuất:** Nếu token hết hạn (backend trả về 401), axios interceptor tự clear localStorage và redirect về `/login`.

---

## 4. Dashboard

**Route:** `/dashboard`  
**Quyền truy cập:** Đã đăng nhập (ProtectedRoute)

### Luồng xử lý khi mount
1. Gọi `GET /applications/me` để lấy đơn vay đang active
2. Render theo 2 trạng thái:

#### Trạng thái A — Chưa có đơn hoặc đơn đã bị từ chối
- Hiển thị màn hình "Chưa có đơn vay nào"
- Nút **"Nộp đơn vay mới"** → `/apply`
- Nếu có đơn bị từ chối: hiển thị card lịch sử bên dưới

#### Trạng thái B — Đang có đơn active
- Hiển thị `ApplicationCard` với: số tiền, kỳ hạn, trạng thái, ngày nộp, mức rủi ro
- Nút **"Xem chi tiết"** → `/application/:id`

### Quick Actions (luôn hiển thị)
| Card          | Hành động        |
|--------------|-----------------|
| 💬 Tư vấn AI  | → `/chat`        |
| 📋 Nộp đơn   | → `/apply`       |
| 📊 Lịch sử   | (xem dashboard)  |

---

## 5. Nộp đơn vay

**Route:** `/apply`  
**Quyền truy cập:** Đã đăng nhập

### Form fields
| Field                      | Kiểu     | Validation                        |
|----------------------------|----------|-----------------------------------|
| Thu nhập hàng tháng (USD)  | Number   | > 0, bắt buộc                    |
| Số tiền muốn vay (USD)     | Number   | > 0, ≤ 40,000, bắt buộc          |
| Kỳ hạn vay                 | Dropdown | 12 / 36 / 60 tháng               |
| Tỷ lệ nợ/Thu nhập (DTI %)  | Number   | 0–100, có tooltip giải thích      |
| Tình trạng việc làm        | Dropdown | Employed, Self-employed, v.v.     |
| Điểm tín dụng              | Number   | 300–850                           |
| Mục đích vay               | Dropdown | Debt Consolidation, Business, v.v.|
| Có nhà riêng               | Dropdown | Có / Không                        |

### Luồng xử lý sau submit
1. Gọi `POST /applications` với toàn bộ dữ liệu form
2. Backend chạy ML model → trả về `ApplicationOut` với `status`

**Kết quả 1 — `AUTO_REJECTED` (xác suất vỡ nợ > 40%):**
- Modal đỏ hiển thị: xác suất vỡ nợ, lý do từ chối (rủi ro CAO)
- Nút "Về Dashboard" → `/dashboard`

**Kết quả 2 — `PENDING_REVIEW` (rủi ro thấp/trung bình):**
- Modal xanh: "Đơn đã nộp thành công, đang chờ xét duyệt"
- Nút "Về Dashboard" hoặc "Xem chi tiết" → `/application/:id`

---

## 6. Chi tiết đơn vay

**Route:** `/application/:id`  
**Quyền truy cập:** Đã đăng nhập

Trang này hiển thị **toàn bộ thông tin** của một đơn vay và thay đổi giao diện theo `status`.

### Các trạng thái và giao diện tương ứng

#### `AUTO_REJECTED` — Tự động từ chối
- Badge: 🔴 "Tự động từ chối"
- Banner đỏ: xác suất vỡ nợ cụ thể, lý do (rủi ro CAO)
- Kết quả AI: risk level = HIGH, điểm rủi ro
- **Hành động:** Nút "Nộp đơn mới" → `/apply`

#### `PENDING_REVIEW` — Đang chờ xét duyệt
- Badge: 🟡 "Chờ xét duyệt"
- Banner vàng: "Đang chờ admin xét duyệt, thường 1–2 ngày làm việc"
- Kết quả AI hiển thị: risk level (LOW/MEDIUM), điểm rủi ro, hạn mức/kỳ hạn đề xuất
- Timeline: bước "Admin xét duyệt" đang active (spinner)
- **Hành động:** Không có — chỉ chờ

#### `ADMIN_REJECTED` — Admin từ chối
- Badge: 🔴 "Đã từ chối"
- Banner đỏ: lý do từ chối của admin (`admin_note`) nếu có
- **Hành động:** Nút "Nộp đơn mới" → `/apply`

#### `AWAITING_INFO` — Admin đã duyệt, chờ thông tin cá nhân
- Badge: 🟢 "Chờ thông tin"
- Banner xanh lá: "Chúc mừng! Đơn đã được duyệt"
- Hiển thị: hạn mức đề xuất, kỳ hạn đề xuất
- **Hành động:** Nút "Nộp thông tin cá nhân" → `/submit-info/:id`

#### `INFO_SUBMITTED` — Đã nộp thông tin cá nhân
- Badge: 🔵 "Đã nộp thông tin"
- Banner xanh dương: "Thông tin đang được xử lý"
- Timeline đầy đủ (4/5 bước hoàn thành)
- **Hành động:** Không có — chờ liên hệ

### Thành phần luôn hiển thị
- **Kết quả AI:** risk level, xác suất vỡ nợ, hạn mức đề xuất, kỳ hạn đề xuất (nếu có)
- **Thông tin đơn:** 8 trường thông tin đã nộp (thu nhập, số tiền, DTI, điểm tín dụng, v.v.)
- **Timeline tiến trình:** 5 bước từ nộp đơn → hoàn tất

---

## 7. Nộp thông tin cá nhân

**Route:** `/submit-info/:id`  
**Quyền truy cập:** Đã đăng nhập, đơn phải có status `AWAITING_INFO`

### Guard tự động
Khi mount, trang kiểm tra `GET /applications/:id`:
- Nếu status **≠** `AWAITING_INFO` → redirect về `/application/:id` kèm toast thông báo
- Đảm bảo không ai truy cập URL trực tiếp sai thời điểm

### Form fields
| Field             | Validation                              |
|-------------------|-----------------------------------------|
| Họ và tên đầy đủ  | Bắt buộc                               |
| Số CCCD / CMND   | Bắt buộc, 9–12 chữ số                  |
| Số điện thoại     | Bắt buộc, định dạng phone hợp lệ       |
| Email             | Bắt buộc, định dạng email              |
| Ngày sinh         | Bắt buộc, date picker (không > hôm nay)|
| Địa chỉ thường trú| Bắt buộc, tối thiểu 10 ký tự          |

### Luồng xử lý
1. Gọi `POST /applications/:id/personal-info`
2. **Thành công:** Modal xanh "Đã nộp thông tin thành công" → redirect `/application/:id`
3. **Thất bại:** Toast error

---

## 8. Chatbot AI (RAG)

**Route:** `/chat`  
**Quyền truy cập:** Đã đăng nhập

### Giao diện
- Danh sách tin nhắn cuộn tự động xuống tin mới nhất
- Tin nhắn của người dùng: bên **phải**, bong bóng xanh
- Tin nhắn của AI: bên **trái**, bong bóng trắng viền xám
- Typing indicator (3 dấu chấm bounce) khi AI đang trả lời
- Input textarea + nút gửi

### Gợi ý câu hỏi ban đầu
Khi chưa có tin nhắn người dùng, hiển thị 4 nút gợi ý:
- "Tại sao tôi bị đánh giá rủi ro cao?"
- "Làm thế nào để tăng điểm tín dụng?"
- "Tôi nên vay bao nhiêu là hợp lý?"
- "DTI là gì và ảnh hưởng như thế nào?"

### Luồng xử lý
1. Người dùng nhập và nhấn Enter (hoặc Shift+Enter để xuống dòng)
2. Tin nhắn được thêm ngay vào list (optimistic UI)
3. Gọi `POST /chat` với `{ message: "..." }`
4. **Thành công:** Hiển thị phản hồi từ RAG model
5. **Thất bại:** Hiển thị tin nhắn lỗi thân thiện từ bot
6. Chat history giữ trong component state — reset khi rời trang

---

## 9. Navbar & Authentication State

### Khi chưa đăng nhập
```
[CI CreditIntel]          [Đăng nhập]  [Đăng ký]
```

### Khi đã đăng nhập
```
[CI CreditIntel]  [Dashboard]  [Tư vấn AI]   Xin chào, {username}  [Đăng xuất]
```

### Đăng xuất
1. Nhấn "Đăng xuất"
2. Xóa `token` và `user` khỏi `localStorage`
3. Reset Zustand store
4. Redirect về `/`

### Mobile (< 768px)
- Navbar thu gọn với nút hamburger ☰
- Menu dropdown hiện ra khi nhấn

---

## 10. Bảo vệ route (ProtectedRoute)

Các route yêu cầu đăng nhập được bọc bởi `ProtectedRoute`:
- Kiểm tra `token` trong Zustand store (đồng bộ từ `localStorage`)
- Nếu không có token → redirect `/login` và lưu `location.state.from` để sau đăng nhập redirect đúng trang

---

## Sơ đồ trạng thái đơn vay

```
                    ┌─────────────────────────────────┐
                    │         Nộp đơn (POST /applications)│
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │         ML Model chạy          │
                    └───────────────┬───────────────┘
                                    │
              ┌─────────────────────┴─────────────────────┐
              │ risk HIGH (>40%)                           │ risk LOW/MEDIUM
              ▼                                            ▼
       AUTO_REJECTED                               PENDING_REVIEW
       (từ chối tức thì)                          (chờ admin duyệt)
              │                                            │
              │                           ┌───────────────┴───────────────┐
              │                           │                               │
              │                    Admin TỪ CHỐI                  Admin PHÊ DUYỆT
              │                           │                               │
              │                    ADMIN_REJECTED                  AWAITING_INFO
              │                           │                               │
              │                           │                    Customer nộp thông tin
              │                           │                               │
              │                           │                        INFO_SUBMITTED
              │                           │                               │
              └───────────────────────────┴───────────────────────────────┘
                                          │
                               Có thể nộp đơn mới
```

---

## Màu sắc trạng thái

| Trạng thái       | Màu nền    | Màu chữ   | Ý nghĩa              |
|-----------------|-----------|-----------|----------------------|
| AUTO_REJECTED   | Đỏ nhạt   | Đỏ đậm    | Từ chối tự động      |
| ADMIN_REJECTED  | Đỏ nhạt   | Đỏ đậm    | Admin từ chối        |
| PENDING_REVIEW  | Vàng nhạt | Vàng đậm  | Đang chờ xét duyệt   |
| AWAITING_INFO   | Xanh lá nhạt | Xanh lá đậm | Admin đã duyệt     |
| INFO_SUBMITTED  | Xanh dương nhạt | Xanh dương đậm | Đã nộp thông tin |

| Rủi ro  | Màu      |
|--------|----------|
| LOW    | Xanh lá  |
| MEDIUM | Vàng     |
| HIGH   | Đỏ       |
