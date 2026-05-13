# TÀI LIỆU TỔNG QUAN HỆ THỐNG CREDITINTEL (OVERALL DOCUMENTATION)

## 1. Giới thiệu dự án (Project Overview)
**CreditIntel** là một hệ thống toàn diện kết hợp giữa Data Engineering (Kỹ thuật dữ liệu), Machine Learning (Học máy) và Web Application (Ứng dụng Web) phục vụ mục đích quản lý rủi ro danh mục cho vay và dự đoán rủi ro vỡ nợ tín dụng. Hệ thống được xây dựng ban đầu dựa trên tập dữ liệu Prosper Loan Dataset (~113K khoản vay, 2005-2014) và đang được phát triển thành một nền tảng Web cho phép khách hàng đăng ký vay và Admin quản lý/xét duyệt.

**Mục tiêu cốt lõi:**
- Chuẩn hóa quy trình xử lý dữ liệu từ dạng thô đến phân tích.
- Cung cấp mô hình Học máy để đánh giá rủi ro (Risk Assessment) và tự động hóa các quyết định cho vay.
- Giao diện người dùng cho cả Khách hàng (Customer) và Quản trị viên (Admin) để thực hiện quy trình xét duyệt khoản vay.
- Tích hợp Chatbot RAG (Retrieval-Augmented Generation) để hỗ trợ và tư vấn tài chính cho khách hàng một cách thông minh.

---

## 2. Kiến trúc hệ thống (System Architecture)

Kiến trúc hệ thống bao gồm 4 thành phần chính: **Data Lakehouse Pipeline**, **Machine Learning Engine**, **Backend API**, và **Frontend Web App**.

### 2.1. Cấu trúc cơ sở dữ liệu & Data Pipeline (Data Lakehouse)
Hệ thống sử dụng **PostgreSQL** (Supabase) và kiến trúc 4 lớp dữ liệu:
*   **Bronze Layer (`bronze.raw_loans`):** Lưu trữ dữ liệu thô (raw data) được load trực tiếp từ file CSV (Prosper Loan Data) vào database thông qua pandas & SQLAlchemy.
*   **Silver Layer (`silver.prosper_loans_cleansed`):** Dữ liệu đã được làm sạch, xử lý missing values, chuẩn hóa các định dạng, khử trùng lặp và tạo trường target `is_default` (phục vụ cho downstream).
*   **Core Layer (`core.*`):** Cấu trúc schema chuẩn hóa nghiệp vụ (Business Normalized), bao gồm các bảng: `loans`, `borrowers`, `credit_profiles`, `risk_assessment` và các bảng dimensions (ví dụ: `dim_employment_status`, `dim_listing_category`). Đây là lõi lưu trữ dữ liệu chính thức.
*   **Gold Layer (`gold.loan_features_v1` & Analytical Views):** Lớp dữ liệu phục vụ phân tích. Chứa các tính năng (feature engineering) đã được chế biến chuyên sâu để đưa vào mô hình Machine Learning và các View (như `vw_default_rate_by_term`, `vw_risk_by_employment`) dùng để hiển thị trên Admin Dashboard.

### 2.2. Backend API (FastAPI)
Được thiết kế theo kiến trúc RESTful API.
*   **Authentication & Authorization:** Hệ thống phân quyền JWT (Customer & Admin).
*   **Routers:** `/auth`, `/applications` (xử lý đơn vay của khách), `/admin` (quản lý, dashboard stats, xét duyệt đơn), `/credit-score`, `/chat`.
*   **Database ORM:** Tương tác với PostgreSQL thông qua SQLAlchemy.

### 2.3. Trí tuệ nhân tạo (Machine Learning & RAG)
*   **Machine Learning (Dự đoán vỡ nợ):** Sử dụng LightGBM từ `ml/retrain_customer_model.py` để dự đoán xác suất vỡ nợ (`probability_of_default`). Phân loại thành 3 mức rủi ro:
    *   `Low` (Thấp): Xác suất < 0.2 (Đề xuất vay lên tới 15,000$ / 36 tháng).
    *   `Medium` (Trung bình): 0.2 - 0.4 (Đề xuất 8,000$ / 24 tháng).
    *   `High` (Cao): > 0.4 (Từ chối tự động - Auto Rejected, hoặc chỉ vay tối đa 3,000$ / 12 tháng).
*   **RAG Chatbot:** Xây dựng bằng `LangChain`, nhúng tài liệu (Embeddings) lưu trong vector database `Pinecone` (dùng data dictionary và các chính sách của CreditIntel). Sử dụng LLM (OpenAI/Gemini qua OpenRouter) để sinh câu trả lời tư vấn cho khách hàng dựa trên lịch sử khoản vay (user context) và tài liệu nội bộ.

### 2.4. Frontend Web App (React + Vite)
*   Sử dụng ReactJS, Vite, Tailwind CSS.
*   Tách biệt rõ ràng các luồng trang của **Customer** (`/apply`, `/dashboard`, `/submit-info`, `/chat`) và **Admin** (`/admin/dashboard`, `/admin/pending`, chi tiết đơn, thông tin cá nhân).

---

## 3. Cấu trúc thư mục dự án (Directory Structure)

*   `backend/`: Source code của FastAPI, bao gồm `api/routers`, `core/config`, `db/session`, `models/` (Pydantic schemas), `services/` (Business logic), và thư mục `rag/` (cho logic Chatbot).
*   `config/`: Chứa file `settings.yaml` (Cấu hình kết nối DB, API keys, đường dẫn raw data...).
*   `data/`: Chứa dữ liệu thô (ví dụ: `raw/prosperLoanData.csv`).
*   `database/`: Các file script SQL thiết lập cơ sở dữ liệu (`init_database.sql`, `init_core.sql`, `transform_silver.sql`, `transform_core.sql`, `transform_gold.sql`).
*   `docs/`: Chứa tài liệu dự án, bao gồm `data_dictionary/` (Giải thích các schema), `ml_md/`, và `overall/` (chứa các kế hoạch phát triển).
*   `frontend/`: Source code của React application (`src/components/`, `src/pages/`, `src/services/`...).
*   `ml/`: Hai script model được hỗ trợ: `retrain_customer_model.py` cho risk prediction và `train_scorecard.py` cho credit scorecard; artifacts nằm trong `models/`.
*   `ml_service/`: Thư mục chứa các luồng ETL pipeline (`etl/load_bronze.py`, `etl/etl_silver.py`, `etl/etl_core.py`, `etl/etl_gold.py`) và phiên bản app cũ bằng Streamlit (`app.py`, `dashboard.py`).
*   `utils/`: Thư mục tiện ích chung (vd: `db_connection.py`).

---

## 4. Các Module cốt lõi và Chức năng (Modules & Functions)

### 4.1. Module ETL (Kéo, Biến đổi & Nạp dữ liệu)
- **`load_bronze.py`:** Đọc dữ liệu từ file CSV, nạp toàn bộ vào bảng `bronze.raw_loans`.
- **`etl_silver.py`:** Loại bỏ giá trị Null/Duplicate, chuẩn hóa format (ngày tháng, boolean), tính toán các field cơ bản và nạp vào `silver.prosper_loans_cleansed`.
- **`etl_core.py`:** Transform từ dữ liệu dạng phẳng (flat) ở Silver thành các bảng chuẩn hóa (Normalization) trong Schema `core`.
- **`etl_gold.py`:** Thực hiện Feature Engineering (Tạo các feature mới như phân cụm điểm tín dụng, tỉ lệ nợ/thu nhập, tính toán biến ngụy tạo (dummy) từ Categorical) để đẩy vào `gold.loan_features_v1`.

### 4.2. Module Machine Learning (Dự đoán)
Hệ thống sử dụng hai Model Artifacts để phục vụ hai mục đích khác nhau:
1.  **`customer_risk_model.pkl` (Training bởi `retrain_customer_model.py`):** LightGBM risk model dùng cho quyết định rủi ro khi khách nộp đơn. Backend gọi qua `backend/services/ml_service.py`.
2.  **`scorecard_model.pkl` (Training bởi `train_scorecard.py`):** Logistic Regression scorecard dùng cho API `/credit-score`. Backend gọi qua `backend/services/credit_score_service.py`.

### 4.3. Module RAG Chatbot (Hỗ trợ Khách hàng)
- **`rag/ingest.py`:** Chạy 1 lần để nhúng (embed) các tài liệu markdown (`docs/data_dictionary/`) thành Vector và lưu lên Pinecone.
- **`rag/chain.py`:** Định nghĩa `ConversationalRetrievalChain` của Langchain, sử dụng LLM model (`gemini-flash-1.5` hoặc `OpenAI`) để truy xuất ngữ cảnh (retriever).
- **`services/chat_service.py`:** Lưu trữ lịch sử hội thoại vào PostgreSQL (bảng `chat_messages` và `chat_sessions`), tổng hợp thông tin khoản vay hiện tại của khách hàng (user_context) đưa vào prompt để Chatbot đưa ra những lời khuyên cá nhân hóa nhất.

### 4.4. Module Quản lý Luồng đơn vay (Application Service)
Quy trình trạng thái (State machine) của một đơn vay:
1.  **Submit Form:** Khách hàng nộp đơn. Model ML chạy dự đoán ngay lập tức.
2.  **ML Quyết định:**
    *   Nếu P(Default) > 0.4: Chuyển trạng thái `AUTO_REJECTED` (Hệ thống tự động từ chối).
    *   Nếu P(Default) <= 0.4: Chuyển trạng thái `PENDING_REVIEW` (Chờ Admin duyệt).
3.  **Admin Xét duyệt:** Admin xem đơn, xem các điểm rủi ro và quyết định:
    *   Từ chối: `ADMIN_REJECTED`.
    *   Đồng ý: `AWAITING_INFO` (Chờ khách hàng bổ sung thông tin định danh: CCCD, SĐT).
4.  **Hoàn thành:** Khách hàng nộp thông tin định danh -> `INFO_SUBMITTED`.

---

## 5. Danh sách Công nghệ & Thư viện (Tech Stack & Libraries)

*   **Ngôn ngữ lập trình:** Python 3.x, JavaScript (React)
*   **Data Processing & ETL:** `pandas`, `numpy`, `SQLAlchemy`, `psycopg2-binary`.
*   **Machine Learning:** `LightGBM`, `scikit-learn` (LogisticRegression, StandardScaler, OrdinalEncoder, Metrics), `joblib` (Lưu mô hình).
*   **Backend Framework:** `FastAPI`, `pydantic` (Data Validation), `uvicorn`, `python-jose` (JWT), `passlib` (Bcrypt Hash).
*   **LLM & RAG:** `langchain`, `langchain-openai`, `langchain-pinecone`, `pinecone-client`.
*   **Database:** `PostgreSQL` (hosted trên Supabase).
*   **Frontend:** `React` (v18), `Vite`, `Tailwind CSS`, `React Router`, React Hooks.
*   **Công cụ khác:** `PyYAML` (Đọc config), Git.

---

## 6. Thông số Input/Output (I/O Specifications)

### 6.1. Input (Dữ liệu đầu vào từ Khách hàng nộp đơn)
- `monthly_income` (Thu nhập hàng tháng - Numeric)
- `loan_amount` (Số tiền muốn vay - Numeric)
- `term` (Kỳ hạn - 12, 36, hoặc 60 tháng)
- `employment_status` (Tình trạng việc làm - Employed, Self-employed, Retired, Not employed, Other)
- `dti` (Tỉ lệ nợ trên thu nhập - Numeric)
- `is_homeowner` (Sở hữu nhà - Boolean)
- `listing_category` (Mục đích vay - Categorical/Numeric ID)
- `credit_score` (Điểm tín dụng tự khai báo - Numeric)

### 6.2. Output (Kết quả từ Machine Learning)
- `probability_of_default` (Xác suất vỡ nợ: 0.0 -> 1.0)
- `risk_level` (Mức độ rủi ro: Low, Medium, High)
- `risk_score_internal` (Điểm tín dụng nội bộ: 0 - 100, quy đổi từ xác suất)
- `auto_decision` (Quyết định tự động: `AUTO_REJECTED` hoặc `PENDING_REVIEW`)
- `recommended_amount` & `recommended_term` (Khuyến nghị vay thông minh).

---

## 7. Kết quả & Đánh giá hiệu năng Model (Results)
Mô hình `RandomForestClassifier` (với tính năng class_weight='balanced') đạt được những chỉ số đánh giá khả quan trên tập kiểm thử (Test Set) của dữ liệu Prosper (Historical Data):
*   **ROC-AUC Score:** Khoảng 0.864 (Rất tốt trong việc phân tách hồ sơ vỡ nợ và không vỡ nợ).
*   **Tỉ lệ bao phủ (Recall cho Default class):** Lên tới ~76%, có nghĩa là hệ thống nhận diện được phần lớn hồ sơ thực sự có rủi ro vỡ nợ.
*   **Khả năng mở rộng (Scalability):** Với việc triển khai FastAPI và PostgreSQL (Supabase), hệ thống có khả năng đáp ứng tải tốt cho hàng nghìn đơn vay song song. RAG Chatbot hỗ trợ phản hồi trong <2s với Pinecone index.

---
*(Tài liệu này đóng vai trò là "Sổ tay" kiến trúc kỹ thuật dành cho toàn bộ dự án CreditIntel)*
