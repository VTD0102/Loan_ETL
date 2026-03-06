# Loan_ETL - Hướng dẫn vận hành dự án

Dự án xử lý dữ liệu khoản vay Prosper theo kiến trúc **Medallion** (Bronze -> Silver -> Gold), phục vụ cho phân tích, huấn luyện mô hình ML và dashboard.

## 1) Cấu trúc thư mục & chức năng

```text
Loan_ETL/
├── config/
│   └── settings.yaml              # Cấu hình DB, đường dẫn dữ liệu, schema/table
├── data/
│   └── raw/
│       └── prosperLoanData.csv    # Dữ liệu đầu vào thô
├── database/
│   ├── init_database.sql          # Tạo database/schema/bảng ban đầu
│   └── transform_silver.sql       # SQL tham chiếu cho bước làm sạch Silver
├── ingestion/
│   └── load_raw_to_postgres.py    # Script nạp raw data vào Postgres
├── utils/
│   └── db_connection.py           # Hàm tạo kết nối DB từ settings.yaml
├── dbt/
│   ├── dbt_project.yml            # Cấu hình dự án dbt
│   └── models/
│       ├── bronze/                # Mô hình dbt lớp Bronze
│       ├── silver/                # Mô hình dbt lớp Silver
│       └── gold/                  # Mô hình dbt lớp Gold
├── expectations/
│   └── loan_expectations.py       # Data quality checks
├── orchestration/
│   ├── airflow_dag.py             # Điều phối pipeline bằng Airflow
│   └── prefect_flow.py            # Điều phối pipeline bằng Prefect
├── ml/
│   ├── train_model.py             # Huấn luyện mô hình
│   └── predict.py                 # Suy luận dự đoán
├── load_bronze.py                 # Script nạp lớp Bronze (chạy nhanh)
├── etl_silver.py                  # Script xử lý làm sạch và nạp lớp Silver
├── requirements.txt               # Danh sách thư viện Python
└── README.md                      # Tài liệu hướng dẫn dự án
```

## 2) Cấu hình hiện tại

Dự án đang dùng PostgreSQL local với cấu hình:
- Host: `localhost`
- Port: `5433`
- User: `postgres`
- Password: `postgres`

Cấu hình này được đặt tại `config/settings.yaml`.

## 3) Cách chạy nhanh (theo thứ tự)

### Bước 0: Cài thư viện

```bash
pip install -r requirements.txt
```

### Bước 1: Khởi tạo database và schema

1. Tạo database (ví dụ): `postgres_LoanManagement` (hoặc DB bạn đang dùng).
2. Chạy file SQL:

```bash
psql -h localhost -p 5433 -U postgres -d postgres_LoanManagement -f database/init_database.sql
```

> Nếu bạn dùng tên DB khác, hãy sửa lại tham số `-d` và đồng bộ trong các script kết nối.

### Bước 2: Nạp dữ liệu Bronze

Chạy một trong hai script:

```bash
python load_bronze.py
```
hoặc
```bash
python ingestion/load_raw_to_postgres.py
```

Kết quả: dữ liệu thô được nạp vào bảng Bronze.

### Bước 3: Xử lý Silver

```bash
python etl_silver.py
```

Kết quả: ép kiểu, làm sạch, khử trùng lặp và tạo cờ `is_default` vào bảng Silver.

### Bước 4 (tuỳ chọn): chạy dbt models

```bash
cd dbt
# dbt deps      # nếu có package
# dbt seed      # nếu có seed
dbt run
dbt test
```

### Bước 5 (tuỳ chọn): kiểm tra chất lượng dữ liệu

```bash
python expectations/loan_expectations.py
```

### Bước 6 (tuỳ chọn): huấn luyện / dự đoán

```bash
python ml/train_model.py
python ml/predict.py
```

## 4) Tác vụ chính đang làm trong dự án

Hiện tại luồng công việc chính của dự án gồm:
1. **Ingestion dữ liệu thô** từ CSV vào Bronze.
2. **Chuẩn hoá dữ liệu Silver** (cast kiểu dữ liệu, xử lý null, deduplicate, tạo nhãn default).
3. **Xây Gold layer bằng dbt** để phục vụ BI/ML.
4. **Data quality checks** để đảm bảo tính tin cậy dữ liệu.
5. **Huấn luyện mô hình ML** dự đoán rủi ro khoản vay.
6. **Orchestration** bằng Airflow/Prefect để tự động hoá pipeline.

## 5) Luồng tổng quan

```text
CSV (raw)
  ↓
Python ingestion
  ↓
PostgreSQL Bronze
  ↓
Silver Transform (Python SQL / dbt)
  ↓
Gold Features (dbt)
  ↓
ML Training/Inference
  ↓
Dashboard/BI
```

## 6) Ghi chú

- Nếu gặp lỗi kết nối DB, kiểm tra lại `config/settings.yaml` và cổng PostgreSQL có đúng `5433` hay không.
- Với các script đang dùng chuỗi kết nối cứng, nên đồng bộ toàn bộ về config để tránh lệch môi trường.
