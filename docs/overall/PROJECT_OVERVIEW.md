# Tổng quan Dự án CreditIntel: Hệ thống Quản lý Rủi ro Danh mục Cho vay

## Giới thiệu Dự án

CreditIntel là một dự án Data Engineering và Machine Learning toàn diện, được phát triển như một phần của khóa học quản lý cơ sở dữ liệu. Dự án tập trung vào việc xây dựng hệ thống giám sát danh mục cho vay và dự đoán rủi ro vỡ nợ tín dụng, sử dụng dữ liệu từ Prosper Loan Dataset. Hệ thống giúp các tổ chức tài chính đánh giá và quản lý rủi ro một cách hiệu quả, từ việc xử lý dữ liệu thô đến việc đưa ra quyết định dựa trên AI.

## Chức năng Chính

### 1. ETL Pipeline
- **Xử lý dữ liệu đa lớp:** Từ dữ liệu thô (Bronze) đến dữ liệu sạch (Silver), chuẩn hóa (Core) và sẵn sàng cho phân tích (Gold).
- **Tích hợp dữ liệu:** Kết hợp thông tin từ nhiều nguồn để tạo ra cái nhìn toàn diện về khách hàng và khoản vay.
- **Tự động hóa quy trình:** Scripts Python để load, transform và load dữ liệu vào PostgreSQL.

### 2. Dashboard Rủi ro
- **Trực quan hóa tương tác:** Sử dụng Streamlit và Plotly để hiển thị sức khỏe danh mục, tỷ lệ vỡ nợ, phân tích theo thu nhập và các chỉ số rủi ro khác.
- **Phân tích thời gian thực:** Cập nhật dữ liệu từ database để cung cấp insights kịp thời cho người dùng.

### 3. AI Dự đoán Rủi ro
- **Risk model:** LightGBM train bởi `machinelearning/ml/retrain_customer_model.py`, artifact `customer_risk_model.pkl`.
- **Scorecard:** Logistic Regression train bởi `machinelearning/ml/train_scorecard.py`, artifact `scorecard_model.pkl`.
- **Business Rule Engine:** Áp dụng ngưỡng risk để quyết định `AUTO_REJECTED` hoặc `PENDING_REVIEW`.
- **Đánh giá thời gian thực:** Backend service load artifact bằng joblib, xử lý đơn vay mới và đưa ra khuyến nghị về số tiền/kỳ hạn.

### 4. Quản lý Cơ sở Dữ liệu
- **Schema thiết kế:** Bao gồm các bảng dimension (employment_status, occupation, v.v.) và fact tables (borrowers, loans, credit_profiles).
- **Risk Assessment:** Bảng core.risk_assessment lưu trữ kết quả đánh giá rủi ro từ ML model.

## Cấu trúc Dự án

Dự án được tổ chức theo kiến trúc modular MVC-lite để dễ bảo trì và mở rộng:

### Kiến trúc Dữ liệu (Data Lakehouse)
- **Bronze Layer:** Dữ liệu thô từ CSV (prosperLoanData.csv), chưa xử lý.
- **Silver Layer:** Dữ liệu đã làm sạch, loại bỏ trùng lặp, chuẩn hóa định dạng (bảng silver.prosper_loans_cleansed).
- **Core Layer:** CSDL quan hệ với các thực thể nghiệp vụ, giảm lặp dữ liệu và thể hiện quan hệ.
- **Gold Layer:** Dữ liệu tổng hợp cho ML và dashboard, với feature engineering (bảng gold.loan_features_v1).

### Cấu trúc Thư mục
- `backend/`: FastAPI API, auth, services, schemas, models, RAG runtime.
- `frontend/`: React/Vite UI.
- `machinelearning/etl/`: Scripts ETL cho từng lớp (load_bronze.py, etl_silver.py, etl_gold.py).
- `machinelearning/ml/`: Hai script model được hỗ trợ: `retrain_customer_model.py`, `train_scorecard.py`, và artifacts trong `models/`.
- `machinelearning/database/`: SQL transforms cho Home Credit ETL.
- `machinelearning/config/`: Cấu hình ETL/DuckDB.
- `machinelearning/data/`: Dữ liệu thô và DuckDB local.
- `machinelearning/notebooks/`: Notebook EDA/training phụ trợ.
- `machinelearning/utils/`: Utilities như db_connection.py.
- `docs/`: Tài liệu chi tiết về data dictionary và ML.

## Các Hoạt động Chính

### 1. Thu thập và Xử lý Dữ liệu
- Load dữ liệu từ CSV vào Bronze.
- Làm sạch và chuẩn hóa ở Silver.
- Transform thành schema quan hệ ở Core.
- Feature engineering cho Gold.

### 2. Training Mô hình ML
- Sử dụng dữ liệu từ Gold để train LightGBM risk model.
- Sử dụng dữ liệu từ Gold để train Logistic Regression scorecard.
- Lưu artifacts vào `customer_risk_model.pkl` và `scorecard_model.pkl`.

### 3. Dự đoán và Đánh giá
- Nhận input từ người dùng qua UI.
- Chạy prediction và lưu kết quả vào core.risk_assessment.
- Hiển thị kết quả với giải thích.

### 4. Giám sát và Báo cáo
- Dashboard cập nhật từ database.
- Phân tích rủi ro theo các chiều: thời gian, thu nhập, trạng thái vay.

## Điểm Mạnh

- **Kiến trúc Scalable:** Sử dụng data lakehouse architecture, dễ mở rộng cho dữ liệu lớn.
- **Tích hợp End-to-End:** Từ ETL đến ML và UI, tất cả trong một hệ thống.
- **Minh bạch AI:** Explainable AI giúp người dùng hiểu quyết định của model.
- **Dễ sử dụng:** Giao diện Streamlit đơn giản, hướng dẫn cài đặt rõ ràng.
- **Modular Design:** MVC-lite giúp code dễ maintain và test.
- **Business Value:** Giúp giảm rủi ro vỡ nợ, tối ưu hóa danh mục cho vay.

## Công nghệ Sử dụng

### Ngôn ngữ và Framework
- **Python 3.x:** Ngôn ngữ chính cho tất cả scripts và ứng dụng.
- **Streamlit:** Framework web đơn giản cho dashboard và UI.

### Cơ sở Dữ liệu
- **PostgreSQL:** RDBMS cho lưu trữ dữ liệu structured.
- **SQLAlchemy:** ORM để tương tác với database từ Python.

### Data Science và ML
- **Pandas:** Xử lý và phân tích dữ liệu.
- **Scikit-learn:** Thư viện ML cho Random Forest và preprocessing.
- **Plotly:** Trực quan hóa dữ liệu tương tác.

### Công cụ Khác
- **Virtualenv:** Quản lý môi trường Python.
- **YAML:** Cấu hình settings.
- **Git:** Version control.

## Cách Triển khai

1. **Chuẩn bị môi trường:** Clone repo, tạo venv, cài dependencies.
2. **Thiết lập DB:** Chạy scripts SQL để tạo schema.
3. **Chạy ETL:** Load và transform dữ liệu qua các lớp.
4. **Train Model:** Chạy `python -m machinelearning.ml.retrain_customer_model` và `python -m machinelearning.ml.train_scorecard`.
5. **Khởi chạy App:** Chạy FastAPI backend và React frontend.

Dự án này không chỉ là một sản phẩm kỹ thuật mà còn là minh chứng cho việc áp dụng Data Engineering và ML vào bài toán thực tế trong lĩnh vực tài chính.
