# CreditIntel Frontend — Design Rules

> Tài liệu này là **Design System bắt buộc** cho toàn bộ giao diện của hệ thống CreditIntel, bao gồm cả phần Admin.  
> Giao diện Customer đã được implement theo đúng các quy tắc dưới đây và là **chuẩn tham chiếu**.  
> Người phát triển phần Admin **phải tuân thủ nghiêm túc** để đảm bảo hệ thống ăn khớp, nhất quán.

---

## 1. Màu sắc (Color System)

Toàn bộ màu sắc được định nghĩa trong `tailwind.config.js`. **Không dùng màu hex cứng** trong JSX — chỉ dùng Tailwind class.

### Bảng màu chính

| Tên token     | Tailwind class prefix | Mục đích                          |
|---------------|-----------------------|-----------------------------------|
| `primary`     | `primary-*`           | Accent chính — xanh dương         |
| `success`     | `success-*`           | Thành công, trạng thái tích cực   |
| `warning`     | `warning-*`           | Cảnh báo, chờ xử lý               |
| `danger`      | `danger-*`            | Lỗi, từ chối, rủi ro cao          |
| `gray-*`      | (Tailwind default)    | Text, border, nền phụ             |

### Giá trị chính xác

```js
// tailwind.config.js — theme.extend.colors
primary: {
  50:  '#eff6ff',  // nền nhạt (hover bg, section bg)
  100: '#dbeafe',
  200: '#bfdbfe',
  400: '#60a5fa',
  500: '#3b82f6',
  600: '#2563eb',  // ← màu chính, dùng cho button, link, accent
  700: '#1d4ed8',  // hover state
  800: '#1e40af',
}
success: { 50: '#f0fdf4', 100: '#dcfce7', 500: '#22c55e', 600: '#16a34a', 700: '#15803d' }
warning: { 50: '#fffbeb', 100: '#fef3c7', 500: '#f59e0b', 600: '#d97706', 700: '#b45309' }
danger:  { 50: '#fef2f2', 100: '#fee2e2', 500: '#ef4444', 600: '#dc2626', 700: '#b91c1c' }
```

### Quy tắc dùng màu

- **Nền trang:** `bg-white` (trang form/detail) hoặc `bg-gray-50` (trang dashboard/list)
- **Nền card:** luôn `bg-white`
- **Text tiêu đề:** `text-gray-900`
- **Text mô tả/phụ:** `text-gray-500` hoặc `text-gray-600`
- **Text label form:** `text-gray-700`
- **Border:** `border-gray-200` (card), `border-gray-300` (input)

---

## 2. Typography

Font duy nhất: **Inter** (đã load qua Google Fonts trong `index.html`).

| Loại text          | Class Tailwind                              | Ví dụ dùng                       |
|--------------------|---------------------------------------------|----------------------------------|
| Tiêu đề trang      | `text-2xl font-bold text-gray-900`          | `<h1>` đầu page                  |
| Tiêu đề section    | `text-lg font-semibold text-gray-900`       | Heading trong card               |
| Sub-heading card   | `text-base font-semibold text-gray-900`     | Label nhóm trong card            |
| Label form         | `text-sm font-medium text-gray-700`         | Dùng class `.label`              |
| Body text          | `text-sm text-gray-500`                     | Mô tả, hint, phụ chú             |
| Text nhỏ/meta      | `text-xs text-gray-400`                     | Ngày tháng, ID, tag phụ          |
| Text lỗi           | `text-xs text-danger-600`                   | Dùng class `.error-msg`          |

**Không dùng font-size tùy tiện** ngoài hệ thống trên.

---

## 3. Layout & Spacing

### Cấu trúc trang chuẩn

```jsx
// Trang dashboard / list (nền xám)
<div className="min-h-screen bg-gray-50">
  <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    {/* nội dung */}
  </div>
</div>

// Trang form / detail (nền xám, container hẹp hơn)
<div className="min-h-screen bg-gray-50 py-10 px-4">
  <div className="max-w-2xl mx-auto">
    {/* nội dung */}
  </div>
</div>
```

### Max-width theo loại trang

| Loại trang                        | Max-width          |
|-----------------------------------|--------------------|
| Form đơn lẻ (register, apply…)    | `max-w-lg`         |
| Form đơn vay (nhiều trường)       | `max-w-2xl`        |
| Chi tiết / detail page            | `max-w-3xl`        |
| Dashboard / list page             | `max-w-4xl`        |
| Landing page / full-width section | `max-w-5xl` hoặc `max-w-6xl` |

### Padding nội dung

- Container ngang: `px-4 sm:px-6`
- Padding dọc trang: `py-10`
- Padding trong card: `p-6` (chuẩn) · `p-8` (form) · `p-4` (compact)
- Khoảng cách giữa các section: `mb-6` hoặc `mb-8`

### Grid

```jsx
// 2 cột responsive
<div className="grid sm:grid-cols-2 gap-5"> ... </div>

// 3 cột responsive
<div className="grid sm:grid-cols-3 gap-4"> ... </div>

// 4 cột responsive (dùng cho stats/KPI cards)
<div className="grid grid-cols-2 sm:grid-cols-4 gap-3"> ... </div>
```

---

## 4. Component Classes (CSS Utility)

Các class này được định nghĩa trong `src/index.css` — **bắt buộc dùng** thay vì viết Tailwind class thủ công.

### Buttons

```jsx
<button className="btn-primary">   // Xanh dương — action chính
<button className="btn-outline">   // Viền xám — action phụ
<button className="btn-danger">    // Đỏ — hành động nguy hiểm (xóa, từ chối)
<button className="btn-ghost">     // Không viền — action ít quan trọng
```

**Tất cả button đều có sẵn:** `disabled:opacity-50 disabled:cursor-not-allowed` — chỉ cần thêm prop `disabled={loading}`.

Kích thước mở rộng khi cần:
```jsx
<button className="btn-primary w-full py-3 text-base">  // Full width, lớn hơn
<button className="btn-outline text-sm px-4 py-2">      // Nhỏ hơn
```

### Form elements

```jsx
// Label
<label className="label">Tên trường</label>

// Input chuẩn
<input className="input" />

// Input có lỗi (kết hợp với react-hook-form)
<input className={`input ${errors.field ? 'input-error' : ''}`} />

// Error message
<p className="error-msg">{errors.field?.message}</p>

// Textarea (thêm resize-none)
<textarea className="input resize-none" rows={3} />

// Select (dùng class input)
<select className="input"> ... </select>
```

### Card

```jsx
<div className="card">           // bg-white rounded-xl border border-gray-200 shadow-sm
<div className="card p-6">      // + padding chuẩn
<div className="card p-8">      // + padding form
```

Hover effect cho card có thể click:
```jsx
<div className="card hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
```

---

## 5. Shared Components — Bắt buộc tái sử dụng

Admin **phải dùng lại** các component sau. **Không tự tạo component trùng chức năng.**

### `LoadingSpinner`
```jsx
import LoadingSpinner from '../../components/common/LoadingSpinner'

<LoadingSpinner />            // size mặc định: md (h-7 w-7)
<LoadingSpinner size="sm" />  // h-4 w-4 — dùng trong button
<LoadingSpinner size="lg" />  // h-10 w-10 — dùng cho full-page loading
```

Dùng trong button loading:
```jsx
<button disabled={loading} className="btn-primary">
  {loading && <LoadingSpinner size="sm" className="mr-2" />}
  {loading ? 'Đang xử lý...' : 'Xác nhận'}
</button>
```

### `Modal`
```jsx
import Modal from '../../components/common/Modal'

<Modal
  open={isOpen}              // boolean — bắt buộc
  onClose={() => setOpen(false)}  // function — bắt buộc
  title="Tiêu đề modal"     // string — tuỳ chọn
  maxWidth="max-w-md"        // string — mặc định max-w-md, có thể đổi thành max-w-lg, max-w-xl
>
  {/* nội dung modal */}
</Modal>
```

### `StatusBadge` và `RiskBadge`
```jsx
import { StatusBadge, RiskBadge } from '../../components/common/Badge'

// Hiển thị trạng thái đơn vay
<StatusBadge status="PENDING_REVIEW" />
<StatusBadge status="AUTO_REJECTED" />
<StatusBadge status="AWAITING_INFO" />

// Hiển thị mức rủi ro
<RiskBadge level="LOW" />
<RiskBadge level="MEDIUM" />
<RiskBadge level="HIGH" />
```

**Không tự định nghĩa màu cho badge** — tất cả màu đều lấy từ `STATUS_META` / `RISK_META` trong `src/utils/format.js`.

### `ApplicationTimeline`
```jsx
import ApplicationTimeline from '../../components/customer/ApplicationTimeline'

<ApplicationTimeline app={applicationObject} />
// app phải có trường: status, submitted_at, reviewed_at
```

### `ApplicationCard`
```jsx
import ApplicationCard from '../../components/customer/ApplicationCard'

<ApplicationCard app={applicationObject} />
<ApplicationCard app={applicationObject} compact />  // giao diện nhỏ gọn hơn
```

---

## 6. Shared Utilities — Bắt buộc dùng

File: `src/utils/format.js`

```js
import { formatCurrency, formatDate, formatDateTime, STATUS_META, RISK_META } from '../../utils/format'

formatCurrency(15000)      // → "$15.000" (định dạng vi-VN)
formatDate('2025-04-20T09:30:00')      // → "20/04/2025"
formatDateTime('2025-04-20T09:30:00')  // → "20/04/2025, 09:30"
```

**Dùng `STATUS_META` / `RISK_META` để lấy màu** thay vì tự hardcode:
```js
const meta = STATUS_META['PENDING_REVIEW']
// meta.label  → "Chờ xét duyệt"
// meta.bg     → "bg-warning-50"
// meta.text   → "text-warning-700"
// meta.border → "border-warning-200"
```

---

## 7. Trạng thái đơn vay & Màu sắc chuẩn

Đây là **nguồn sự thật duy nhất** cho màu trạng thái — lấy từ `STATUS_META`:

| Status            | Label               | Màu nền         | Màu chữ          | Màu border          |
|-------------------|---------------------|-----------------|------------------|---------------------|
| `AUTO_REJECTED`   | Tự động từ chối     | `bg-danger-50`  | `text-danger-700`  | `border-danger-200`  |
| `ADMIN_REJECTED`  | Đã từ chối          | `bg-danger-50`  | `text-danger-700`  | `border-danger-200`  |
| `PENDING_REVIEW`  | Chờ xét duyệt       | `bg-warning-50` | `text-warning-700` | `border-warning-200` |
| `AWAITING_INFO`   | Chờ thông tin       | `bg-success-50` | `text-success-700` | `border-success-200` |
| `INFO_SUBMITTED`  | Đã nộp thông tin    | `bg-primary-50` | `text-primary-700` | `border-primary-200` |

Màu mức rủi ro — lấy từ `RISK_META`:

| Risk Level | Label        | Màu nền         | Màu chữ          |
|------------|--------------|-----------------|------------------|
| `LOW`      | Thấp         | `bg-success-50` | `text-success-700` |
| `MEDIUM`   | Trung bình   | `bg-warning-50` | `text-warning-700` |
| `HIGH`     | Cao          | `bg-danger-50`  | `text-danger-700`  |

---

## 8. Auth Store & API — Bắt buộc dùng chung

### Auth Store (Zustand)

```js
import useAuthStore from '../../store/authStore'

// Trong component
const token  = useAuthStore((s) => s.token)
const user   = useAuthStore((s) => s.user)
const logout = useAuthStore((s) => s.logout)
const setAuth = useAuthStore((s) => s.setAuth)

// Đăng nhập thành công:
setAuth(access_token, user)  // tự lưu localStorage + update state

// Đăng xuất:
logout()  // tự xóa localStorage + reset state
```

**Không tự lưu token vào `localStorage` thủ công** — luôn dùng `setAuth()` và `logout()`.

### Axios Instance

```js
import api from '../../services/api'

// Tất cả API call phải dùng instance này
// JWT tự động được đính kèm vào mọi request
// 401 tự động redirect về /login

const res = await api.get('/admin/applications')
const res = await api.post('/admin/applications/1/approve', { admin_note: '...' })
```

**Không tạo axios instance mới.** Thêm API call admin vào file mới `src/services/admin.js` theo cùng pattern:

```js
// src/services/admin.js (tạo mới theo pattern này)
import api from './api'

export const getAdminApplications = (params) => api.get('/admin/applications', { params })
export const approveApplication   = (id, data) => api.post(`/admin/applications/${id}/approve`, data)
export const rejectApplication    = (id, data) => api.post(`/admin/applications/${id}/reject`, data)
```

### ProtectedRoute

```jsx
import ProtectedRoute from '../../components/ProtectedRoute'

// Dùng cho tất cả route cần đăng nhập
<Route path="/admin/dashboard" element={
  <ProtectedRoute>
    <AdminDashboardPage />
  </ProtectedRoute>
} />
```

---

## 9. Form Pattern (react-hook-form)

Tất cả form phải dùng `react-hook-form`. Pattern chuẩn:

```jsx
import { useForm } from 'react-hook-form'

const { register, handleSubmit, formState: { errors } } = useForm()

// Cấu trúc một field:
<div>
  <label className="label">Tên field</label>
  <input
    className={`input ${errors.fieldName ? 'input-error' : ''}`}
    {...register('fieldName', {
      required: 'Bắt buộc',
      // thêm các rule khác nếu cần
    })}
  />
  {errors.fieldName && <p className="error-msg">{errors.fieldName.message}</p>}
</div>
```

---

## 10. Loading / Error / Empty States

**Mọi page đều phải có đủ 3 trạng thái này.**

### Loading state

```jsx
// Full-page loading
if (loading) return (
  <div className="min-h-screen flex items-center justify-center bg-gray-50">
    <LoadingSpinner size="lg" />
  </div>
)

// Loading trong card
<div className="card p-12 flex items-center justify-center">
  <LoadingSpinner size="lg" />
</div>
```

### Error state

```jsx
// Full-page error
if (error) return (
  <div className="min-h-screen flex items-center justify-center bg-gray-50">
    <div className="card p-8 text-center max-w-sm w-full">
      <p className="text-danger-600 mb-4">{error}</p>
      <button onClick={() => navigate(-1)} className="btn-primary">Quay lại</button>
    </div>
  </div>
)

// Inline error trong card
<div className="card p-8 text-center text-danger-600">{error}</div>
```

### Empty state

```jsx
// Pattern chuẩn cho empty state
<div className="text-center py-16 px-4">
  <div className="w-20 h-20 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto mb-5">
    {/* SVG icon phù hợp */}
  </div>
  <h3 className="text-xl font-bold text-gray-900 mb-2">Tiêu đề</h3>
  <p className="text-gray-500 mb-6 max-w-sm mx-auto">Mô tả ngắn</p>
  <button className="btn-primary">Action</button>
</div>
```

---

## 11. Notifications (react-toastify)

```js
import { toast } from 'react-toastify'

toast.success('Thao tác thành công!')
toast.error('Có lỗi xảy ra, vui lòng thử lại.')
toast.info('Thông tin cần biết.')
toast.warning('Cảnh báo.')
```

`ToastContainer` đã được mount sẵn trong `src/main.jsx` — **không mount thêm**.

---

## 12. Animations

Các animation được định nghĩa sẵn trong `src/index.css`:

```jsx
// Fade in từ dưới lên — dùng cho card, modal nội dung
<div className="animate-fade-in"> ... </div>

// Slide up — tự động dùng cho Modal panel

// Hover effect cho card có thể click
<div className="card hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">

// Hover effect cho button/link thứ cấp
<button className="... transition-colors duration-150 hover:text-primary-600">
```

**Không dùng animation library khác** (framer-motion, GSAP, v.v.) — dùng Tailwind transition/animation là đủ.

---

## 13. Navbar

Navbar (`src/components/common/Navbar/index.jsx`) đã xử lý cả 2 trạng thái logged-in / guest và cả mobile. Admin chỉ cần đảm bảo:

- Navbar admin có thể là component riêng **nhưng phải giữ nguyên** `h-16`, `sticky top-0 z-40`, `bg-white/95 backdrop-blur-sm`, `border-b border-gray-200 shadow-sm`
- Logo `CI` với `bg-primary-600 rounded-lg` phải xuất hiện nhất quán
- Hamburger menu trên mobile: breakpoint `md` (768px)

---

## 14. Responsive Design

Breakpoint duy nhất cần quan tâm: **`sm` (640px)** và **`md` (768px)**.

```jsx
// Grid: 1 cột mobile → 2 cột tablet+
<div className="grid sm:grid-cols-2 gap-5">

// Ẩn/hiện theo màn hình
<span className="hidden sm:block">CreditIntel</span>

// Padding responsive
<div className="px-4 sm:px-6">
```

Tất cả trang phải kiểm tra trên mobile (375px) và desktop (1280px) trước khi hoàn thành.

---

## 15. Icon

Dùng **SVG inline** theo pattern sau (nhất quán với toàn bộ Customer pages):

```jsx
<svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="..." />
</svg>
```

- Kích thước thông dụng: `w-4 h-4` (nhỏ), `w-5 h-5` (chuẩn), `w-6 h-6` (lớn), `w-8 h-8` (icon trong button tròn)
- Màu icon theo context: `text-gray-400` (placeholder), `text-gray-600` (active), `text-primary-600` (highlight)
- **Không dùng icon library** (heroicons package, lucide-react, v.v.) — dùng SVG inline là đủ và tránh thêm dependency.

---

## 16. Những điều KHÔNG được làm

| ❌ Không làm                                           | ✅ Thay bằng                                         |
|-------------------------------------------------------|------------------------------------------------------|
| Dùng màu hex cứng (`#2563eb`)                         | Dùng Tailwind class (`text-primary-600`)             |
| Tự tạo loading spinner mới                            | Dùng `<LoadingSpinner />`                            |
| Tự tạo modal mới                                      | Dùng `<Modal />`                                     |
| Tự render badge trạng thái với màu hardcode           | Dùng `<StatusBadge />` hoặc lấy từ `STATUS_META`    |
| Tự lưu token vào `localStorage` thủ công             | Dùng `useAuthStore().setAuth()`                      |
| Tạo axios instance mới                                | Import `api` từ `src/services/api.js`                |
| Dùng `font-size` ngoài hệ thống (vd: `text-3xl` tuỳ tiện) | Tuân theo bảng Typography ở mục 2              |
| Dùng `border-radius` tuỳ tiện                         | `rounded-lg` (input, button) · `rounded-xl` (card) · `rounded-2xl` (modal, large card) · `rounded-full` (badge, avatar) |
| Mount thêm `<ToastContainer />`                       | Đã có sẵn trong `main.jsx`                           |
| Dùng animation library bên ngoài                      | Dùng Tailwind class + `animate-fade-in` có sẵn      |
| Dùng icon library (heroicons, lucide…)                | Dùng SVG inline theo pattern mục 15                  |

---

> **Nguyên tắc cuối:** Khi không chắc chắn về một quyết định UI, hãy tham chiếu code Customer tại `src/pages/customer/` — đó là chuẩn thiết kế của hệ thống.
