from pathlib import Path

from sqlalchemy import text

from utils.db_connection import get_engine

BASE_DIR = Path(__file__).resolve().parents[2]


def run_gold_pipeline():
    """Transform data from Core or Silver to Gold layer."""
    try:
        engine = get_engine()

        with (BASE_DIR / "database" / "transform_gold.sql").open("r", encoding="utf-8") as file:
            etl_query = text(file.read())

        with engine.connect() as conn:
            print("Running Gold ETL from Core or Silver")
            conn.execute(etl_query)
            conn.commit()
            print("Gold ETL completed")

    except Exception as exc:
        print(f"Gold ETL failed: {exc}")


if __name__ == "__main__":
    run_gold_pipeline()
