# CreditIntel — Báo cáo hoàn thành tích hợp CIC Bureau & Synthetic Data

> **Ngày hoàn thành**: 19/05/2026  
> **Branch**: `phi`  
> **Các Phase bao gồm**: A, B, C, D

---

## 📑 Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Phase A: Tích hợp CIC Backend & Core Stabilization](#2-phase-a-tích-hợp-cic-backend--core-stabilization)
3. [Phase B: Hệ sinh thái khoản vay giả lập (Synthetic Data)](#3-phase-b-hệ-sinh-thái-khoản-vay-giả-lập)
4. [Phase C: Cập nhật Frontend UI/UX](#4-phase-c-cập-nhật-frontend-uiux)
5. [Phase D: Kiểm chứng & Hoàn thiện (E2E)](#5-phase-d-kiểm-chứng--hoàn-thiện)
6. [Các bước tiếp theo (Next Steps)](#6-các-bước-tiếp-theo-next-steps)

---

## 1. Tổng quan dự án

Mục tiêu của đợt refactor này là biến CreditIntel từ một hệ thống thu thập thông tin "tự khai" sang một hệ thống xác thực đáng tin cậy bằng cách tích hợp **Trung tâm Thông tin Tín dụng (CIC)** giả lập. Thay vì tin tưởng hoàn toàn vào số liệu người dùng nhập (như nợ xấu, số hồ sơ), hệ thống giờ đây tự động đối chiếu CCCD với cơ sở dữ liệu CIC và dùng thông tin thật để chạy AI Model (LightGBM).

Song song đó, hệ thống được vá các lỗi crash nghiêm trọng (Stabilization), nâng cấp UI, và bổ sung bộ giả lập dữ liệu vay (Synthetic Generator) để phục vụ test/demo.

---

## 2. Phase A: Tích hợp CIC Backend & Core Stabilization

### Core Stabilization (Sửa lỗi nghiêm trọng)
- **Fix Crash flow duyệt đơn**: Hàm `confirm()` bị lỗi do gọi sai hàm `ml_service._load_both()` (không tồn tại). Đã sửa thành `_load()` để toàn bộ flow nộp đơn vay có thể hoạt động từ đầu đến cuối.
- **Chống Duplicate DB-level**: Thêm `UNIQUE INDEX idx_one_active_app_per_user`, ngăn chặn 1 user tạo nhiều đơn vay cùng lúc do click liên tục (race condition).
- **Transaction Safety**: Thêm `db.rollback()` vào tất cả service (`application`, `admin`, `chat`). Bất kỳ lỗi nào xảy ra giữa chừng sẽ không làm hư hỏng dữ liệu (Data corruption).
- **Fix lỗi Document**: Không tạo record `PersonalInfo` giả bằng UUID khi tải tài liệu nữa, tránh việc block quy trình xác minh thông tin.

### CIC Backend
- **CCCD Integration**: Thêm trường `cccd` vào `User` (12 số, unique).
- **CIC Database**: Tạo bảng `cic_credit_records` độc lập mô phỏng dữ liệu quốc gia.
- **Tự động đối chiếu (Auto-Enrichment)**: Khi user nộp đơn (`evaluate`/`confirm`), backend tự lấy CCCD tra cứu bảng CIC:
  - Nếu nằm trong **Blacklist** → Từ chối tự động (`AUTO_REJECTED`) ngay lập tức, không cần chạy ML.
  - Nếu có dữ liệu → **Ghi đè** các thông tin tài chính quan trọng (total_overdue, bad_debt...) bằng số liệu CIC thật.
  - Lưu kết quả so sánh (tự khai vs CIC thật) vào `feature_snapshot` để Admin xem.

---

## 3. Phase B: Hệ sinh thái khoản vay giả lập

Tạo ra hệ sinh thái tự động sinh dữ liệu thực tế để test ML Model và làm Demo mà **không cần retrain model**.

- **3 Profiles phân bổ thực tế**:
  - `Good` (60%): Điểm CIC cao, không nợ xấu → ML trả về rủi ro Thấp/Trung Bình.
  - `Risky` (25%): Điểm CIC trung bình, có nợ, DTI cao → ML trả về rủi ro Trung bình.
  - `Defaulter` (15%): Nợ xấu, DTI quá hạn → Bị CIC Blacklist hoặc ML đánh rủi ro cao (AUTO_REJECTED).
- **Tự động hoàn toàn**: API/CLI sẽ tự tạo `User` (Tên tiếng Việt) → tạo `CIC record` → đẩy đơn vay qua luồng ML pipeline thật để verify.
- **Đăng nhập được**: Các tài khoản giả lập đều được tạo với email `synthetic...` và mật khẩu `Synthetic123!` (Có thể dùng để đăng nhập và kiểm tra UI).

---

## 4. Phase C: Cập nhật Frontend UI/UX

Đồng bộ giao diện khách hàng và Admin với những thay đổi mạnh mẽ từ Backend.

- **Form Đăng ký (Register)**: Thêm field `CCCD` (bắt buộc nhập 12 số) để cấp ID cho việc tra cứu CIC.
- **Form Vay vốn (Apply)**: Thêm ghi chú rõ ràng ở phần Lịch sử Tín dụng: *"Hệ thống sẽ tự động tra cứu CCCD qua CIC. Dữ liệu CIC sẽ được dùng thay thế phần tự khai này."*
- **Landing Page & Navbar Fix**: 
  - Sửa lỗi UI khó chịu: Khi đã đăng nhập, ấn vào logo `CI CreditIntel` thay vì hiển thị "Đăng ký/Đăng nhập", hệ thống sẽ đưa thẳng người dùng vào `/dashboard`.
- **Admin Dashboard**: Giao diện chi tiết đơn vay (`ApplicationDetail`) giờ hiển thị thẻ **"Đã xác minh qua CIC"** và Điểm CIC ngay trong phần Lịch sử Tín dụng, giúp Admin biết đây là dữ liệu đã được đối chiếu, không phải tự khai.

---

## 5. Phase D: Kiểm chứng & Hoàn thiện

Quá trình E2E (End-to-end) testing đã hoàn tất. Các phần thoả mãn các tiêu chí:

1. **Synthetic Accounts có đăng nhập được không?**
   - **CÓ**. Password của mọi tài khoản giả lập là `Synthetic123!`. Khách hàng hoàn toàn có thể login để xem trạng thái đơn vay, chat với AI tư vấn.
2. **Model AI có cần Retrain không?**
   - **KHÔNG**. Các features từ hệ sinh thái giả lập và CIC được mapping chuẩn 1:1 với dataset Home Credit cũ. Model chạy bình thường, ROC-AUC vẫn giữ nguyên chất lượng.
3. **Data Integrity (Tính toàn vẹn)**:
   - Các API chặn đứng được hoàn toàn việc spam submit (nhờ Partial Unique Index và `db.rollback()`). 

---

## 6. Các bước tiếp theo (Next Steps)

Hệ thống Core hiện tại đã **rất ổn định** (Transaction-safe, CIC Integration mượt mà, ML Flow hoàn chỉnh). 
Dưới đây là những thứ nên cân nhắc để phát triển tiếp cho Production:

1. **Bổ sung OTP / Email Verification**:
   - Hiện tại đăng ký chỉ cần nhập Email và Password. Cần thêm luồng gửi OTP qua Email (hoặc SMS) để xác thực người dùng thật sự sở hữu email/CCCD đó.
2. **eKYC cho CCCD**:
   - Thay vì để user gõ chay 12 số CCCD, tích hợp một model OCR nhẹ hoặc API eKYC (ZaloPay, VNPT) để user upload ảnh CCCD mặt trước/sau → trích xuất Số CCCD, Họ Tên, Ngày Sinh. Điều này chống fake CCCD.
3. **Quản lý Hợp đồng (Smart Contracts / PDF)**:
   - Khi Admin ấn "Phê duyệt" (Approve), hệ thống nên tự động generate ra một bản Hợp đồng vay vốn (PDF) có thông tin giải ngân để user ký số.
4. **Hệ thống theo dõi thanh toán (Repayment Tracker)**:
   - Cần thêm 1 module nhỏ để theo dõi các khoản vay đã Approved: Khi nào đến hạn trả, lãi suất cộng dồn, trễ hạn bị tính phí ra sao.
5. **Giới hạn tỷ lệ API (Rate Limiting)**:
   - Bảo vệ API `/auth/register` và `/applications/evaluate` bằng Redis Rate Limiter để chống bị brute-force hoặc spam data.
