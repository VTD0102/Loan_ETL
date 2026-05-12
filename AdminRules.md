Bạn là một Senior React Developer. Dựa trên cấu trúc thư mục hiện tại của project (có phân chia src/pages/admin, src/pages/customer, src/components/admin, src/components/common, src/services...), hãy thực hiện code cho module ADMIN theo danh sách các yêu cầu cực kỳ chi tiết dưới đây.

⚠️ **YÊU CẦU BẮT BUỘC (CRITICAL RULES):**
1. Đọc và tuân thủ tuyệt đối các quy tắc code được định nghĩa trong file `RULES.md` ở trong thư mục frontend
2. Tham khảo và giữ nguyên coding style, state management, logic call API, và cách viết UI (TailwindCSS) của role Customer (đã code trong `src/pages/customer` và `src/components/customer`).
3. Các components dùng chung (như Button, Table, Modal) nếu có sẵn ở `src/components/common` thì phải tái sử dụng.
4. Logic call API phải được viết gọn gàng và đưa vào thư mục `src/services` (ví dụ tạo thêm `src/services/adminService.js`).
5. Sử dụng React Router v6 cho routing. Cập nhật file `App.jsx` (hoặc file config route hiện tại) để khai báo các route của admin.
6. Mọi UI cần tuân thủ Responsive, có Loading State, Error State và Empty State.

---
### 🛠 CHI TIẾT CÁC TASK CẦN THỰC HIỆN:

#### TASK 1: Setup Route & Layout (Path: `src/components/admin/` & `src/App.jsx`)
- Sử dụng file `src/components/ProtectedRoute.jsx` hiện có hoặc tạo `src/components/admin/AdminProtectedRoute.jsx` để check logic: `role === 'admin'`. Nếu không phải admin, redirect về login.
- Tạo `src/components/admin/AdminLayout.jsx`:
  - Có Sidebar menu: Dashboard, Pending Review, All Applications, Logout.
  - Có Header: Logo, Admin username.
  - Có `<Outlet />` cho nested routes.
- Setup route trong `App.jsx`:
  - `/admin/login` → AdminLoginPage
  - (Các route dưới bọc trong AdminProtectedRoute và AdminLayout)
  - `/admin/dashboard` → AdminDashboardPage
  - `/admin/pending` → PendingApplicationsPage
  - `/admin/applications` → AllApplicationsPage
  - `/admin/application/:id` → AdminApplicationDetailPage
  - `/admin/personal-info/:id` → PersonalInfoViewPage

#### TASK 2: Login Admin (Path: `src/pages/admin/AdminLoginPage.jsx`)
- Form simple: email, password.
- Call API `POST /auth/login`.
- Logic: Kiểm tra response: nếu `role !== 'admin'` → show error "Không có quyền admin".
- Success → save token (cùng cách với customer), redirect to `/admin/dashboard`.

#### TASK 3: Dashboard & Charts (Path: `src/pages/admin/AdminDashboardPage.jsx`)
- Layout: 2 cột (Cards trên, Charts dưới).
- Khi mount, call API `GET /admin/dashboard/summary`.
- Hiển thị 5 cards dạng grid (Sử dụng tái cấu trúc tạo `src/components/admin/SummaryCard.jsx`):
  1. Tổng đơn hôm nay (icon)
  2. Đang chờ duyệt (badge vàng)
  3. Đã duyệt hôm nay (badge xanh)
  4. Đã từ chối hôm nay (badge đỏ)
  5. Tự động từ chối (badge cam)
  - *Click vào card sẽ navigate sang trang list tương ứng kèm filter.*
- **Charts (sử dụng recharts hoặc chart.js):**
  - Chart 1 (Pie/Donut): Phân bố Risk Level (LOW - xanh, MEDIUM - vàng, HIGH - đỏ). Call `GET /admin/dashboard/risk-distribution`.
  - Chart 2 (Line): Trend đơn vay theo thời gian (Query từ list, group by date. X: ngày, Y: số đơn).

#### TASK 4: Pending Applications (Path: `src/pages/admin/PendingApplicationsPage.jsx`)
- Call API `GET /admin/applications/pending?page=1&limit=20`.
- Tạo `src/components/admin/ApplicationsTable.jsx` hiển thị: ID, User ID/Email, Số tiền vay, Kỳ hạn, Thu nhập, Risk Level (badge màu), Risk Score (progress bar/gauge), Ngày nộp.
- Action column: Nút "Xem chi tiết" → navigate `/admin/application/{id}`.
- Có Pagination (prev/next). Sort `submitted_at ASC`. Hiển thị Empty state nếu không có data.

#### TASK 5: All Applications (Path: `src/pages/admin/AllApplicationsPage.jsx`)
- Tái sử dụng `ApplicationsTable.jsx` nhưng thêm cột Status.
- Tạo `src/components/admin/FilterBar.jsx` trên đầu bảng:
  - Dropdown "Status" (All, AUTO_REJECTED, PENDING_REVIEW, ADMIN_REJECTED, AWAITING_INFO, INFO_SUBMITTED)
  - Dropdown "Risk Level" (All, LOW, MEDIUM, HIGH)
  - Date range picker (From - To)
  - Nút "Apply Filters", "Clear Filters"
- Call API: `GET /admin/applications?status=...&risk_level=...&from_date=...&to_date=...&page=1&limit=20`.
- Có Pagination.

#### TASK 6: Application Detail (Path: `src/pages/admin/AdminApplicationDetailPage.jsx`)
- Call API `GET /admin/applications/{id}`.
- Chia thành các Sections:
  1. Thông tin khách hàng: User ID, email, username. (Nếu status = INFO_SUBMITTED, thêm nút "Xem thông tin cá nhân" → navigate `/admin/personal-info/{id}`).
  2. Thông tin đơn vay: Số tiền, kỳ hạn, thu nhập, DTI, tình trạng việc làm, có nhà, mục đích, credit score.
  3. ML Results (`src/components/admin/MLResultsDisplay.jsx`): Default probability (%), Risk level (badge), Risk score (gauge), Recommended amount & term. Có text so sánh giữa khách xin và model đề xuất.
  4. Actions (`src/components/admin/ApproveRejectButtons.jsx`) - *Chỉ hiện khi PENDING_REVIEW*:
     - Nút "Approve" (Xanh) → Gọi API `POST .../approve`. Có Confirm Dialog.
     - Nút "Reject" (Đỏ) → Mở Modal bắt buộc nhập lý do → Gọi API `POST .../reject`.
     - API Success → Toast message, refresh data hoặc redirect `/admin/pending`.
  5. Timeline: Submitted at, Reviewed at, Reviewed by.

#### TASK 7: Personal Info View (Path: `src/pages/admin/PersonalInfoViewPage.jsx`)
- Call API `GET /admin/applications/{id}/personal-info`.
- Hiển thị layout read-only form/card: Họ tên, CCCD/CMND, SĐT, Email, Ngày sinh, Địa chỉ, Ngày nộp.
- Nút "Quay lại" → `/admin/application/{id}`.
- Xử lý 404: Nếu chưa có thông tin, render UI Empty State: "Khách hàng chưa nộp thông tin".

#### TASK 8: UI/UX & Polish
- Navigation xuyên suốt: Breadcrumbs (nếu cần), click các links, table rows hoạt động trơn tru.
- Theme Admin: Giữ consistent color scheme với Customer App nhưng có thể chọn tone màu professional hơn.
- Add confirm dialogs cho các action nguy hiểm (Approve/Reject).

Hãy làm từng bước. Phân tích cấu trúc thư mục của tôi và báo cho tôi biết bạn đã sẵn sàng xuất code cho Task 1 và Task 2 trước chưa. CHú ý: Khi hạn chế tác động đến code của các phần khác