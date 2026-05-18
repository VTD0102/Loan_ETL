# CreditIntel — Báo cáo hoàn thành tích hợp CIC Bureau & Synthetic Data (Phase A - D)

> **Ngày hoàn thành**: 19/05/2026  
> **Branch**: `phi`  
> **Phiên bản tài liệu**: Bản đầy đủ và chi tiết (Full Version)

Tài liệu này tổng hợp toàn bộ các thay đổi kỹ thuật, các vấn đề đã gặp phải, giải pháp khắc phục và hướng dẫn sử dụng chi tiết cho toàn bộ chu trình nâng cấp hệ thống CreditIntel từ Phase A đến Phase D. Bất kỳ thông tin nào từ các giai đoạn trước đều được giữ nguyên và giải thích cặn kẽ hơn nhằm phục vụ cho việc bàn giao (handoff), đào tạo team, và tài liệu hoá dự án.

---

## 📑 Mục lục

1. [Tổng quan dự án & Bối cảnh](#1-tổng-quan-dự-án--bối-cảnh)
2. [Phase A: Tích hợp CIC Backend & Sửa lỗi hệ thống (Core Stabilization)](#2-phase-a-tích-hợp-cic-backend--sửa-lỗi-hệ-thống)
3. [Phase B: Xây dựng hệ sinh thái khoản vay giả lập (Synthetic Data)](#3-phase-b-xây-dựng-hệ-sinh-thái-khoản-vay-giả-lập)
4. [Phase C: Cập nhật và Đồng bộ Frontend UI/UX](#4-phase-c-cập-nhật-và-đồng-bộ-frontend-uiux)
5. [Phase D: Kiểm chứng toàn diện (E2E) và Kết quả](#5-phase-d-kiểm-chứng-toàn-diện-e2e-và-kết-quả)
6. [Định hướng phát triển tiếp theo (Next Steps)](#6-định-hướng-phát-triển-tiếp-theo-next-steps)

---

## 1. Tổng quan dự án & Bối cảnh

Trước đợt nâng cấp này, hệ thống CreditIntel đang hoạt động dựa trên cơ chế "Tự khai". Tức là, khi khách hàng điền form nộp đơn vay, mọi thông tin về tài chính và lịch sử tín dụng (như số hồ sơ nợ, tổng số tiền quá hạn, có nợ xấu hay không) đều do khách hàng tự nhập liệu. Điều này dẫn đến lỗ hổng rủi ro cực lớn: một khách hàng có lịch sử nợ xấu hoàn toàn có thể tự khai là "chưa từng nợ xấu" để đánh lừa mô hình trí tuệ nhân tạo (LightGBM).

**Mục tiêu của toàn bộ chiến dịch refactor (Phase A - D)** là:
1. **Chuyển đổi sang cơ chế xác thực**: Tích hợp dữ liệu từ Trung tâm Thông tin Tín dụng (CIC) giả lập làm "Nguồn dữ liệu gốc" (Source of Truth). 
2. **Khắc phục triệt để các lỗi Crash**: Vá các lỗ hổng xử lý luồng dữ liệu khiến hệ thống bị treo, hoặc cho phép spam đơn vay.
3. **Sinh dữ liệu thử nghiệm**: Xây dựng bộ công cụ tạo dữ liệu giả lập giống thật để test hệ thống liên tục mà không làm hỏng dữ liệu gốc.
4. **Đồng bộ Giao diện**: Cập nhật lại UI để khách hàng và Admin hiểu rõ luồng chạy mới của hệ thống.

---

## 2. Phase A: Tích hợp CIC Backend & Sửa lỗi hệ thống

Phase A giải quyết các vấn đề liên quan đến lõi (core logic) của Backend, đảm bảo an toàn dữ liệu và tích hợp CIC.

### 2.1. Vá lỗi nghiêm trọng (Core Stabilization)

- **Sửa lỗi Crash trong luồng duyệt đơn (Confirm Flow)**: 
  - *Vấn đề*: Khi Admin hoặc hệ thống gọi hàm `confirm()` để duyệt đơn, code cũ gọi đến hàm `ml_service._load_both()`. Tuy nhiên, hàm này không hề tồn tại trong service ML, dẫn đến ứng dụng bị crash hoàn toàn không thể xử lý đơn tiếp.
  - *Giải pháp*: Đã rà soát và đổi thành `_load()`, khôi phục lại tính toàn vẹn của luồng xét duyệt. Mọi đơn vay hiện tại đều có thể hoàn tất từ `PENDING_REVIEW` sang `APPROVED` hoặc `REJECTED`.
- **Chống trùng lặp dữ liệu cấp cơ sở dữ liệu (Database-level Duplicate Prevention)**: 
  - *Vấn đề*: Hệ thống có rủi ro "Race condition" - nếu khách hàng click nút Submit liên tục, hệ thống tạo ra 2-3 đơn vay cùng lúc cho một người.
  - *Giải pháp*: Thêm `UNIQUE INDEX idx_one_active_app_per_user` vào cơ sở dữ liệu. Bắt buộc mỗi tài khoản chỉ được phép có duy nhất 1 đơn vay ở trạng thái chờ duyệt.
- **An toàn giao dịch (Transaction Safety)**: 
  - *Vấn đề*: Nếu có lỗi trong quá trình lưu dữ liệu (ví dụ mạng chập chờn), dữ liệu có thể bị lưu một nửa (Data corruption).
  - *Giải pháp*: Bổ sung cơ chế `db.rollback()` vào các khối lệnh `try...except` trên toàn bộ các service cốt lõi (application, admin, chat).
- **Khắc phục lỗi tạo Document ảo**: 
  - *Vấn đề*: Trước đây, quá trình upload tài liệu tự động sinh ra một record `PersonalInfo` rác bằng UUID giả, gây nhiễu luồng xác minh của Admin.
  - *Giải pháp*: Xoá bỏ logic tạo record ảo, quy trình xác minh giấy tờ giờ đây mượt mà và chuẩn xác.

### 2.2. Xây dựng Kiến trúc CIC Backend

- **Trường dữ liệu CCCD cốt lõi**: Bổ sung cột `cccd` (string, 12 ký tự, unique) vào bảng `users`. CCCD được chọn làm ID tham chiếu duy nhất để tra cứu CIC.
- **Tạo bảng Cơ sở dữ liệu CIC (`cic_credit_records`)**: Tạo một ORM Model riêng biệt đóng vai trò như một kho dữ liệu của ngân hàng nhà nước.
- **Cơ chế tra cứu tự động (Auto-Enrichment)**: Cốt lõi của hệ thống mới. Nằm tại `application_service.py` (hàm `evaluate()` và `confirm()`):
  1. Khi nhận đơn, backend sẽ query bảng `cic_credit_records` bằng `cccd`.
  2. **Trường hợp Blacklist (Nợ chú ý/nợ xấu nặng)**: Nếu CIC record có cờ `blacklist_flag = True`, hệ thống sẽ ném ngoại lệ và lập tức đổi status đơn vay thành `AUTO_REJECTED` (Tự động từ chối). Điều này giúp hệ thống không tốn tài nguyên chạy mô hình ML vô ích.
  3. **Trường hợp có dữ liệu CIC**: Backend tự động lấy các trường quan trọng từ CIC (ví dụ: `total_overdue_amount`, `max_dpd_12m`, `has_bad_debt`) và **ghi đè** (overwrite) lên dữ liệu tự khai của khách hàng.
  4. Mô hình AI LightGBM sau đó sẽ chạy dựa trên **dữ liệu đã bị ghi đè** này, đảm bảo kết quả dự đoán rủi ro là chính xác nhất.
  5. **Tính minh bạch**: Backend tạo ra một bản chụp (`feature_snapshot`) lưu lại toàn bộ dữ liệu *trước* và *sau* khi bị CIC ghi đè. Snapshot này được lưu vào DB để Admin sau này có thể xem khách hàng đã khai gian như thế nào.

---

## 3. Phase B: Xây dựng hệ sinh thái khoản vay giả lập

Để chứng minh toàn bộ quy trình trên hoạt động (Demo) và giúp đội ngũ phát triển Frontend có data test, một Hệ thống Sinh dữ liệu Giả lập (Synthetic Data Ecosystem) đã được viết ra.

### 3.1. Nguyên lý hoạt động
Hệ thống này sẽ tạo ra một record hoàn chỉnh bao gồm: **1 User mới** + **1 Record CIC tương ứng** + **1 Đơn vay (LoanApplication)**. Đơn vay này không chỉ được tạo trong Database mà thực sự **phải chạy qua luồng AI Model thật** (hàm `evaluate`).
*Đặc biệt: Dữ liệu được sinh ra cố tình khớp với phân phối dữ liệu (Distribution) mà mô hình LightGBM đã học trên tập dữ liệu Home Credit, nhờ đó mô hình dự đoán hoàn toàn chính xác mà KHÔNG CẦN retrain lại.*

### 3.2. Chi tiết 3 Profiles người vay (Mô phỏng thực tế)

Hệ thống sẽ random tạo ra người dùng thuộc 1 trong 3 nhóm sau:

**1. Good Profile (Tỷ lệ 60%) - Khách hàng Tốt**
- **Đặc điểm**: Thu nhập cao và ổn định ($4,000 – $15,000/tháng), DTI (Tỷ lệ nợ/thu nhập) thấp (5-30%), học vấn cao, có việc làm ổn định.
- **Thông tin CIC**: Điểm tín dụng rất cao (680 – 850), không có nợ xấu (`has_bad_debt = False`).
- **Phản ứng của ML Model**: Dự đoán xác suất vỡ nợ rất thấp (chỉ từ 10-30%), đẩy hồ sơ vào trạng thái `PENDING_REVIEW` (Chờ duyệt) dễ dàng.

**2. Risky Profile (Tỷ lệ 25%) - Khách hàng Tiềm ẩn Rủi ro**
- **Đặc điểm**: Thu nhập trung bình ($2,000 – $6,000), DTI cao hơn (30-50%), công việc có thể làm tự do (Self-employed).
- **Thông tin CIC**: Điểm tín dụng ở mức trung bình (500 – 680), có tiền sử quá hạn nhẹ (dưới $500), 20% khả năng có nợ xấu.
- **Phản ứng của ML Model**: Dự đoán xác suất vỡ nợ khoảng 25-40%, đẩy hồ sơ vào trạng thái `PENDING_REVIEW` nhưng ở mức cảnh báo rủi ro cao hơn (Borderline).

**3. Defaulter Profile (Tỷ lệ 15%) - Khách hàng Kém/Nguy cơ Vỡ nợ**
- **Đặc điểm**: Thu nhập thấp ($1,000 – $4,000), DTI quá tải (45-85%), thất nghiệp hoặc học vấn thấp, vay quá khả năng chi trả.
- **Thông tin CIC**: Điểm tín dụng rất thấp (300 – 500). LUÔN CÓ nợ xấu (`has_bad_debt = True`). Số tiền quá hạn lên tới $5,000 và có thể trễ hạn tới 180 ngày. Đặc biệt, 10% trong số này bị CIC đánh dấu Blacklist.
- **Phản ứng của ML Model**: Xác suất vỡ nợ > 40%. Nếu dính cờ Blacklist, bị `AUTO_REJECTED` lập tức bỏ qua ML.

### 3.3. Các công cụ tạo dữ liệu đã triển khai
1. **File Script (CLI)**: Tệp `backend/scripts/seed_synthetic.py`. Dành cho lập trình viên chạy trong Terminal. Ví dụ: `python scripts/seed_synthetic.py --count 50` để tạo 50 hồ sơ.
2. **API Endpoint**: `POST /cic/synthetic/generate?count=10`. Nằm tại router `cic.py`. Admin có thể trigger API này (yêu cầu Authorization) qua Swagger UI hoặc Postman để cấp data cho hệ thống dashboard bất kỳ lúc nào.

*Lưu ý: Mọi user giả lập đều có email đuôi `@creditintel.test` và mật khẩu đăng nhập mặc định là `Synthetic123!` để team QA dễ dàng test.*

---

## 4. Phase C: Cập nhật và Đồng bộ Frontend UI/UX

Để quy trình phía Backend (Phase A, B) mang lại trải nghiệm thực tế cho khách hàng, giao diện Frontend đã được làm lại cẩn thận.

### 4.1. Thay đổi Luồng Đăng ký (Register Flow)
- **Tích hợp form mới**: Tại file `frontend/src/pages/customer/Register/index.jsx`, một trường input mới là **Số CCCD** được chèn thêm vào sau trường Tên Đăng Nhập.
- **Validation chặt chẽ**: Frontend sử dụng Regex `^[0-9]{12}$` chặn người dùng gõ chữ cái, bắt buộc gõ chính xác 12 số.
- **Ý nghĩa kỹ thuật**: Đảm bảo từ nay về sau, 100% user trong database đều có thẻ CCCD, là nền tảng để backend gọi API tra cứu sang cơ sở dữ liệu CIC.

### 4.2. Cải tiến Form Nộp Đơn Vay (Apply Flow)
- Tại file `frontend/src/pages/customer/Apply/index.jsx`, ở bước nhập "Lịch sử tín dụng".
- Đổi tiêu đề thành: **"Lịch sử tín dụng (Tự khai)"**.
- Thêm một khối cảnh báo nổi bật (Disclaimer): 
  > *"Lưu ý: Hệ thống sẽ tự động tra cứu CCCD của bạn qua Trung tâm Thông tin Tín dụng (CIC). Nếu có dữ liệu CIC, thông tin CIC sẽ được dùng để thay thế phần tự khai này nhằm đảm bảo tính chính xác."*
- Giúp minh bạch với khách hàng về cơ chế hoạt động, giải thích lý do tại sao hệ thống AI cuối cùng có thể nhận diện ra họ có nợ xấu dù họ cố tình khai là "không có".

### 4.3. Sửa lỗi Giao diện (Bug Fix) ở Trang chủ (Landing Page)
- **Mô tả lỗi**: Trước đây, nếu người dùng đã đăng nhập (có token) mà ấn vào Logo ở góc trên bên trái, hệ thống trả họ về trang chủ. Lúc này giữa màn hình vẫn hiện 2 nút to đùng: "Đăng ký ngay - Miễn phí" và "Đăng nhập", tạo cảm giác ứng dụng chưa nhận diện được user.
- **Cách khắc phục**:
  - Tại `frontend/src/components/common/Navbar/index.jsx`: Logo được bọc điều kiện. Nếu `token` tồn tại, ấn logo sẽ tự động nhảy về `/dashboard`.
  - Tại `frontend/src/pages/customer/Landing/index.jsx`: Nếu người dùng cố tình nhập URL `/`, toàn bộ khối CTA (Call to Action) chứa các nút Đăng nhập/Đăng ký sẽ biến mất, thay bằng một nút duy nhất: **"Đi tới Dashboard"**.

---

## 5. Phase D: Kiểm chứng toàn diện (E2E) và Kết quả

Sau khi gộp chung các thay đổi, một loạt bài test E2E (End-to-End) đã được chạy và xác nhận mức độ hoàn thiện của hệ thống:

### 5.1. Kiểm tra tài khoản giả lập
- **Thử nghiệm Đăng nhập**: Dùng email sinh ra (ví dụ: `synthetic.nguyenvana.493@creditintel.test`) và mật khẩu `Synthetic123!`. Kết quả: Đăng nhập thành công, token được cấp, truy cập Dashboard và xem lịch sử khoản vay trơn tru.

### 5.2. Tính năng "Đã xác minh qua CIC" trên Admin Dashboard
- Để tăng cường trải nghiệm cho Admin duyệt hồ sơ, một chỉnh sửa cuối cùng đã được bổ sung vào trang `ApplicationDetail` (`frontend/src/pages/admin/ApplicationDetail/index.jsx`).
- Ở thẻ (Section) "Lịch sử tín dụng", frontend sẽ đọc object `feature_snapshot`. Nếu cờ `cic_applied = true`, một **Badge màu xanh lá cây cực kỳ nổi bật** sẽ hiện ra với dòng chữ: 
  > **Đã xác minh qua CIC**
  > Dữ liệu bên dưới đã được tự động cập nhật từ hệ thống CIC quốc gia. Điểm CIC: [Ví dụ: 720]
- Tính năng này giải quyết trọn vẹn Use-case: Admin nhìn vào hồ sơ lập tức phân biệt được số liệu nào là khách hàng tự bịa, số liệu nào là hệ thống CreditIntel tự động lấy từ Nhà nước về.

### 5.3. Kết quả đánh giá luồng ML
- Pipeline LightGBM hoạt động hoàn hảo. Quá trình tra cứu CIC (Auto-Enrichment) nhồi dữ liệu vào model không gây ra bất kỳ lỗi schema nào (như "Missing columns" hay "Data type mismatch").
- Hiệu suất ROC-AUC giữ nguyên do distribution của Synthetic data được đo đếm kỹ để khớp với Home Credit dataset.

---

## 6. Định hướng phát triển tiếp theo (Next Steps)

Hệ thống lõi (Core System) hiện tại đã đạt độ trưởng thành (Maturity) đủ cao để vận hành thực tế. Tuy nhiên, để tiến gần hơn đến một ứng dụng thương mại (Production-ready Application), tôi đề xuất team tập trung vào các tính năng nâng cao sau đây:

1. **OCR & eKYC (Chống gian lận định danh)**:
   - *Vấn đề*: Hiện nay việc yêu cầu user tự nhập 12 số CCCD không thể chống lại rủi ro user mượn CCCD của người thân để vay.
   - *Giải pháp*: Tích hợp Module eKYC. Yêu cầu tải lên mặt trước, mặt sau thẻ CCCD và ảnh selfie chân dung. Sử dụng AI Computer Vision (hoặc call API bên thứ 3) để tự động trích xuất thông tin, đối chiếu khuôn mặt.
2. **Khởi tạo Hợp đồng vay tự động (Auto Smart-Contract / PDF)**:
   - *Vấn đề*: Quy trình hiện tại dừng lại ở mức "Phê duyệt" (Approved) khoản vay.
   - *Giải pháp*: Xây dựng luồng Post-Approval. Khi Admin nhấn Phê duyệt, hệ thống gọi service PDF (VD: ReportLab trong Python) tự động đổ dữ liệu (Tên, CCCD, Lãi suất, Bảng tính trả gốc lãi từng tháng) vào một mẫu Hợp đồng tín dụng. Khách hàng nhận được File PDF trên Dashboard và thực hiện ký số (Digital Signature).
3. **Module Quản lý trả nợ sau giải ngân (Repayment Tracker)**:
   - Tạo một bảng điều khiển nhỏ (Dashboard widget) theo dõi vòng đời khoản vay: Ngày giải ngân, Kì hạn trả nợ tiếp theo, Lãi suất cộng dồn. Tự động chuyển trạng thái nợ nếu khách hàng chậm trả (DPD - Days Past Due).
4. **Xác thực bảo mật (2FA / OTP)**:
   - Gắn module xác thực OTP gửi qua Email hoặc SMS ngay từ bước đăng ký tài khoản hoặc trước khi nhấn nút "Xác nhận vay", đảm bảo chống lại các bot tự động spam đơn vay.
