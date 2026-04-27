from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import text

from utils.db_connection import get_engine

BASE_DIR = Path(__file__).resolve().parents[2]


def load_config():
    with (BASE_DIR / "config" / "settings.yaml").open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main():
    """Load raw CSV data into Bronze layer on Supabase."""
    try:
        config = load_config()
        csv_file = config["paths"]["raw_data"]
        schema = config["schemas"]["bronze"]
        table = config["tables"]["raw_loans"]

        engine = get_engine()

        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
            conn.commit()
            print(f"Created or verified schema: {schema}")

        print(f"Reading CSV file: {csv_file}")
        df = pd.read_csv(csv_file, low_memory=False, dtype=str)

        print(f"Loading {df.shape[0]} rows and {df.shape[1]} columns into {schema}.{table}")
        df.to_sql(
            name=table,
            con=engine,
            schema=schema,
            if_exists="replace",
            index=False,
            chunksize=10000,
            method="multi",
        )

        print(f"Bronze load completed: {schema}.{table}")

    except Exception as exc:
        print(f"Bronze load failed: {exc}")


if __name__ == "__main__":
    main()
