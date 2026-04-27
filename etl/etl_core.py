from pathlib import Path

from sqlalchemy import text

from utils.db_connection import get_engine

BASE_DIR = Path(__file__).resolve().parents[2]


def run_core_pipeline():
    try:
        engine = get_engine()

        with (BASE_DIR / "database" / "init_core.sql").open("r", encoding="utf-8") as file:
            init_query = text(file.read())

        with (BASE_DIR / "database" / "transform_core.sql").open("r", encoding="utf-8") as file:
            transform_query = text(file.read())

        with engine.connect() as conn:
            print("Initializing Core schema")
            conn.execute(init_query)
            conn.commit()

            print("Running Core ETL from Silver")
            conn.execute(transform_query)
            conn.commit()
            print("Core ETL completed")

    except Exception as exc:
        print(f"Core ETL failed: {exc}")


if __name__ == "__main__":
    run_core_pipeline()
