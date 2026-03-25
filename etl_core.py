import os
from sqlalchemy import text
from utils.db_connection import get_engine

def run_core_pipeline():
    try:
        engine = get_engine()
        
        # Bước 1: Khởi tạo Schema và Bảng Core (nếu chưa có)
        with open("database/init_core.sql", "r", encoding="utf-8") as f:
            init_query = text(f.read())
            
        # Bước 2: Chạy biến đổi dữ liệu Silver -> Core
        with open("database/transform_core.sql", "r", encoding="utf-8") as f:
            transform_query = text(f.read())

        with engine.connect() as conn:
            print("⏳ Đang khởi tạo cấu trúc Core Schema...")
            conn.execute(init_query)
            conn.commit()
            
            print("⏳ Đang chuyển đổi dữ liệu từ Silver sang Core (Normalization)...")
            conn.execute(transform_query)
            conn.commit()
            print("✅ Hoàn tất Core ETL!")

    except Exception as e:
        print(f"❌ Lỗi Core ETL: {e}")

if __name__ == "__main__":
    run_core_pipeline()