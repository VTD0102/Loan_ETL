Hướng dẫn vận hành Pipeline (Prosper Loan Project)
Dự án này thực hiện luồng dữ liệu tự động theo mô hình Medallion (Bronze -> Silver). Để chạy dự án, hãy thực hiện theo đúng thứ tự 3 bước dưới đây:

Bước 1: Khởi tạo Database & Cấu trúc
Tạo Database tên: postgres_LoanManagement.
Mở file init_database.sql và thực thi để khởi tạo các Schema (bronze, silver, gold) cùng cấu trúc bảng Silver trống.

Bước 2: Nạp dữ liệu lớp Bronze (Thô)
Đảm bảo file prosperLoanData.csv nằm cùng thư mục, sau đó chạy:
Chạy python load_bronze.py
Kết quả: 113,937 dòng dữ liệu thô sẽ được nạp vào bảng bronze.prosper_loans_raw.

Bước 3: Nạp dữ liệu lớp Silver (Sạch)
Chạy script để thực hiện ép kiểu, khử trùng lặp và tạo nhãn vỡ nợ:
Chạy python etl_silver.py
Kết quả: Bảng silver.prosper_loans_cleansed

File tham khảo: File transform_silver.sql chứa toàn bộ logic SQL chi tiết (ép kiểu ::FLOAT::INT, gộp Rating) dùng để đối chiếu khi cần.
