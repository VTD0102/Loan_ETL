import pandas as pd
import yaml

from utils.db_connection import get_engine


def load_config():
    with open("config/settings.yaml", "r") as file:
        return yaml.safe_load(file)


def main():
    """Load raw CSV data into Bronze layer.

    Vai trò:
    - Đọc dữ liệu raw theo path cấu hình.
    - Nạp dữ liệu vào bảng Bronze đúng schema/table trong settings.
    """
    try:
        config = load_config()
        csv_file = config["paths"]["raw_data"]
        schema = config["schemas"]["bronze"]
        table = config["tables"]["raw_loans"]

        engine = get_engine()

        print(f"⏳ Đang đọc file CSV: {csv_file}")
        df = pd.read_csv(csv_file, low_memory=False, dtype=str)

        print(f"🚀 Đang nạp {df.shape[0]} dòng và {df.shape[1]} cột vào {schema}.{table}...")
        df.to_sql(
            name=table,
            con=engine,
            schema=schema,
            if_exists="replace",
            index=False,
        )

        print(f"✅ Đã hoàn thành nạp dữ liệu vào lớp Bronze: {schema}.{table}")

    except Exception as e:
        print(f"❌ Lỗi load Bronze: {e}")


if __name__ == "__main__":
    main()
