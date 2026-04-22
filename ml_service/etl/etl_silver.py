from pathlib import Path

from sqlalchemy import text

from utils.db_connection import get_engine

BASE_DIR = Path(__file__).resolve().parents[2]


def run_silver_pipeline():
    """Transform data from Bronze to Silver layer."""
    try:
        engine = get_engine()

        with (BASE_DIR / "database" / "transform_silver.sql").open("r", encoding="utf-8") as file:
            etl_query = text(file.read())

        with engine.connect() as conn:
            print("Running Silver ETL from Bronze")
            conn.execute(etl_query)
            conn.commit()
            print("Silver ETL completed")

    except Exception as exc:
        print(f"Silver ETL failed: {exc}")


if __name__ == "__main__":
    run_silver_pipeline()
