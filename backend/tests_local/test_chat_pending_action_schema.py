"""Verify chat sessions can store pending conversational actions."""

import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from init_db import _COLUMN_MIGRATIONS
from models.chat import ChatSession


def test_chat_session_has_pending_action_json_column():
    column = ChatSession.__table__.columns["pending_action"]
    assert column.nullable is True
    assert "JSON" in column.type.__class__.__name__.upper()
    postgresql_type = column.type.dialect_impl(postgresql.dialect())
    assert "JSONB" in postgresql_type.__class__.__name__.upper()


def test_init_db_registers_pending_action_migration():
    pending_action_migrations = [
        migration
        for migration in _COLUMN_MIGRATIONS
        if "pending_action" in migration.lower()
    ]
    assert pending_action_migrations == [
        "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS pending_action JSONB"
    ]


if __name__ == "__main__":
    test_chat_session_has_pending_action_json_column()
    test_init_db_registers_pending_action_migration()
    print("chat pending action schema tests passed")
