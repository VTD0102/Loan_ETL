from sqlalchemy import text

from utils.db_connection import get_engine


def run_gold_pipeline():
    """Transform data from Silver to Gold layer.

    Vai trò:
    - Lấy dữ liệu đã làm sạch từ silver.
    - Loại bỏ các cột có leakage.
    - Tạo feature engineering cho bài toán ML baseline.
    """
    try:
        engine = get_engine()

        with open("database/transform_gold.sql", "r", encoding="utf-8") as file:
            etl_query = text(file.read())

        with engine.connect() as conn:
            print("⏳ Đang chạy Gold ETL từ Silver...")
            conn.execute(etl_query)
            conn.commit()
            print("✅ Gold ETL hoàn tất.")

    except Exception as e:
        print(f"❌ Lỗi Gold ETL: {e}")


if __name__ == "__main__":
    run_gold_pipeline()