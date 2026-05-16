# Chi tiết Modules, Files và Folders trong Dự án CreditIntel

Tài liệu này mô tả chi tiết từng module, file và folder trong dự án CreditIntel, bao gồm chức năng, mục đích và cách thức hoạt động.

## Cấu trúc Tổng quan

Dự án được tổ chức theo kiến trúc modular với các thư mục chính:
- **backend/:** FastAPI API, services, schemas, models, RAG runtime
- **frontend/:** React/Vite UI
- **machinelearning/:** ETL, SQL transforms, local data/config, notebooks, ML training
- **docs/:** Tài liệu chi tiết

## Root Files

### README.md
- **Chức năng:** Tài liệu giới thiệu dự án.
- **Mục đích:** Mô tả tổng quan, cài đặt và sử dụng.
- **Cách hoạt động:** Markdown file tĩnh.

### requirements.txt
- **Chức năng:** File aggregate cho môi trường Python đầy đủ.
- **Mục đích:** Cài cả backend và ML/ETL khi cần làm việc toàn repo.
- **Cách hoạt động:** Trỏ tới `backend/requirements.txt` và `machinelearning/requirements.txt`; khi chỉ chạy một layer thì cài file requirements của layer đó.

## Thư mục machinelearning/config/

### settings.yaml
- **Chức năng:** File cấu hình hệ thống.
- **Mục đích:** Lưu trữ thông tin kết nối database, API keys, v.v.
- **Cách hoạt động:** Đọc bởi các module Python sử dụng PyYAML.
- **Ví dụ:** host, port, username, password cho PostgreSQL.

## Thư mục machinelearning/data/

### raw/prosperLoanData.csv
- **Chức năng:** Dữ liệu thô nguồn.
- **Mục đích:** Nguồn dữ liệu chính cho ETL pipeline.
- **Cách hoạt động:** CSV file chứa thông tin khoản vay từ Prosper.
- **Cấu trúc:** Các cột như listing_key, borrower_rate, loan_status, v.v.

## Thư mục machinelearning/database/

### transform_silver_homecredit.sql
- **Chức năng:** Transform Bronze → Silver cho Home Credit.
- **Mục đích:** Tạo bảng `silver.home_credit_cleansed` cho ETL/model hiện tại.
- **Cách hoạt động:** Đọc `bronze.home_credit_raw`, chuẩn hóa loan, income, credit score, demographic và employment fields.

### transform_gold_homecredit.sql
- **Chức năng:** Transform Silver → Gold cho Home Credit.
- **Mục đích:** Tạo bảng `gold.hc_features_v1` cho `customer_risk_model.pkl` và `scorecard_model.pkl`.
- **Cách hoạt động:** Join thêm previous application/bureau aggregates và tạo feature engineering cho training.

## Thư mục docs/

### overall/
- **Chức năng:** Tài liệu tổng quan dự án, kiến trúc app, module/file map, admin guide và lịch sử rebuild.
- **Mục đích:** Giúp người đọc nắm bối cảnh hệ thống end-to-end trước khi đi vào ML hoặc RAG.
- **File chính:** `overall.md`, `PROJECT_OVERVIEW.md`, `APP_DEVELOPMENT_PLAN.md`, `MODULES_AND_FILES.md`, `ADMIN_GUIDE.md`, `REBUILD_2026.md`.

### ml/
- **Chức năng:** Tài liệu dataset, feature, model, scorecard và tích hợp ML với backend/frontend.
- **Mục đích:** Gom toàn bộ nội dung phục vụ ETL/ML training, model contract và credit scoring.
- **File chính:** `ML_FEATURES.md`, `02_dataset_lua_chon.html`, `ml_backend_frontend_integration.md`, `2026-05-12-credit-score.md`.

### rag/
- **Chức năng:** Tài liệu thiết kế, context requirement và đánh giá readiness cho RAG chatbot.
- **Mục đích:** Gom toàn bộ nội dung liên quan chatbot, knowledge base, context builder và tư vấn khoản vay.
- **File chính:** `RAG_chatbot_plan.md`, `rag_ml_context_requirements.md`, `rag_system_overview.md`, `10_danh_gia_model_rag.html`.

## Thư mục machinelearning/ml/

### retrain_customer_model.py
- **Chức năng:** Train LightGBM risk model.
- **Mục đích:** Sinh artifact `machinelearning/ml/models/customer_risk_model.pkl` cho backend xét rủi ro khi khách nộp đơn.
- **Cách hoạt động:** Đọc `gold.hc_features_v1`, train pipeline LightGBM, lưu metadata contract (`feature_cols`, defaults, thresholds, model_version).
- **Dependencies:** LightGBM, scikit-learn, pandas, joblib.

### train_scorecard.py
- **Chức năng:** Train Logistic Regression scorecard.
- **Mục đích:** Sinh artifact `machinelearning/ml/models/scorecard_model.pkl` cho API credit score.
- **Cách hoạt động:** Đọc `gold.hc_features_v1`, train scorecard, lưu FICO params và contribution table.
- **Dependencies:** scikit-learn, pandas, joblib.

### models/customer_risk_model.pkl
- **Chức năng:** Artifact LightGBM risk prediction.
- **Mục đích:** Được load bởi `backend/services/ml_service.py`.

### models/scorecard_model.pkl
- **Chức năng:** Artifact LR scorecard.
- **Mục đích:** Được load bởi `backend/services/credit_score_service.py`.

## Thư mục machinelearning/utils/

### db_connection.py
- **Chức năng:** Utility kết nối database.
- **Mục đích:** Cung cấp connection object cho SQLAlchemy.
- **Cách hoạt động:** Đọc settings.yaml, tạo engine.
- **Dependencies:** SQLAlchemy, PyYAML.

## Luồng Hoạt động Tổng thể

1. **ETL Flow:** `machinelearning/etl/load_bronze.py` → `machinelearning/etl/etl_silver.py` → `machinelearning/etl/etl_gold.py`
2. **ML Flow:** `retrain_customer_model.py` → backend risk inference; `train_scorecard.py` → backend credit score inference
3. **UI Flow:** app.py → dashboard.py + prediction_ui.py
4. **Config:** settings.yaml cho tất cả connections
5. **Docs:** docs/ cho reference

Tất cả modules được thiết kế modular để dễ test và maintain.
