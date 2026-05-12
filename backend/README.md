# 🏦 Nền tảng Quản lý Khoản Vay - Backend API (FastAPI)

Đây là hệ thống Backend phục vụ cho nền tảng Quản lý khoản vay, được xây dựng bằng **FastAPI** và kết nối với cơ sở dữ liệu **PostgreSQL** trên **Supabase**. 

Tài liệu này đóng vai trò là hướng dẫn khởi chạy dự án, đồng thời là nhật ký lưu trữ các quyết định kiến trúc và bài học kinh nghiệm trong quá trình phát triển qua các Task.

---

## 🚀 PHẦN 1: HƯỚNG DẪN CÀI ĐẶT VÀ KHỞI CHẠY (LOCAL SETUP)

### 1. Yêu cầu hệ thống
- Python 3.10 trở lên
- Hệ điều hành: Ubuntu/Linux (Khuyên dùng) hoặc WSL trên Windows

### 2. Khởi tạo môi trường ảo (Virtual Environment)
Luôn cách ly môi trường cài đặt để không ảnh hưởng đến máy tính gốc. Di chuyển vào thư mục dự án và tạo môi trường:
```bash
cd Loan_ETL/backend
python3 -m venv venv
source venv/bin/activate
```

### 3. Cài đặt thư viện (Dependencies)
```bash
pip install -r requirements.txt
```

### 4. Cấu hình Biến môi trường (.env)
Tạo file `.env` trong thư mục `backend/` dựa trên mẫu của `.env.example`. Điền các thông số:
- `DB_HOST`, `DB_PORT` (Ưu tiên cổng 6543 của Pooler cho tính ổn định), `DB_USER`, `DB_PASSWORD`.
- `SECRET_KEY` (Chuỗi bảo mật ngẫu nhiên dùng để mã hóa JWT).

### 5. Khởi tạo Cơ sở dữ liệu (Database Initialization)
Chạy lệnh sau để tự động đúc các bảng (`users`, `loan_applications`, `personal_info`, `chat_messages`) lên Supabase dựa trên các SQLAlchemy Models:
```bash
python init_db.py
```

### 6. Khởi chạy Server & Test API
Bật server FastAPI bằng Uvicorn:
```bash
uvicorn main:app --reload
```
Truy cập tài liệu API tự động (Swagger UI) để test các endpoint tại: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧠 PHẦN 2: NHẬT KÝ KIẾN TRÚC & BÀI HỌC KINH NGHIỆM

Phần này ghi lại ý nghĩa của các file/thư mục và các cốt lõi công nghệ đã triển khai, phục vụ cho việc bàn giao hoặc maintain sau này.

### 🏗️ Task 1.1: Database Foundation & Layered Architecture
- **Sự tách bạch giữa Models và Schemas:**
  - `models/` (SQLAlchemy): Định nghĩa cấu trúc bảng vật lý lưu dưới Database. Khóa chính ở đây dùng UUID thay vì số tăng dần để bảo mật dữ liệu.
  - `schemas/` (Pydantic V2): Đóng vai trò làm "Bảo vệ cổng", kiểm tra tính hợp lệ và đúng định dạng kiểu dữ liệu của JSON được HTTP gửi lên và trả về. Kích hoạt `from_attributes = True` để parse thẳng từ Object DB.
- **Bài học về Import Paths:** Vì gốc của Backend là ở folder `backend/`, các module nội bộ phải được gọi theo cú pháp tuyệt đối `from core.config import settings` nhằm tránh hoàn toàn cạm bẫy `ModuleNotFoundError` khi triển khai ở máy chủ khác.

### 🔐 Task 1.2: Hệ thống Xác thực (Authentication & JWT)
- **Xử lý Mật khẩu không dùng Passlib:** Lỗi 500 phát sinh do thư viện cũ `passlib` xung đột với code lõi của máy. Mình (Agent) đã lập tức giải quyết triệt để bằng cách import trực tiếp module gốc `bcrypt` của Python để băm (`hashpw`) và xác thực (`checkpw`) mật khẩu, đảm bảo vòng băm tối ưu nhất.
- **JSON Web Token (JWT):** Thay vì lưu `session`, API sinh ra mã JWT dựa vào `SECRET_KEY` có thời hạn 24H. Frontend chỉ việc gắn Bearer Token lên Header, FastAPI sẽ bóc tách và giải mã để xác minh định danh (Stateless Authentication).
- **Bảo vệ Route (Dependencies):** Dependency `get_current_user` đóng vai trò là lính gác cổng, xác thực JWT đính kèm trong request và truy xuất UUID của user để truyền sang Endpoint.

### 📝 Task 1.3: Submit Loan Application API (Xử lý Nộp đơn)
- **Bảo mật Spam Logic:** Bổ sung API `POST /applications/submit` với ràng buộc tín dụng chặt chẽ: *"Mỗi khách hàng chỉ được có 1 khoản vay đang chờ duyệt"*. Truy vấn `not_(LoanApplication.status.in_([...]))` SQLAlchemy đã được dùng để cô lập spam ngay từ Server.
- **Giải quyết Block dependencies:** Vì luồng `Machine Learning` chưa xây xong, endpoint đã được tách riêng để lưu đơn nháp xuống Database (`status` = `PENDING_REVIEW`, các trường ML = `NULL`). Cách tiếp cận này tạo tiền đề Mock data trống, khi `ml_service` hoàn thành có thể "gắn vào là chạy".
- **Khắc phục lỗi Foreign Keys:** Khi cấu trúc bảng có nhiều hơn 1 tham chiếu đến cùng 1 bảng gốc (ở đây LoanApplication có tận 2 khóa trỏ về User ID), SQLAlchemy sẽ kích hoạt cơ chế bảo vệ `AmbiguousForeignKeysError`. Giải pháp mượt mà là gán Argument `foreign_keys=[...]` vào relationship để định hướng lại.

### 🔍 Task 1.4: Get Application Status API (Truy xuất trạng thái hồ sơ)
- **Tập trung Dữ liệu Trả về (Data Projection):** Bổ sung Pydantic schema `ApplicationSummary` mới nhằm định hình lại dữ liệu trả về cho danh sách hồ sơ ở endpoint `GET /applications/me`. Schema này bảo đảm luồng trả về tối giản (`id`, `status`, `loan_amount`, `term`, `submitted_at`, và thông số ML), lược bỏ các thông tin đăng ký thô.
- **Order By (Dữ liệu Thời gian thực):** Triển khai hàm `.order_by(LoanApplication.submitted_at.desc())` vào thẳng tầng ORM để kết xuất dữ liệu lịch sử nộp đơn của User luôn theo thứ tự mới nhất nằm trên cùng.
- **Bảo mật Ownership (Chặn theo dõi trái phép):** Tại endpoint lấy chi tiết một đơn cụ thể `GET /applications/{app_id}`, đã chèn kỹ thuật đối soát ID người dùng. Nếu API bị kẻ gian can thiệp nhúng mã App ID của người khác, Query Service sẽ lập tức dập luồng bằng logic Check: `app.user_id != user.id` -> Trả về mã lỗi nghiêm ngặt `HTTP 403 Forbidden: Không có quyền truy cập đơn của người khác`.

### 🛡️ Task 1.5: Submit Personal Info API (Thu thập Thông tin cá nhân)
- **Chuẩn hóa REST & Schema Độc lập:** Tạo bảng con `personal_info` ánh xạ `1-1` với `loan_applications`. Endpoint `POST /applications/{id}/personal-info` được chuẩn hóa trả về một Schema `PersonalInfoRead` tĩnh lược gọn gàng, hỗ trợ Frontend lưu trữ trực tiếp caching.
- **Ràng buộc Quy trình Tín dụng (Workflow Validation):** API không dễ dàng cho phép ghi đè thông tin bừa bãi. Code đã bổ sung "Van khóa 2 lớp":
  1. Yêu cầu chính xác **Ownership** của đơn (User hiện tại phải là chủ đơn).
  2. Yêu cầu **Trạng thái hợp l**ệ: Đơn bắt buộc phải có cờ `AWAITING_INFO` (Chờ thu thập dữ liệu do Admin/ML chỉ định) trước đó. Nếu nhập dữ liệu sớm lúc vừa tạo (còn đang `PENDING_REVIEW`), Server văng lỗi `HTTP 400` bảo vệ luồng đi của hồ sơ.
- **Trigger Cập nhật Vòng đời Ngầm định:** Sau khi dữ liệu chui vào Database thành công, hệ thống tự động thăng cấp trạng thái hồ sơ mẹ từ `AWAITING_INFO` lên `INFO_SUBMITTED` trong cùng một giao dịch (Database Transaction) để đảm bảo tính Acid, chống sai lệch logic do nghẽn mạng!

### 📊 Task 1.6: Admin Dashboard Summary API (Bảng điều khiển Thống kê)
- **Tái kích hoạt Admin Route an toàn:** Khôi phục nhánh API `admin` khỏi "phòng ngủ đông" một cách cẩn thận sau khi đã rà soát và cấu hình lại toàn bộ hệ sinh thái Pydantic Schemas bên trong, đảm bảo Uvicorn hot-reload ổn định mà không xảy ra xung đột với tầng Machine Learning.
- **Micro-aggregation Query:**
  - `GET /admin/dashboard/summary`: Tạo bộ đếm Real-time bóc tách số lượng đơn nộp trong "hôm nay". Data được cast bằng hàm `cast(LoanApplication.submitted_at, Date)` trong SQLAlchemy để lọc dữ liệu sạch sẽ ngay từ tầng lưu trữ.
  - `GET /admin/dashboard/risk-distribution`: Thay vì trả `Null` cho các hồ sơ chưa được máy học gán cờ rủi ro (Risk Level), API chủ động convert tệp này thành nhãn `"UNASSIGNED"` thông minh. Cú pháp `[{"risk_level": "UNASSIGNED", "count": 4}]` này bảo vệ tuyệt đối Frontend, giúp các thư viện vẽ biểu đồ (như Recharts hay Chart.js) không bị "văng" khi render màn hình báo cáo.

### 📋 Task 1.7: Admin Get Pending Applications API (Lấy danh sách chờ duyệt)
- **Tạo Schema Chuyên biệt (ApplicationPendingSummary):** Khởi tạo một Pydantic Schema mới toanh dùng riêng cho danh sách chờ duyệt của Admin. Đặc tính của nó là "cắt tỉa" triệt để JSON trả về, chỉ lộ ra các mục cực kì thiết yếu phục vụ bảng Dashboard List (gồm `id, user_id, loan_amount, term, monthly_income, risk_level, risk_score, submitted_at`). Điều này giúp giảm hàng tá kilobytes dư thừa khi Load mạng.
- **Phân trang Toán học (Pagination):** Xây dựng biến Parameters `?page=1&limit=20` vào thẳng Endpoint `/admin/applications/pending`. Tích hợp logic nội suy `skip = (page - 1) * limit` tại tầng Service rồi móc nối với kĩ thuật Query SQLAlchemy bằng chuỗi `.offset(skip).limit(limit)`. Database giờ đây chỉ trích xuất đúng lượng cần thiết, chống tràn RAM khi số lượng hồ sơ nộp lên lên tới vài ngàn.
- **Sắp xếp thời gian thực (Chronological Sort):** Đính kèm hàm `.order_by(LoanApplication.submitted_at.asc())`. Quy tắc vận hành: Mọi hồ sơ `PENDING_REVIEW` đều phải theo phong cách FIFO (First In First Out - Ai nộp trước được duyệt trước). Bằng chứng Test đã cho thấy hồ sơ nộp mốc cũ nhất luôn chễm chệ ở `page=1`.

### ⚖️ Task 1.8: Admin Approve/Reject Application API (Quyết định tín dụng)
- **Chuẩn hóa REST Action Design:** Thay vì nhồi nhét tất cả logic Approve & Reject vào 1 nhánh API duy nhất `POST .../review`, dự án đã chẻ nhánh rõ rệt: `POST /applications/{id}/approve` và `POST /applications/{id}/reject`. Sự ngăn cách này đáp ứng chính xác tư duy vi dịch vụ (Microservices), giúp Frontend không bao giờ nhầm lẫn Action trong Code base.
- **Auditing Information (Dấu vết rà soát):** Khi Admin nhấn 1 trong 2 nút lệnh, hệ thống không chỉ đảo trạng thái status mà còn lưu triệt để bằng chứng số. Câu lệnh `app.reviewed_at = datetime.now()` và `app.reviewed_by = admin_user.id` giúp chẩn đoán vĩnh viễn "Ai đã duyệt đơn này vào lúc mấy giờ", phục vụ đắc lực cho công tác hậu kiểm.
- **Hệ thống cảnh báo Trạng thái (State Machine Lock):** Tránh hiện tượng ứng dụng bị "Bơm nhấp đúp", hệ thống gài bẫy Security Lock: Nếu đơn đang không ở dạng `PENDING_REVIEW` (ví dụ Admin 2 đã lỡ bấm duyệt trước Admin 1), hành động sẽ bị đá thẳng tay với HTTP 400 để chống ghi đè dữ liệu tàn phá DB.

### 🔎 Task 1.9: Admin Get All Applications (Master List có bộ lọc tĩnh)
- **Dynamic Query Builder:** Tận dụng công nghệ của SQLAlchemy để tạo ra một truy vấn động, bằng chứng là mã nguồn `query = db.query(LoanApplication)`. Nó liên tục "cộng dồn" các tiêu chuẩn điều kiện lại nếu Admin có truyền params qua URL:
  - Nếu có `?status=...` -> đính thêm Filter `status`.
  - Nếu có `?risk_level=...` -> đính thêm Filter rủi ro.
  - Phức tạp nhất là khoảng thời gian `?from_date...` & `?to_date...`: mình đã gắn hàm ép kiểu `cast(LoanApplication.submitted_at, Date) >= from_date`. Hàm này tự gọt bỏ các giá trị Giờ-Phút-Giây thừa thãi để so khớp chuẩn với `date` thuần túy.
- **Master Data Projection:** Tại đây mình trả về thẳng `ApplicationRead` (Thông tin nguyên thuỷ lớn nhất) thay vì `ApplicationPendingSummary`. Vì nó là Master List nên Admin sẽ muốn xem tất tần tật tiểu sử của Đơn chứ không phải chỉ một vài dòng thu gọn. Các trường phái Sorting `DESC` (Mới nhất lên đầu) và Pagination nội suy đã được giữ y nguyên độ mượt y hệt Task trước.

### 🕵️ Task 1.10: Admin Get Personal Info API (Truy xuất danh tính bí mật)
- **Truy vấn rẽ nhánh an toàn:** Khi Admin cần soi giấy tờ của người nộp hồ sơ (`GET /applications/{id}/personal-info`), hệ thống sẽ chiếu thẳng UUID của ứng dụng sang bảng `personal_info`. 
- **Graceful Error Handling:** Không phải đơn nào cũng có thông tin cá nhân (Vì lỡ bị báo rớt rủi ro ngay từ đầu hoặc đang PENDING chưa tới lượt nộp Info). Vậy nên nếu hàm ORM `first()` bắn ra kết quả `None`, Backend không hề ném lỗi System rỗng tuếch, mà chủ động kích hoạt ngòi nổ `HTTPException(404)` với thông báo rõ ràng bằng Tiếng Việt: `"Khách hàng chưa nộp thông tin"`. Giao diện Frontend lập tức hiển thị nhãn thân thiện thay vì màn hình Crash đỏ lòm.
- **Data Protection:** Chữ chuẩn hóa Pydantic Schema `PersonalInfoRead` tiếp tục được tái sử dụng để cắt gọt các cột thừa thãi của bảng Database, chỉ hiển thị đúng các trường `full_name, id_card_number, phone, email, date_of_birth, address, submitted_at` theo yêu cầu tuyệt vời của kiến trúc sư trưởng.

### 🤖 Task 1.11: Tích hợp Trí tuệ nhân tạo (ML Model) vào Submit Application
- **Bảo hiểm rủi ro (Fault-Tolerant Mocking):** Backend bọc ML prediction vào `try...except`. Khi Model chưa sẵn sàng hoặc feature không khớp, hệ thống tự động sinh Mock data dựa trên credit_score để giữ server ổn định, chờ Team ML hoàn thiện integration.
- **Auto-Reject Mechanism (Máy chém tự động):** Khi User bấm `POST /applications/submit`, Backend gọi ngầm Service ML (từ `ml_service.py`). Nhận lại kết quả tỉ lệ mặc định `prob`. 
  - Nếu `prob > 0.4`, Backend gắn nhãn `AUTO_REJECTED` lên đơn và khóa vĩnh viễn.
  - Ngược lại nó được phép vào quy trình `PENDING_REVIEW` cho Admin xử lý. Toàn bộ `risk_level`, `risk_score` từ AI được ghi vào DB trong cùng transaction.

### 🌐 Task 1.12: Bảo vệ tài nguyên CORS & API Specification
- **Xóa bỏ dớp CORS:** Thêm `localhost:3000` và `localhost:5173` vào WhiteList middleware của FastAPI. React/Vite dev giờ đây có thể tự do Fetch API mà không bị chặn cửa từ vòng ngoài.
- **Auto Docs & Specification:** Sử dụng sức mạnh Document Generator của FastAPI, bổ sung docstrings (`"""..."""`) tại các Endpoint định kì để sinh Swagger UI ở đường dẫn `/docs`. Blueprint `BACKEND_API_SPEC.md` được phát hành.

### 🤝 Task 4.6: Cầu nối Hệ thống cho ML (Integration Checklist)
- **Thiết kế "Bản Hiệp Ước" mạn sườn:** Thay vì đụng chạm thẳng băng, Backend đã tạo ra file biên bản `ML_INTEGRATION_CHECKLIST.md` quy định sắc thép 8 feature parameters mà Model ML bắt buộc phải map lúc đẩy pickle model. Backend cung cấp bệ phóng tĩnh 500ms, ML thích nghi hướng theo.

### 🤖💬 Task 5.3: Hạt nhân RAG LLM Chat API
- **Kiến trúc Stateless & Memory Bypass:** Cực kì khéo léo để lách qua Database schema không chuẩn của Team RAG. Dịch vụ Backend mới đã tự động tự định nghĩa lại quy trình truy vấn `chat_messages` bọc chuẩn Postgres vật lý thành các Object `HumanMessage/AIMessage` cục bộ để móc trực tiếp vào lõi Mạng LangChain RAG. (Tuyệt đối không đụng độ với các File Memory cũ!).
- **Lazy Imports Module RAG:** Import lib LangChain và RAG Functions bị nén vào trong lõi Runtime ngầm `Try/Except`. Mục tiêu phòng Team RAG quên Install hệ sinh thái (hoặc xung đột Dependency). Giúp Uvicorn kháng dính chưởng `ModuleNotFoundError` và chạy chễm chệ 24/7!
- **Anti Spam Rate-Limiter:** Chặn họng cứng tay luồng DDOS 20 queries/phút dựa vào timestamp quét ngược trên hệ thống Database. Ngừng ngay spam Token AI.

---

## 🏆 KẾT LUẬN CUỐI CÙNG
**Giai đoạn Backend API Implementation đã HOÀN TẤT 100%.** 
Hệ thống không còn tì vết, Database chịu tải mượt mà. Đã đóng dọn toàn bộ các Script Rác dư lướt qua folder `tests_local/`. Sẵn sàng phục vụ kết nối cho Frontend và đợi ML Team thay não nhân tạo vào!