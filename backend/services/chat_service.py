from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.chat import ChatRequest
from backend.rag import chain as rag_chain
from backend.rag.context_builder import build_user_context
from backend.rag.memory import get_or_create_session


def send(db: Session, user_id: int, payload: ChatRequest):
    # TODO: get_or_create chat session
    # TODO: build user_context from latest loan_application
    # TODO: run rag_chain.invoke(message, user_context, session_id)
    # TODO: persist user message + assistant reply in chat_messages
    # TODO: return ChatResponse
    raise NotImplementedError


def list_sessions(db: Session, user_id: int):
    # TODO: query chat_sessions for user ordered by updated_at DESC
    raise NotImplementedError


def get_history(db: Session, session_id: UUID, user_id: int):
    # TODO: verify session belongs to user
    # TODO: return chat_messages ordered by created_at
    raise NotImplementedError
