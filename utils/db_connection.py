import yaml
from sqlalchemy import create_engine


def load_config():

    with open("config/settings.yaml", "r") as file:
        config = yaml.safe_load(file)

    return config


def get_engine():

    config = load_config()

    db = config["database"]

    connection_string = (
        f"postgresql://{db['user']}:{db['password']}"
        f"@{db['host']}:{db['port']}/{db['name']}"
    )

    engine = create_engine(connection_string)

    return engine