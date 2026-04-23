# CreditIntel — Frontend

Ứng dụng web React cho phép khách hàng đăng ký vay, theo dõi trạng thái hồ sơ và tư vấn với AI chatbot.

---

## Yêu cầu hệ thống

| Công cụ | Phiên bản tối thiểu |
|---------|-------------------|
| Node.js | 18.x trở lên      |
| npm     | 9.x trở lên       |

---

## Cài đặt

### 1. Cài đặt dependencies

```bash
cd frontend
npm install
```

### 2. Cấu hình môi trường

Tạo file `.env` trong thư mục `frontend/` (hoặc copy từ ví dụ bên dưới):

```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
```

| Biến             | Mặc định                | Mô tả                          |
|------------------|-------------------------|--------------------------------|
| `VITE_API_URL`   | `http://localhost:8000` | URL của FastAPI backend        |

> **Lưu ý:** Backend phải được khởi động trước khi chạy frontend. Xem hướng dẫn tại [`/backend`](../backend/).

---

## Khởi động

### Development (hot reload)

```bash
npm run dev
```

Ứng dụng chạy tại: **http://localhost:5173**

### Production build

```bash
npm run build       # Tạo bundle tối ưu trong dist/
npm run preview     # Xem trước bản production trên localhost
```

---

## Khởi động backend (cần thiết)

```bash
# Tại thư mục gốc của dự án
pip install -r backend/requirements.txt

# Tạo file backend/.env từ backend/.env.example
# Sau đó chạy:
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API docs tự động có tại: http://localhost:8000/docs

---

## Cấu trúc thư mục

```
frontend/
├── public/                    # Static assets (favicon, ...)
└── src/
    ├── main.jsx               # Entry point
    ├── App.jsx                # Router + route declarations
    ├── index.css              # Tailwind base + custom components
    │
    ├── services/              # Axios API calls
    │   ├── api.js             # Axios instance + JWT interceptor
    │   ├── auth.js            # register / login
    │   ├── applications.js    # loan application CRUD
    │   └── chat.js            # RAG chatbot
    │
    ├── store/
    │   └── authStore.js       # Zustand — token & user state
    │
    ├── utils/
    │   └── format.js          # Currency, date formatters; STATUS_META / RISK_META
    │
    ├── components/
    │   ├── ProtectedRoute.jsx
    │   ├── common/
    │   │   ├── Navbar/        # Responsive navbar (guest / logged-in)
    │   │   ├── Modal/         # Reusable modal dialog
    │   │   ├── Badge/         # StatusBadge, RiskBadge
    │   │   └── LoadingSpinner/
    │   └── customer/
    │       ├── ApplicationCard/      # Card tóm tắt đơn vay
    │       ├── ApplicationTimeline/  # Timeline 5 bước
    │       └── ChatMessage/          # Bubble tin nhắn chat
    │
    └── pages/
        └── customer/
            ├── Landing/        # Trang chủ (public)
            ├── Register/       # Đăng ký tài khoản
            ├── Login/          # Đăng nhập
            ├── Dashboard/      # Tổng quan đơn vay
            ├── Apply/          # Form nộp đơn vay
            ├── ApplicationDetail/  # Chi tiết & trạng thái đơn
            ├── SubmitInfo/     # Nộp thông tin cá nhân
            └── Chat/           # RAG AI Chatbot
```

---

## Routes

| Path                   | Quyền truy cập | Trang                            |
|------------------------|----------------|----------------------------------|
| `/`                    | Public         | Landing page                     |
| `/register`            | Public         | Đăng ký tài khoản                |
| `/login`               | Public         | Đăng nhập                        |
| `/dashboard`           | Đã đăng nhập   | Dashboard tổng quan              |
| `/apply`               | Đã đăng nhập   | Nộp đơn vay mới                  |
| `/application/:id`     | Đã đăng nhập   | Chi tiết đơn vay (xem mọi status)|
| `/submit-info/:id`     | Đã đăng nhập   | Nộp thông tin cá nhân            |
| `/chat`                | Đã đăng nhập   | Chatbot tư vấn AI                |

---

## Công nghệ sử dụng

| Thư viện          | Mục đích                        |
|-------------------|---------------------------------|
| React 18          | UI framework                    |
| Vite 5            | Build tool / dev server         |
| React Router v6   | Client-side routing             |
| TailwindCSS 3     | Utility-first CSS               |
| Axios             | HTTP client                     |
| react-hook-form   | Form state & validation         |
| Zustand           | Global auth state               |
| react-toastify    | Toast notifications             |

---

## Design system

- **Nền chủ đạo:** Trắng (`#ffffff`) + xám nhạt (`#F9FAFB`) cho sections
- **Accent:** Xanh dương (`primary-600 = #2563EB`)
- **Màu trạng thái đơn vay:**

| Status           | Màu       |
|-----------------|-----------|
| AUTO_REJECTED   | Đỏ        |
| ADMIN_REJECTED  | Đỏ        |
| PENDING_REVIEW  | Vàng      |
| AWAITING_INFO   | Xanh lá   |
| INFO_SUBMITTED  | Xanh dương|

- **Màu rủi ro:** LOW = xanh lá · MEDIUM = vàng · HIGH = đỏ
