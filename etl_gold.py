from sqlalchemy import text

from utils.db_connection import get_engine


def run_gold_pipeline():
    """Transform data from Core/Silver to Gold layer.

    Vai trò:
    - Tạo feature table phục vụ Machine Learning.
    - Tạo analytical views phục vụ dashboard và báo cáo.
    - Loại bỏ các cột gây leakage trong mô hình ML.
    """
    try:
        engine = get_engine()

        with open("database/transform_gold.sql", "r", encoding="utf-8") as file:
            etl_query = text(file.read())

        with engine.connect() as conn:
            print("⏳ Đang chạy Gold ETL từ Core/Silver...")
            conn.execute(etl_query)
            conn.commit()
            print("✅ Gold ETL hoàn tất.")

    except Exception as e:
        print(f"❌ Lỗi Gold ETL: {e}")


if __name__ == "__main__":
    run_gold_pipeline()