import pandas as pd
import yaml
from utils.db_connection import get_engine


def load_config():

    with open("config/settings.yaml", "r") as file:
        config = yaml.safe_load(file)

    return config


def load_csv():

    config = load_config()

    file_path = config["paths"]["raw_data"]

    df = pd.read_csv(file_path)

    return df


def load_to_postgres(df):

    config = load_config()

    schema = config["schemas"]["bronze"]
    table = config["tables"]["raw_loans"]

    engine = get_engine()

    df.to_sql(
        table,
        engine,
        schema=schema,
        if_exists="replace",
        index=False
    )

    print(f"Loaded data to {schema}.{table}")


def main():

    df = load_csv()

    load_to_postgres(df)


if __name__ == "__main__":
    main()