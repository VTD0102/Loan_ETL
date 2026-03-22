from sqlalchemy import text

from utils.db_connection import get_engine


def run_silver_pipeline():
    """Transform data from Bronze to Silver layer.

    Vai trò:
    - Làm sạch dữ liệu từ bảng bronze.
    - Bổ sung các cột PK/FK để phục vụ hệ thống Core (MemberKey, LoanKey...).
    - Khử trùng lặp và ép kiểu dữ liệu chuẩn.
    """
    try:
        engine = get_engine()

        with open("database/transform_silver.sql", "r", encoding="utf-8") as file:
            etl_query = text(file.read())

        with engine.connect() as conn:
            print("⏳ Đang chạy Silver ETL từ Bronze...")
            conn.execute(etl_query)
            conn.commit()
            print("✅ Silver ETL hoàn tất.")

    except Exception as e:
        print(f"❌ Lỗi Silver ETL: {e}")


if __name__ == "__main__":
    run_silver_pipeline()