# CreditIntel: Hệ thống Quản lý Rủi ro Danh mục Cho vay

Dự án Data Engineering và Machine Learning toàn diện để giám sát danh mục cho vay và dự đoán rủi ro vỡ nợ tín dụng.

## 🚀 Tính năng chính
- **ETL Pipeline:** Kiến trúc đa lớp (Bronze, Silver, Core, Gold) sử dụng PostgreSQL.
- **Dashboard Rủi ro:** Trực quan hóa tương tác về sức khỏe danh mục, tỷ lệ vỡ nợ và phân tích rủi ro theo thu nhập.
- **AI Dự đoán:** Mô hình Machine Learning (Random Forest) đánh giá đơn xin vay thời gian thực với Business Rule Engine và Explainable AI (XAI).
- **Kiến trúc:** Thiết kế lại theo mô hình MVC-lite để dễ bảo trì.

## 🛠️ Công nghệ sử dụng
- **Ngôn ngữ:** Python 3.x
- **Cơ sở dữ liệu:** PostgreSQL
- **Giao diện:** Streamlit
- **Data Science:** Pandas, Scikit-learn, Plotly, SQLAlchemy
- **Môi trường:** Virtualenv

## 📊 Kiến trúc dữ liệu
Dự án sử dụng kiến trúc data lakehouse với 4 lớp:
- **Bronze:** Dữ liệu thô từ nguồn (prosperLoanData.csv)
- **Silver:** Dữ liệu đã làm sạch và chuẩn hóa (silver.prosper_loans_cleansed)
- **Core:** CSDL quan hệ nghiệp vụ với các bảng dimension và fact (borrowers, loans, credit_profiles, v.v.)
- **Gold:** Dữ liệu cho ML và dashboard (gold.loan_features_v1)

Chi tiết về schema và thuộc tính dữ liệu xem trong [md_files/data_dictionary/](md_files/data_dictionary/).

## 🤖 Hệ thống Machine Learning
- **Mô hình:** Random Forest để dự đoán xác suất vỡ nợ
- **Đánh giá rủi ro:** Tạo bảng core.risk_assessment với điểm rủi ro, mức độ rủi ro và đề xuất số tiền/kỳ hạn
- **Training:** Sử dụng dữ liệu từ gold.loan_features_v1
- **Prediction:** Đánh giá đơn vay mới thời gian thực

Chi tiết về ML pipeline xem trong [md_files/ml_md/](md_files/ml_md/).

## ⚙️ Cài đặt và Sử dụng
1. Clone repository.
2. Tạo và kích hoạt virtual environment: `python -m venv venv` & `.\venv\Scripts\activate`.
3. Cài đặt dependencies: `pip install -r requirements.txt`.
4. **Thiết lập Cơ sở dữ liệu:**
   - Mở SQL IDE (DataGrip, pgAdmin, DBeaver).
   - Chạy script `database/init_database.sql` để tạo database và schema.
   - Cập nhật `config/settings.yaml` với thông tin PostgreSQL local.
5. Chạy ETL pipeline để xử lý dữ liệu:
   - `python load_bronze.py`
   - `python etl_silver.py`
   - `python etl_gold.py`
6. Train mô hình ML: `python ml/train_model.py`.
7. Khởi chạy dashboard và app underwriting: `streamlit run app.py`.

## 📁 Cấu trúc dự án
- `app.py`: Ứng dụng chính Streamlit
- `dashboard.py`: Dashboard trực quan hóa
- `etl_*.py`: Scripts ETL cho các lớp
- `ml/`: Thư mục Machine Learning
- `database/`: Scripts SQL khởi tạo
- `md_files/`: Tài liệu về data dictionary và ML
- `config/`: Cấu hình
- `data/`: Dữ liệu thô và xử lý

## 📚 Tài liệu bổ sung
- [Data Dictionary](md_files/data_dictionary/): Mô tả chi tiết các schema và thuộc tính
- [ML Documentation](md_files/ml_md/): Tài liệu về hệ thống ML và rủi ro