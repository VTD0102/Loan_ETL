# Chi tiết Modules, Files và Folders trong Dự án CreditIntel

Tài liệu này mô tả chi tiết từng module, file và folder trong dự án CreditIntel, bao gồm chức năng, mục đích và cách thức hoạt động.

## Cấu trúc Tổng quan

Dự án được tổ chức theo kiến trúc modular với các thư mục chính:
- **Root Files:** Các file Python chính và cấu hình
- **config/:** Cấu hình hệ thống
- **data/:** Dữ liệu thô và xử lý
- **database/:** Scripts SQL
- **docs/:** Tài liệu chi tiết
- **ml/:** Machine Learning
- **utils/:** Utilities hỗ trợ

## Root Files

### app.py
- **Chức năng:** Ứng dụng chính của hệ thống, tích hợp Streamlit.
- **Mục đích:** Khởi chạy dashboard và prediction UI, là entry point chính.
- **Cách hoạt động:** Import các module như dashboard.py và prediction_ui.py, chạy Streamlit app.
- **Dependencies:** Streamlit, các module nội bộ.

### dashboard.py
- **Chức năng:** Module trực quan hóa dữ liệu.
- **Mục đích:** Tạo dashboard tương tác hiển thị sức khỏe danh mục, tỷ lệ vỡ nợ, phân tích rủi ro.
- **Cách hoạt động:** Sử dụng Plotly để vẽ biểu đồ, query dữ liệu từ database qua SQLAlchemy.
- **Dependencies:** Plotly, Pandas, SQLAlchemy.

### data_handler.py
- **Chức năng:** Xử lý dữ liệu chung.
- **Mục đích:** Cung cấp các hàm utility cho việc load, clean và transform dữ liệu.
- **Cách hoạt động:** Chứa các hàm như read_csv, data_cleaning, v.v.
- **Dependencies:** Pandas, NumPy.

### ml_service/etl/etl_core.py
- **Chức năng:** ETL cho Core layer.
- **Mục đích:** Transform dữ liệu từ Silver thành schema quan hệ (borrowers, loans, credit_profiles).
- **Cách hoạt động:** Sử dụng SQLAlchemy để insert dữ liệu vào các bảng dimension và fact.
- **Dependencies:** SQLAlchemy, Pandas.

### ml_service/etl/etl_gold.py
- **Chức năng:** ETL cho Gold layer.
- **Mục đích:** Tạo bảng gold.loan_features_v1 cho ML và dashboard.
- **Cách hoạt động:** Join dữ liệu từ Core và Silver, thực hiện feature engineering.
- **Dependencies:** SQLAlchemy, Pandas, Scikit-learn (cho preprocessing).

### ml_service/etl/etl_silver.py
- **Chức năng:** ETL cho Silver layer.
- **Mục đích:** Làm sạch và chuẩn hóa dữ liệu từ Bronze, tạo bảng silver.prosper_loans_cleansed.
- **Cách hoạt động:** Loại bỏ trùng lặp, xử lý missing values, chuẩn hóa định dạng.
- **Dependencies:** Pandas, NumPy.

### ml_service/etl/load_bronze.py
- **Chức năng:** Load dữ liệu vào Bronze layer.
- **Mục đích:** Import dữ liệu thô từ CSV vào database.
- **Cách hoạt động:** Đọc prosperLoanData.csv và insert vào bảng bronze.
- **Dependencies:** Pandas, SQLAlchemy.

### frontend/src/pages/customer/Apply/index.jsx
- **Chức năng:** Giao diện nộp đơn vay trên React.
- **Mục đích:** Cho phép người dùng nhập thông tin vay, bao gồm phần thông tin bổ sung optional cho mô hình.
- **Cách hoạt động:** Gửi payload đến backend `/applications/submit`; backend gọi `services/ml_service.py` để chạy artifact từ `retrain_customer_model.py`.
- **Dependencies:** React, react-hook-form, FastAPI backend.

### README.md
- **Chức năng:** Tài liệu giới thiệu dự án.
- **Mục đích:** Mô tả tổng quan, cài đặt và sử dụng.
- **Cách hoạt động:** Markdown file tĩnh.

### requirements.txt
- **Chức năng:** Danh sách dependencies Python.
- **Mục đích:** Cài đặt các thư viện cần thiết.
- **Cách hoạt động:** File text với tên package và version.

## Thư mục config/

### settings.yaml
- **Chức năng:** File cấu hình hệ thống.
- **Mục đích:** Lưu trữ thông tin kết nối database, API keys, v.v.
- **Cách hoạt động:** Đọc bởi các module Python sử dụng PyYAML.
- **Ví dụ:** host, port, username, password cho PostgreSQL.

## Thư mục data/

### raw/prosperLoanData.csv
- **Chức năng:** Dữ liệu thô nguồn.
- **Mục đích:** Nguồn dữ liệu chính cho ETL pipeline.
- **Cách hoạt động:** CSV file chứa thông tin khoản vay từ Prosper.
- **Cấu trúc:** Các cột như listing_key, borrower_rate, loan_status, v.v.

## Thư mục database/

### init_core.sql
- **Chức năng:** Khởi tạo schema Core.
- **Mục đích:** Tạo các bảng dimension và fact trong schema core.
- **Cách hoạt động:** SQL script chạy trên PostgreSQL.

### init_database.sql
- **Chức năng:** Khởi tạo database và schema.
- **Mục đích:** Tạo database, user và các schema (bronze, silver, core, gold).
- **Cách hoạt động:** SQL script nền tảng.

### transform_core.sql
- **Chức năng:** Transform queries cho Core.
- **Mục đích:** Các câu SQL để populate bảng từ Silver.
- **Cách hoạt động:** Chứa INSERT/UPDATE statements.

### transform_gold.sql
- **Chức năng:** Transform queries cho Gold.
- **Mục đích:** Tạo bảng gold.loan_features_v1.
- **Cách hoạt động:** Complex JOIN và aggregation.

### transform_silver.sql
- **Chức năng:** Transform queries cho Silver.
- **Mục đích:** Clean và chuẩn hóa dữ liệu.
- **Cách hoạt động:** UPDATE và INSERT cho silver.prosper_loans_cleansed.

## Thư mục docs/

### data_dictionary/core_data_dictionary.md
- **Chức năng:** Tài liệu về schema Core.
- **Mục đích:** Mô tả chi tiết các bảng và thuộc tính trong core.
- **Cách hoạt động:** Markdown với bảng dimension và fact tables.

### data_dictionary/gold_data_dictionary.md
- **Chức năng:** Tài liệu về schema Gold.
- **Mục đích:** Mô tả gold.loan_features_v1 và analytical views.
- **Cách hoạt động:** Giải thích grain, vai trò và data dictionary.

### data_dictionary/silver_data_dictionary.md.md
- **Chức năng:** Tài liệu về schema Silver.
- **Mục đích:** Mô tả silver.prosper_loans_cleansed.
- **Cách hoạt động:** Phân nhóm thuộc tính (khóa, thời gian, trạng thái, v.v.).

### ml_md/init_core.md
- **Chức năng:** Tài liệu về bảng risk_assessment.
- **Mục đích:** Mô tả schema và cách tạo bảng core.risk_assessment.
- **Cách hoạt động:** Chứa SQL CREATE TABLE và comments.

### ml_md/ml_1.md
- **Chức năng:** Tài liệu về ML pipeline.
- **Mục đích:** Mô tả vai trò, files và actions trong ML system.
- **Cách hoạt động:** Overview về training và prediction.

## Thư mục ml/

### retrain_customer_model.py
- **Chức năng:** Train LightGBM risk model.
- **Mục đích:** Sinh artifact `ml/models/customer_risk_model.pkl` cho backend xét rủi ro khi khách nộp đơn.
- **Cách hoạt động:** Đọc `gold.hc_features_v1`, train pipeline LightGBM, lưu metadata contract (`feature_cols`, defaults, thresholds, model_version).
- **Dependencies:** LightGBM, scikit-learn, pandas, joblib.

### train_scorecard.py
- **Chức năng:** Train Logistic Regression scorecard.
- **Mục đích:** Sinh artifact `ml/models/scorecard_model.pkl` cho API credit score.
- **Cách hoạt động:** Đọc `gold.hc_features_v1`, train scorecard, lưu FICO params và contribution table.
- **Dependencies:** scikit-learn, pandas, joblib.

### models/customer_risk_model.pkl
- **Chức năng:** Artifact LightGBM risk prediction.
- **Mục đích:** Được load bởi `backend/services/ml_service.py`.

### models/scorecard_model.pkl
- **Chức năng:** Artifact LR scorecard.
- **Mục đích:** Được load bởi `backend/services/credit_score_service.py`.

## Thư mục utils/

### db_connection.py
- **Chức năng:** Utility kết nối database.
- **Mục đích:** Cung cấp connection object cho SQLAlchemy.
- **Cách hoạt động:** Đọc settings.yaml, tạo engine.
- **Dependencies:** SQLAlchemy, PyYAML.

## Luồng Hoạt động Tổng thể

1. **ETL Flow:** ml_service/etl/load_bronze.py → ml_service/etl/etl_silver.py → ml_service/etl/etl_core.py → ml_service/etl/etl_gold.py
2. **ML Flow:** `retrain_customer_model.py` → backend risk inference; `train_scorecard.py` → backend credit score inference
3. **UI Flow:** app.py → dashboard.py + prediction_ui.py
4. **Config:** settings.yaml cho tất cả connections
5. **Docs:** docs/ cho reference

Tất cả modules được thiết kế modular để dễ test và maintain.
