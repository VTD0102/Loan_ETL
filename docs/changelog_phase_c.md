# CreditIntel — Changelog: Phase C — Frontend CIC Integration & UI Fixes

> **Ngày thực hiện**: 19/05/2026  
> **Branch**: `phi`  
> **Phụ thuộc**: Phase A (CIC Backend) và Phase B (Synthetic Data)

---

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [Cập nhật luồng đăng ký (Registration)](#cập-nhật-luồng-đăng-ký)
3. [Cải tiến Form nộp đơn vay (Apply Form)](#cải-tiến-form-nộp-đơn-vay)
4. [Sửa lỗi UI Landing Page (Logo Redirect)](#sửa-lỗi-ui-landing-page)
5. [Danh sách file thay đổi](#danh-sách-file-thay-đổi)

---

## Tổng quan

Phase C tập trung vào việc **đồng bộ Frontend với Backend CIC** đã làm ở Phase A & B. 
Nhiệm vụ chính bao gồm:
- Bắt buộc thu thập CCCD khi người dùng mới đăng ký.
- Cập nhật Form nộp đơn vay để giải thích rõ về cơ chế tự động tra cứu CIC.
- Sửa lỗi UI/UX nhỏ: Trang chủ (Landing page) hiển thị sai luồng nếu người dùng đã đăng nhập.

---

## Cập nhật luồng đăng ký (Registration)

**File**: `frontend/src/pages/customer/Register/index.jsx`

- **Thêm input CCCD**: Bổ sung trường nhập Số CCCD vào form đăng ký tài khoản.
- **Validation Frontend**: 
  - Đảm bảo độ dài chính xác là 12 ký tự (`maxLength={12}`).
  - Sử dụng Regex `^[0-9]{12}$` để đảm bảo chỉ nhập chữ số.
- **API Call**: Truyền thêm biến `cccd` vào request gửi lên backend `apiRegister`.

**Lợi ích**: Bất kỳ user mới nào đăng ký cũng sẽ có CCCD, giúp hệ thống ở Phase A tự động match được với dữ liệu CIC giả lập hoặc tra cứu thật sau này.

---

## Cải tiến Form nộp đơn vay (Apply Form)

**File**: `frontend/src/pages/customer/Apply/index.jsx`

- **Cập nhật tiêu đề**: Đổi section "Lịch sử tín dụng" thành "Lịch sử tín dụng (Tự khai)".
- **Thêm Note giải thích (Disclaimer)**: Thêm thông báo UI rõ ràng:
  > *"Lưu ý: Hệ thống sẽ tự động tra cứu CCCD của bạn qua Trung tâm Thông tin Tín dụng (CIC). Nếu có dữ liệu CIC, thông tin CIC sẽ được dùng để thay thế phần tự khai này nhằm đảm bảo tính chính xác."*
- **Ý nghĩa**: 
  - Khách hàng không bị bối rối khi thấy các thông tin tự khai của mình bị thay đổi trong quá trình duyệt.
  - Tăng độ minh bạch và uy tín của hệ thống.
  - Vẫn giữ các trường tự khai để làm fallback (nếu user không có record trên CIC).

---

## Sửa lỗi UI Landing Page (Logo Redirect)

**File 1**: `frontend/src/components/common/Navbar/index.jsx`
**File 2**: `frontend/src/pages/customer/Landing/index.jsx`

- **Vấn đề cũ**: Khi user đã đăng nhập, ấn vào Logo `CI CreditIntel` trên thanh điều hướng vẫn bị đưa về trang chủ (`/`). Trang chủ lúc này lại hiển thị 2 nút "Đăng ký ngay / Đăng nhập" rất vô lý vì user đang ở trạng thái đã đăng nhập.
- **Giải pháp**:
  - **Navbar**: Đổi link của Logo. Nếu phát hiện có `token` (đã đăng nhập), logo sẽ link tới `/dashboard` thay vì `/`.
  - **Landing Page**: Nếu user bằng cách nào đó vẫn vào trang `/` khi đã đăng nhập, thay vì hiện "Đăng ký / Đăng nhập", UI sẽ tự động đổi thành một nút duy nhất: **"Đi tới Dashboard"**.

---

## Danh sách file thay đổi

| File | Thay đổi |
|------|----------|
| `frontend/src/pages/customer/Register/index.jsx` | Bổ sung field `cccd` (input UI + validation + API payload). |
| `frontend/src/pages/customer/Apply/index.jsx` | Thêm note giải thích cơ chế CIC ghi đè thông tin tự khai. |
| `frontend/src/components/common/Navbar/index.jsx` | Sửa link của logo: trỏ về `/dashboard` nếu đã login. |
| `frontend/src/pages/customer/Landing/index.jsx` | Thay nút Đăng ký/Đăng nhập thành "Đi tới Dashboard" nếu đã login. |

---

✅ **Phase C hoàn thành!** Giao diện đã hoạt động đồng bộ với tính năng CIC và các luồng UX đã mượt mà hơn.
