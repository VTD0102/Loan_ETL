from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import require_customer
from db.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from services import chat_service

router = APIRouter()

@router.post("", response_model=ChatResponse, status_code=201)
def send_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    """
    **Send a Query to the AI Loan Advisor (RAG).**
    - Checks past limits (20 query/minute).
    - Translates DB context dynamically.
    - Saves transcript to DB seamlessly.
    """
    answer = chat_service.send(db, current_user["sub"], payload.message)
    return ChatResponse(response=answer)
