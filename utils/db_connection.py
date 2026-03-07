"""Database connection utilities for the loan data platform."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load YAML configuration from disk."""
    path = config_path or DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def _resolve_setting(env_name: str, config_value: Any, default: Any | None = None) -> Any:
    """Return environment variable override if set, else fallback to config/default."""
    return os.getenv(env_name, config_value if config_value is not None else default)


def get_database_settings(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build database settings with environment-variable overrides.

    Env vars:
    - LOAN_DB_HOST
    - LOAN_DB_PORT
    - LOAN_DB_NAME
    - LOAN_DB_USER
    - LOAN_DB_PASSWORD
    """
    base = dict((config or load_config()).get("database", {}))

    settings = {
        "host": _resolve_setting("LOAN_DB_HOST", base.get("host"), "localhost"),
        "port": int(_resolve_setting("LOAN_DB_PORT", base.get("port"), 5432)),
        "name": _resolve_setting("LOAN_DB_NAME", base.get("name"), "postgres"),
        "user": _resolve_setting("LOAN_DB_USER", base.get("user"), "postgres"),
        "password": _resolve_setting("LOAN_DB_PASSWORD", base.get("password"), ""),
        "pool_size": int(_resolve_setting("LOAN_DB_POOL_SIZE", base.get("pool_size"), 5)),
        "max_overflow": int(_resolve_setting("LOAN_DB_MAX_OVERFLOW", base.get("max_overflow"), 10)),
        "pool_recycle": int(_resolve_setting("LOAN_DB_POOL_RECYCLE", base.get("pool_recycle"), 1800)),
    }

    return settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache a SQLAlchemy engine with connection pooling enabled."""
    db = get_database_settings()

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=str(db["user"]),
        password=str(db["password"]),
        host=str(db["host"]),
        port=int(db["port"]),
        database=str(db["name"]),
    )

    return create_engine(
        url,
        pool_size=int(db["pool_size"]),
        max_overflow=int(db["max_overflow"]),
        pool_pre_ping=True,
        pool_recycle=int(db["pool_recycle"]),
        future=True,
    )
