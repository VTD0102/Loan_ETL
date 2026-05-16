# Hướng Dẫn Sử Dụng & Quản Trị Module Admin (CreditIntel)

Tài liệu này cung cấp hướng dẫn chi tiết về cách vận hành, kiểm thử và cấu trúc chức năng của hệ thống quản trị (Admin Portal) thuộc dự án CreditIntel.

---

## 1. Khởi Chạy Hệ Thống (Chế độ Mock)

Hiện tại, Frontend được tích hợp cơ chế **Mock Persistence Engine** mạnh mẽ. Hệ thống giả lập Backend API nhưng vẫn đảm bảo tính nhất quán của dữ liệu thông qua trình duyệt.

### Các bước khởi động:
1.  Mở terminal tại thư mục gốc của dự án.
2.  Di chuyển vào thư mục `frontend`:
    ```bash
    cd frontend
    ```
3.  Cài đặt dependencies (chỉ thực hiện lần đầu):
    ```bash
    npm install
    ```
4.  Chạy ứng dụng ở chế độ Mock:
    ```bash
    npm run mock
    ```
5.  Truy cập giao diện Admin:
    **[http://localhost:5173/admin/login](http://localhost:5173/admin/login)**

---

## 2. Cơ Chế Lưu Trữ & Đồng Bộ Dữ Liệu

Khác với các hệ thống mock thông thường, CreditIntel sử dụng **LocalStorage** để lưu trữ trạng thái đơn vay:

*   **Tính nhất quán:** Mọi thao tác (Duyệt đơn, Từ chối, Nộp hồ sơ mới) sẽ được lưu lại. Dữ liệu **KHÔNG** bị mất khi bạn nhấn F5 (Refresh) trình duyệt.
*   **Đồng bộ Role:** Dữ liệu được dùng chung giữa vai trò **Admin** và **Customer**.
    *   *Ví dụ:* Nếu bạn đóng vai Customer nộp một đơn vay mới, sau đó đăng nhập Admin, bạn sẽ thấy đơn vay đó xuất hiện ngay lập tức trong danh sách chờ duyệt.
*   **Reset dữ liệu:** Để khôi phục dữ liệu về trạng thái ban đầu, bạn có thể xóa LocalStorage trong Developer Tools của trình duyệt hoặc xóa Cache trang web.

---

## 3. Tài Khoản Kiểm Thử (Test Accounts)

Hệ thống phân quyền dựa trên logic email trong chế độ Mock:

| Vai trò | Email hợp lệ | Mật khẩu |
| :--- | :--- | :--- |
| **Quản trị viên (Admin)** | Email có chứa chuỗi `admin` (Ví dụ: `admin@creditintel.dev`) | Bất kỳ |
| **Khách hàng (Customer)** | Email bất kỳ không chứa `admin` (Ví dụ: `user@test.com`) | Bất kỳ |

---

## 4. Các Chức Năng Chính Của Admin

Hệ thống Admin được thiết kế chuyên sâu để xử lý quy trình thẩm định tín dụng:

### 4.1. Dashboard Tổng Quan
*   **Chỉ số đo lường (KPIs):** Hiển thị số lượng đơn mới, đơn đang chờ, đơn đã duyệt/từ chối trong ngày.
*   **Biểu đồ phân bố rủi ro:** Trực quan hóa tỷ lệ hồ sơ LOW, MEDIUM, HIGH rủi ro dựa trên kết quả từ mô hình AI/ML.
*   **Xu hướng nộp đơn:** Biểu đồ đường hiển thị biến động lượng đơn vay theo thời gian.

### 4.2. Quản Lý Đơn Vay (Applications)
*   **Danh sách chờ duyệt (Pending):** Tập trung các hồ sơ cần xử lý gấp.
*   **Bộ lọc thông minh:** Hỗ trợ lọc theo Trạng thái, Mức độ rủi ro và Khoảng thời gian nộp đơn.
*   **Phân tích ML (ML Results):** Mỗi đơn vay đều hiển thị xác suất nợ xấu (Default Probability) và đề xuất hạn mức/kỳ hạn từ AI.

### 4.3. Quy Trình Xử Lý Hồ Sơ
1.  **Xem chi tiết:** Click vào hồ sơ để xem đầy đủ thông tin tài chính và kết quả chấm điểm tín dụng.
2.  **Phê duyệt (Approve):** Hệ thống chuyển trạng thái sang `AWAITING_INFO`, yêu cầu khách hàng nộp hồ sơ định danh (KYC).
3.  **Từ chối (Reject):** Admin bắt buộc phải nhập lý do từ chối. Lý do này sẽ được hiển thị trực tiếp cho khách hàng.
4.  **Xem thông tin cá nhân (PersonalInfo):** Chỉ khả dụng với các đơn đã qua bước duyệt sơ bộ và khách hàng đã nộp thông tin CCCD/Địa chỉ.

---

## 5. Kịch Bản Kiểm Thử Đề Xuất (Testing Flow)

Để thấy rõ sức mạnh của hệ thống, hãy thử kịch bản sau:

1.  **BƯỚC 1:** Đăng nhập Customer (`user@test.com`), nộp một đơn vay mới với số tiền $20,000.
2.  **BƯỚC 2:** Đăng xuất và đăng nhập Admin (`admin@creditintel.dev`).
3.  **BƯỚC 3:** Vào mục **Pending Review**, bạn sẽ thấy đơn vay $20,000 vừa nộp.
4.  **BƯỚC 4:** Nhấn **Approve**.
5.  **BƯỚC 5:** Đăng nhập lại Customer, bạn sẽ thấy trạng thái đơn vay chuyển thành "Cần nộp thông tin". Hãy nộp thông tin cá nhân.
6.  **BƯỚC 6:** Quay lại Admin, mở chi tiết đơn vay đó và nhấn nút **"Xem thông tin cá nhân"** để kiểm tra tính bảo mật và đầy đủ của dữ liệu.

---

## 6. Cấu Trúc Thư Mục Admin (Dành cho Developer)

```text
frontend/src/
├── components/admin/        # Các UI component chuyên biệt của Admin
│   ├── AdminLayout/         # Sidebar, Header, Breadcrumbs
│   ├── ApplicationsTable/   # Bảng dữ liệu tích hợp Pagination
│   ├── ApproveRejectButtons/# Logic xử lý phê duyệt/từ chối
│   ├── FilterBar/           # Thanh công cụ lọc đa năng
│   └── MLResultsDisplay/    # Trực quan hóa Gauge rủi ro & Đề xuất AI
│
├── pages/admin/             # Các trang nghiệp vụ (Pages)
│   ├── Dashboard/           # Thống kê & Charts
│   ├── ApplicationList/     # Toàn bộ danh sách đơn
│   ├── PendingList/         # Danh sách đơn chờ xử lý
│   └── ApplicationDetail/   # Chi tiết hồ sơ & Action Panel
│
├── services/admin.js        # API service layer (Admin endpoints)
└── mocks/                   # Persistence Layer
    ├── mockData.js          # Khởi tạo dữ liệu ban đầu
    └── mockHandlers.js      # Xử lý Logic Mock & Save LocalStorage
```

---
*Tài liệu này được cập nhật theo phiên bản Mock Persistence v2.0.*
