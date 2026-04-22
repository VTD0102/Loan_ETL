from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import text
from sqlalchemy.orm import Session


def load_chat_history(db: Session, session_id: UUID) -> list:
    """Load last 10 turns from chat_messages and return as LangChain message objects."""
    rows = db.execute(
        text(
            "SELECT role, content FROM chat_messages "
            "WHERE session_id = :sid ORDER BY created_at DESC LIMIT 20"
        ),
        {"sid": str(session_id)},
    ).fetchall()

    messages = []
    for row in reversed(rows):
        if row.role == "user":
            messages.append(HumanMessage(content=row.content))
        else:
            messages.append(AIMessage(content=row.content))
    return messages


def get_or_create_session(db: Session, user_id: int, session_id: UUID | None) -> UUID:
    if session_id is not None:
        row = db.execute(
            text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"),
            {"sid": str(session_id), "uid": user_id},
        ).fetchone()
        if row is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Session not found")
        return session_id
    else:
        row = db.execute(
            text("INSERT INTO chat_sessions (user_id) VALUES (:user_id) RETURNING id"),
            {"user_id": user_id},
        ).fetchone()
        db.commit()
        return row[0]
