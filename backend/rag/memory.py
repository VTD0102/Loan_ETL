from uuid import UUID

from langchain_community.chat_message_histories import PostgresChatMessageHistory
from sqlalchemy.orm import Session

from backend.core.config import settings


def get_message_history(session_id: UUID) -> PostgresChatMessageHistory:
    connection_string = (
        f"postgresql+psycopg2://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
    # TODO: return PostgresChatMessageHistory with correct table_name
    raise NotImplementedError


def get_or_create_session(db: Session, user_id: int, session_id: UUID | None) -> UUID:
    # TODO: if session_id given, verify it belongs to user
    # TODO: else insert new chat_sessions row and return new UUID
    raise NotImplementedError
