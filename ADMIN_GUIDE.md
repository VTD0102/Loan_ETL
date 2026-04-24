# Hướng Dẫn Sử Dụng & Chạy Module Admin (CreditIntel)

Tài liệu này cung cấp hướng dẫn chi tiết về cách chạy, kiểm thử và hiểu các chức năng của module Admin trong dự án CreditIntel.

---

## 1. Hướng dẫn chạy dự án (Chế độ Mock)

Hiện tại, frontend đang được thiết lập để chạy độc lập với Backend thông qua chế độ **Mock Mode**. Dữ liệu được giả lập (mock data) và lưu trực tiếp trong bộ nhớ (RAM) của trình duyệt.

### Các bước khởi chạy:
1. Mở terminal và di chuyển vào thư mục `frontend`:
   ```bash
   cd frontend
   ```
2. Cài đặt các gói phụ thuộc (nếu chưa cài):
   ```bash
   npm install
   ```
3. Chạy lệnh khởi động mock server:
   ```bash
   npm run mock
   ```
4. Truy cập giao diện Admin qua trình duyệt:
   **[http://localhost:5173/admin/login](http://localhost:5173/admin/login)**

---

## 2. Tài khoản kiểm thử (Test Accounts)

Trong chế độ Mock, hệ thống không xác thực mật khẩu nhưng kiểm tra dựa trên **địa chỉ email** để phân quyền.

### Đăng nhập Admin
*   **Email:** `admin@creditintel.dev` *(hoặc bất kỳ email nào có chứa chữ "admin")*
*   **Mật khẩu:** Bất kỳ (ví dụ: `password123`)

### Đăng nhập Khách hàng (Customer) - để đối chiếu
*   **Email:** Bất kỳ email nào **KHÔNG** chứa chữ "admin" (ví dụ: `user@example.com`)
*   **Mật khẩu:** Bất kỳ

---

## 3. Các tính năng chính của Admin

Module Admin được thiết kế để quản lý các đơn vay tín dụng với các tính năng sau:

| Tính năng | Đường dẫn (Route) | Mô tả |
| :--- | :--- | :--- |
| **Đăng nhập** | `/admin/login` | Cổng xác thực dành riêng cho Admin. |
| **Dashboard** | `/admin/dashboard` | Thống kê tổng quan số lượng đơn trong ngày, biểu đồ phân bố rủi ro (Pie chart) và xu hướng nộp đơn (Line chart). |
| **Đơn chờ duyệt** | `/admin/pending` | Danh sách các đơn vay đang ở trạng thái `PENDING_REVIEW` cần Admin xử lý. |
| **Tất cả đơn vay** | `/admin/applications` | Hiển thị toàn bộ đơn vay. Hỗ trợ lọc theo: Trạng thái, Mức rủi ro và Khoảng thời gian nộp. |
| **Chi tiết đơn vay** | `/admin/application/:id` | Hiển thị toàn bộ hồ sơ vay của khách hàng, kết quả đánh giá rủi ro từ hệ thống Machine Learning và lịch sử tiến trình. |
| **Xử lý đơn (Approve/Reject)**| N/A (Trong trang Chi tiết) | Admin có quyền **Duyệt (Approve)** hoặc **Từ chối (Reject)** đơn vay (cần nhập lý do từ chối). |
| **Xem thông tin cá nhân** | `/admin/personal-info/:id` | Xem các thông tin nhạy cảm của khách hàng (CCCD, SĐT, Địa chỉ) sau khi họ đã nộp thông tin. |

---

## 4. Dữ liệu giả lập (Mock Data) để Test

Dữ liệu của Admin được định nghĩa độc lập tại `frontend/src/mocks/mockData.js` (`MOCK_ADMIN_APPS`).

Để test đầy đủ các luồng, bạn có thể sử dụng các ID đơn vay sau:

*   **Test chức năng Duyệt/Từ chối:** Click vào các đơn có trạng thái **Chờ xét duyệt** (ID: `10`, `11`, `12`, `20`, `21`). Nút hành động sẽ xuất hiện ở cuối trang chi tiết.
*   **Test xem Thông tin cá nhân:** Click vào đơn có trạng thái **Đã nộp thông tin** (ID: `18`).
*   **Test hiển thị Empty State (Không có thông tin):** Thử truy cập `/admin/personal-info/10` (Đơn chưa nộp thông tin cá nhân).

---

## 5. Lưu ý quan trọng về Chế độ Mock

Vì hệ thống đang chạy hoàn toàn bằng dữ liệu giả lập trên RAM:

1.  **Mất dữ liệu khi Refresh (F5):** Bất kỳ thay đổi nào (duyệt đơn, từ chối đơn) sẽ bị mất và khôi phục về trạng thái ban đầu nếu bạn tải lại trang (refresh browser).
2.  **Sự tách biệt dữ liệu Admin/Customer:** Hiện tại dữ liệu hiển thị cho Admin (`MOCK_ADMIN_APPS`) và dữ liệu hiển thị cho Customer (`MOCK_APPS`) là **hai danh sách riêng biệt** để tiện cho việc có nhiều dữ liệu test. Do đó, việc Admin duyệt đơn sẽ không tự động cập nhật sang phía giao diện của Customer.
3.  **Bước tiếp theo:** Để dữ liệu đồng bộ theo thời gian thực và lưu trữ vĩnh viễn, dự án cần được kết nối với Backend API và Database thật.

---

## 6. Cấu trúc thư mục (Dành cho Developer)

Nếu cần tùy chỉnh code, đây là nơi chứa các thành phần của Admin:

```text
frontend/src/
├── components/admin/        # Các UI component tái sử dụng của Admin
│   ├── AdminLayout/         # Khung giao diện (Sidebar, Header)
│   ├── ApplicationsTable/   # Bảng danh sách đơn vay
│   ├── ApproveRejectButtons/# Nút Duyệt/Từ chối
│   ├── FilterBar/           # Thanh công cụ lọc
│   ├── MLResultsDisplay/    # Trực quan hóa kết quả Machine Learning
│   └── SummaryCard/         # Card thống kê Dashboard
│
├── pages/admin/             # Các trang (Pages) của Admin
│   ├── ApplicationDetail/
│   ├── ApplicationList/
│   ├── Dashboard/
│   ├── Login/
│   ├── PendingList/
│   └── PersonalInfoView/
│
├── services/admin.js        # File định nghĩa các endpoint API gọi từ Admin
└── mocks/                   # Dữ liệu giả lập và Handlers bắt request
    ├── mockData.js
    └── mockHandlers.js
```
