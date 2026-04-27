from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.chat import ChatMessage
from models.user import User


def send(db: Session, user_email: str, payload_message: str) -> str:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    user_id = user.id

    # 1. Rate Limiting: 20 per minute
    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    query_count = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.user_id == user_id,
        ChatMessage.created_at >= one_min_ago
    ).scalar()

    if query_count >= 20:
        raise HTTPException(status_code=429, detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau 1 phút.")

    # 2. Extract Logic (Memory Bypass)
    history_rows = db.query(ChatMessage).filter(ChatMessage.user_id == user_id).order_by(ChatMessage.created_at.desc()).limit(10).all()
    
    # 4. Invoke RAG Stateless
    try:
        from langchain_core.messages import AIMessage, HumanMessage
        from rag.chain import invoke
        from rag.context_builder import build_user_context
        
        chat_history = []
        for row in reversed(history_rows):
            chat_history.append(HumanMessage(content=row.message))
            chat_history.append(AIMessage(content=row.response))

        # 3. Context Builder
        context = build_user_context(db, user_id)
        
        response_payload = invoke(payload_message, context, chat_history)
        answer = response_payload.get("answer", "Xin lỗi, hiện tại tôi không thể kết nối tới lõi suy luận kiến thức.")
    except ImportError as ie:
        answer = f"⚠️ RAG Module chưa sẵn sàng (Chưa cài đặt đủ thư viện Môi trường: {str(ie)}). Xin thử lại sau."
    except Exception as e:
        answer = f"Lỗi truy vấn nội bộ RAG/LLM: {str(e)}"

    # 5. Log Database saving mechanism
    log_entry = ChatMessage(
        user_id=user_id,
        message=payload_message,
        response=answer,
        is_bot=True
    )
    db.add(log_entry)
    db.commit()

    return answer
