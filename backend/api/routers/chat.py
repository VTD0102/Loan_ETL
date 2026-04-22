from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.dependencies import require_customer
from backend.db.session import get_db
from backend.models.chat import ChatRequest, ChatResponse, ChatMessageOut, ChatSessionOut
from backend.services import chat_service

router = APIRouter()


@router.post("", response_model=ChatResponse, status_code=201)
def send_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return chat_service.send(db, current_user["sub"], payload)


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return chat_service.list_sessions(db, current_user["sub"])


@router.get("/history", response_model=list[ChatMessageOut])
def get_history(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return chat_service.get_history(db, session_id, current_user["sub"])
