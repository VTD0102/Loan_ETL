import sys
from pathlib import Path

import duckdb
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from machinelearning.utils import db_connection


def test_reset_engine_disposes_duckdb_pool_before_read_only_reopen(tmp_path, monkeypatch):
    env_file = tmp_path / "etl_db.env"
    env_file.write_text(
        "ETL_DB_TYPE=duckdb\nETL_DB_PATH=data/etl.duckdb\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "data" / "etl.duckdb"

    monkeypatch.setattr(db_connection, "BASE_DIR", tmp_path)
    monkeypatch.setattr(db_connection, "_ETL_ENV_FILE", env_file)
    monkeypatch.setattr(db_connection, "_engine", None)

    engine = db_connection.get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sample AS SELECT 1 AS id"))

    db_connection.reset_engine()

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        assert con.execute("SELECT id FROM sample").fetchone() == (1,)
    finally:
        con.close()

