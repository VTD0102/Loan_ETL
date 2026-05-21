import importlib.util
import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BACKEND_DIR / "core" / "config.py"

ENV_KEYS = [
    "DATABASE_URL",
    "BUREAU_DATABASE_URL",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "BUREAU_DB_HOST",
    "BUREAU_DB_PORT",
    "BUREAU_DB_NAME",
    "BUREAU_DB_USER",
    "BUREAU_DB_PASSWORD",
    "SECRET_KEY",
    "OPENROUTER_API_KEY",
]


def load_config_with_env(overrides: dict[str, str]):
    original = {key: os.environ.get(key) for key in ENV_KEYS}
    try:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.update(overrides)

        spec = importlib.util.spec_from_file_location("config_under_test", CONFIG_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def base_env() -> dict[str, str]:
    return {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "loan_etl",
        "DB_USER": "postgres",
        "DB_PASSWORD": "postgres",
        "SECRET_KEY": "test-secret",
        "OPENROUTER_API_KEY": "test-openrouter-key",
    }


def test_settings_builds_database_urls_from_db_components():
    config = load_config_with_env(base_env())

    expected = "postgresql://postgres:postgres@localhost:5432/loan_etl"
    assert config.settings.database_url == expected
    assert config.settings.bureau_database_url == expected


def test_settings_builds_bureau_url_from_bureau_db_components():
    env = {
        **base_env(),
        "BUREAU_DB_HOST": "bureau.local",
        "BUREAU_DB_PORT": "6543",
        "BUREAU_DB_NAME": "bureau_db",
        "BUREAU_DB_USER": "bureau_user",
        "BUREAU_DB_PASSWORD": "bureau_pass",
    }

    config = load_config_with_env(env)

    assert config.settings.database_url == "postgresql://postgres:postgres@localhost:5432/loan_etl"
    assert config.settings.bureau_database_url == "postgresql://bureau_user:bureau_pass@bureau.local:6543/bureau_db"


if __name__ == "__main__":
    test_settings_builds_database_urls_from_db_components()
    test_settings_builds_bureau_url_from_bureau_db_components()
    print("Backend config tests passed")
