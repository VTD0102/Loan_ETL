"""
Shared database connection utility for ML and ETL scripts.

If machinelearning/config/etl_db.env exists and ETL_DB_TYPE=duckdb
→ local DuckDB file (no server needed).
Otherwise → Supabase (backend/.env).
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, Engine

BASE_DIR          = Path(__file__).resolve().parents[1]
PROJECT_ROOT      = BASE_DIR.parent
_ETL_ENV_FILE     = BASE_DIR / "config" / "etl_db.env"
_BACKEND_ENV_FILE = PROJECT_ROOT / "backend" / ".env"

_engine: Engine | None = None


def _read_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip().lower()] = val.strip().strip('"').strip("'")
    return env


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    etl = _read_file(_ETL_ENV_FILE)
    db_type = etl.get("etl_db_type", "postgres")

    if db_type == "duckdb":
        db_path = BASE_DIR / etl.get("etl_db_path", "data/etl.duckdb")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"  [db] DuckDB → {db_path}")
        _engine = create_engine(f"duckdb:///{db_path}", connect_args={"read_only": False})
    else:
        # PostgreSQL: etl_db.env (ETL_DB_*) overrides backend/.env (DB_*)
        cfg = _read_file(_BACKEND_ENV_FILE)
        for k, v in etl.items():
            if k.startswith("etl_db_") and not k == "etl_db_type":
                cfg[k.replace("etl_db_", "db_", 1)] = v
        for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            if k in os.environ:
                cfg[k.lower()] = os.environ[k]

        host = cfg.get("db_host", "localhost")
        port = cfg.get("db_port", "5432")
        name = cfg.get("db_name", "postgres")
        user = cfg.get("db_user", "postgres")
        pwd  = cfg.get("db_password", "")
        source = "local Docker" if _ETL_ENV_FILE.exists() else "Supabase"
        print(f"  [db] PostgreSQL ({source}) → {host}:{port}/{name}")
        _engine = create_engine(
            f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}",
            pool_pre_ping=True, pool_size=2, max_overflow=4,
        )

    return _engine


def reset_engine():
    """Close pooled connections and force re-create engine."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def load_config() -> dict:
    try:
        import yaml
        yaml_path = BASE_DIR / "config" / "settings.yaml"
        if yaml_path.exists():
            with yaml_path.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except ImportError:
        pass
    return {}
