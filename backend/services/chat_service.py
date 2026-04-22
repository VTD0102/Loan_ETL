import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.chat import ChatMessageOut, ChatRequest, ChatResponse, ChatSessionOut, SourceChunk
from backend.rag import chain as rag_chain
from backend.rag.context_builder import build_user_context
from backend.rag.memory import get_or_create_session, load_chat_history


def send(db: Session, user_id: int, payload: ChatRequest) -> ChatResponse:
    # 1. Get or create chat session
    session_id = get_or_create_session(db, user_id, payload.session_id)

    # 2. Build user context from latest loan application
    user_context = build_user_context(db, user_id)

    # 3. Load chat history from our own chat_messages table
    chat_history = load_chat_history(db, session_id)

    # 4. Run RAG chain
    result = rag_chain.invoke(payload.message, user_context, chat_history)
    answer = result["answer"]
    source_documents = result["source_documents"]

    # 5. Persist user message
    db.execute(
        text(
            "INSERT INTO chat_messages (session_id, role, content, sources) "
            "VALUES (:sid, 'user', :content, NULL)"
        ),
        {"sid": str(session_id), "content": payload.message},
    )

    # 6. Build sources list
    sources = [
        {
            "file": doc.metadata.get("source", ""),
            "snippet": doc.page_content[:150],
            "score": 0.0,
        }
        for doc in source_documents
    ]

    # 7. Persist assistant message
    db.execute(
        text(
            "INSERT INTO chat_messages (session_id, role, content, sources) "
            "VALUES (:sid, 'assistant', :content, :sources)"
        ),
        {"sid": str(session_id), "content": answer, "sources": json.dumps(sources)},
    )

    # 8. Update session updated_at
    db.execute(
        text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :sid"),
        {"sid": str(session_id)},
    )

    # 9. Set title if session is new (title is NULL)
    db.execute(
        text(
            "UPDATE chat_sessions SET title = :title "
            "WHERE id = :sid AND title IS NULL"
        ),
        {"sid": str(session_id), "title": payload.message[:50]},
    )

    db.commit()

    # 10. Return ChatResponse
    return ChatResponse(
        answer=answer,
        sources=[SourceChunk(**s) for s in sources],
        session_id=session_id,
        created_at=datetime.utcnow(),
    )


def list_sessions(db: Session, user_id: int) -> list[ChatSessionOut]:
    rows = db.execute(
        text(
            "SELECT id, title, created_at, updated_at "
            "FROM chat_sessions "
            "WHERE user_id = :uid "
            "ORDER BY updated_at DESC"
        ),
        {"uid": user_id},
    ).fetchall()

    return [
        ChatSessionOut(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def get_history(db: Session, session_id: UUID, user_id: int) -> list[ChatMessageOut]:
    # Verify session belongs to user
    session_row = db.execute(
        text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"),
        {"sid": str(session_id), "uid": user_id},
    ).fetchone()

    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = db.execute(
        text(
            "SELECT id, role, content, sources, created_at "
            "FROM chat_messages "
            "WHERE session_id = :sid "
            "ORDER BY created_at"
        ),
        {"sid": str(session_id)},
    ).fetchall()

    messages = []
    for row in rows:
        sources = None
        if row.sources is not None:
            raw = row.sources if isinstance(row.sources, list) else json.loads(row.sources)
            sources = [SourceChunk(**s) for s in raw]

        messages.append(
            ChatMessageOut(
                id=row.id,
                role=row.role,
                content=row.content,
                sources=sources,
                created_at=row.created_at,
            )
        )

    return messages
