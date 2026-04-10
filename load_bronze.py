import pandas as pd
import yaml
from sqlalchemy import text # Thêm thư viện này để chạy lệnh SQL thô
from utils.db_connection import get_engine

def load_config():
    with open("config/settings.yaml", "r") as file:
        return yaml.safe_load(file)

def main():
    """Load raw CSV data into Bronze layer on Supabase.
    
    Vai trò:
    - Đọc dữ liệu raw.
    - Tạo Schema trên Supabase nếu chưa có.
    - Nạp dữ liệu siêu tốc bằng chunksize và multi method.
    """
    try:
        config = load_config()
        csv_file = config["paths"]["raw_data"]
        schema = config["schemas"]["bronze"]
        table = config["tables"]["raw_loans"]

        engine = get_engine()

        # 1. BẢO ĐẢM SCHEMA TỒN TẠI TRÊN SUPABASE
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
            conn.commit()
            print(f"✅ Đã kiểm tra/tạo Schema: '{schema}' trên Supabase.")

        # 2. ĐỌC DỮ LIỆU TỪ CSV
        print(f"⏳ Đang đọc file CSV: {csv_file}")
        # dtype=str giữ nguyên mọi thứ ở dạng Text để Bronze không bị lỗi mất mát dữ liệu
        df = pd.read_csv(csv_file, low_memory=False, dtype=str) 

        # 3. ĐẨY LÊN SUPABASE (TỐI ƯU HÓA CLOUD)
        print(f"🚀 Đang nạp {df.shape[0]} dòng và {df.shape[1]} cột vào {schema}.{table}...")
        
        df.to_sql(
            name=table,
            con=engine,
            schema=schema,
            if_exists="replace",
            index=False,
            chunksize=10000,    # Chia thành các gói 10k dòng để không bị sập mạng
            method='multi'      # Chèn nhiều dòng cùng lúc (Nhanh gấp 50 lần)
        )

        print(f"🎉 THÀNH CÔNG: Đã nạp dữ liệu vào lớp Bronze ({schema}.{table}) trên Supabase!")

    except Exception as e:
        print(f"❌ Lỗi load Bronze: {e}")

if __name__ == "__main__":
    main()