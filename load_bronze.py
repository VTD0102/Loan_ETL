import pandas as pd
from sqlalchemy import create_engine

# 1. Cấu hình thông tin (Thay mật khẩu của bạn vào đây)
DB_URL = "postgresql://postgres:26012005@localhost:5432/postgres_LoanManagement"
CSV_FILE = "prosperLoanData.csv" # Đảm bảo file CSV nằm cùng thư mục với code

def main():
    try:
        # Khởi tạo kết nối
        engine = create_engine(DB_URL)
        
        # 2. Đọc dữ liệu (ép kiểu string cho lớp Bronze để đảm bảo nạp thành công 100%)
        print("⏳ Đang đọc file CSV...")
        df = pd.read_csv(CSV_FILE, low_memory=False, dtype=str)
        
        # 3. Đẩy vào Database lớp Bronze
        print(f"🚀 Đang đẩy {df.shape[0]} dòng và {df.shape[1]} cột vào Postgres...")
        df.to_sql(
            name='prosper_loans_raw', 
            con=engine, 
            schema='bronze', 
            if_exists='replace', # Nếu chạy lại sẽ ghi đè bản mới nhất
            index=False
        )
        print("✅ Đã hoàn thành nạp dữ liệu vào lớp Bronze!")

    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    main()