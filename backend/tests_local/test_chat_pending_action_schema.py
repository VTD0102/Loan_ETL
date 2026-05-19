"""Verify chat sessions can store pending conversational actions."""

from init_db import _COLUMN_MIGRATIONS
from models.chat import ChatSession


def test_chat_session_has_pending_action_json_column():
    column = ChatSession.__table__.columns["pending_action"]
    assert column.nullable is True
    assert "JSON" in column.type.__class__.__name__.upper()


def test_init_db_registers_pending_action_migration():
    migration_sql = "\n".join(_COLUMN_MIGRATIONS).lower()
    assert "alter table chat_sessions add column if not exists pending_action" in migration_sql
    assert "jsonb" in migration_sql


if __name__ == "__main__":
    test_chat_session_has_pending_action_json_column()
    test_init_db_registers_pending_action_migration()
    print("chat pending action schema tests passed")
