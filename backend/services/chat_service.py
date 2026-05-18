import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.application import LoanApplication
from models.chat import ChatMessage, ChatSession
from models.user import User
from rag.chain import invoke as _rag_invoke
from rag.context_builder import build_user_context
from rag.exceptions import RAGError
from rag.memory import load_memory
from rag.personalizer import build_personalization
from schemas.application import ApplicationCreate
from services import ml_service

logger = logging.getLogger(__name__)

_RAG_ERROR_MESSAGE = (
    "Xin lỗi, hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau ít phút."
)


def send(db: Session, user_email: str, payload_message: str, session_id: Any = None) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _enforce_rate_limit(db, user.id)
    app = _ensure_latest_application_has_prediction(db, user.id)
    session = _get_or_create_session(db, user.id, session_id)

    # 1) Persist the user message before invoking RAG so it survives any
    #    upstream failure.
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=payload_message,
    )
    db.add(user_message)
    if not session.title:
        session.title = payload_message.strip()[:80]
    db.commit()

    # 2) Build memory context (recent window + lazy summary) for the LLM call.
    memory = load_memory(db, session, exclude_message_id=user_message.id)

    error_flag = False
    sources: list[dict[str, Any]] = []
    try:
        context = build_user_context(db, user.id)
        personalization = build_personalization(user, app)
        response_payload = _rag_invoke(
            payload_message, context, memory.recent_messages,
            personalization=personalization,
            conversation_summary=memory.summary,
        )
        answer = response_payload.get("answer") or ""
        sources = _extract_sources(response_payload.get("source_documents", []))
        if not answer:
            answer = _RAG_ERROR_MESSAGE
            error_flag = True
            sources = []
    except RAGError:
        logger.exception("RAG pipeline failed")
        answer = _RAG_ERROR_MESSAGE
        error_flag = True

    # 3) Save the assistant turn (success or error placeholder).
    db.add(ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources=sources,
        error=error_flag,
    ))
    session.updated_at = datetime.utcnow()
    db.commit()

    if error_flag:
        raise HTTPException(status_code=503, detail=answer)

    return {
        "response": answer,
        "session_id": session.id,
        "sources": sources,
    }


def history(db: Session, user_email: str, session_id: Any = None) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .first()
        )

    if not session:
        return {"session_id": None, "messages": []}

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session_id": session.id,
        "messages": [
            {
                "role": row.role,
                "content": row.content,
                "sources": row.sources or [],
                "created_at": row.created_at,
            }
            for row in messages
        ],
    }


def _enforce_rate_limit(db: Session, user_id: Any) -> None:
    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    query_count = (
        db.query(func.count(ChatMessage.id))
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .filter(
            ChatSession.user_id == user_id,
            ChatMessage.role == "user",
            ChatMessage.created_at >= one_min_ago,
        )
        .scalar()
    )

    if query_count >= 20:
        raise HTTPException(status_code=429, detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau 1 phút.")


def _get_or_create_session(db: Session, user_id: Any, session_id: Any = None) -> ChatSession:
    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session

    session = ChatSession(user_id=user_id)
    db.add(session)
    db.flush()
    return session


def _ensure_latest_application_has_prediction(db: Session, user_id: Any) -> LoanApplication | None:
    app = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )
    if app is None:
        return None
    if app.default_probability is not None and app.model_version:
        return app

    payload = _application_to_payload(app)
    try:
        prediction = ml_service.predict(payload, db=db, user_id=user_id)
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ML model is not available or has an invalid contract: {exc}",
        ) from exc

    app.default_probability = prediction.get("default_probability")
    app.risk_level = prediction.get("risk_level")
    app.risk_score = prediction.get("risk_score")
    app.recommended_amount = prediction.get("recommended_amount")
    app.recommended_term = prediction.get("recommended_term")
    app.model_version = prediction.get("model_version")
    app.feature_snapshot = prediction.get("feature_snapshot")
    app.imputed_features = prediction.get("imputed_features")
    db.flush()
    return app


def _application_to_payload(app: LoanApplication) -> ApplicationCreate:
    return ApplicationCreate.model_construct(
        monthly_income=app.monthly_income,
        loan_amount=app.loan_amount,
        term=app.term,
        employment_status=app.employment_status,
        occupation_type=app.occupation_type or "Unknown",
        years_employed=app.years_employed or 0,
        dti=app.dti,
        is_homeowner=app.is_homeowner,
        listing_category=app.listing_category,
        credit_score=app.credit_score,
        num_bureau_records=app.num_bureau_records or 0,
        num_active_credit=app.num_active_credit or 0,
        total_overdue_amount=app.total_overdue_amount or 0,
        max_credit_overdue_days=app.max_credit_overdue_days or 0,
        has_bad_debt=app.has_bad_debt or False,
        income_verifiable_flag=app.income_verifiable_flag or False,
        age_years=app.age_years or 30,
        gender_male_flag=app.gender_male_flag or False,
        education_ordinal=app.education_ordinal or 3,
        cnt_children=app.cnt_children or 0,
        cnt_fam_members=app.cnt_fam_members or 1,
        is_married_flag=app.is_married_flag or False,
    )


def _extract_sources(documents: list[Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in documents:
        metadata = getattr(doc, "metadata", {}) or {}
        source = metadata.get("source") or metadata.get("file_path") or metadata.get("title")
        if not source:
            source = "knowledge_base"
        key = str(source)
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "source": key,
            "title": metadata.get("title") or key,
        })
    return sources
