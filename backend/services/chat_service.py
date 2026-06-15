import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
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
from services import application_service, loan_adjustment_tool, ml_service

logger = logging.getLogger(__name__)

_RAG_ERROR_MESSAGE = (
    "Xin lỗi, hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau ít phút."
)
_LOAN_ADJUSTMENT_ERROR_MESSAGE = (
    "Xin lỗi, mình không thể mô phỏng phương án nộp lại lúc này. "
    "Vui lòng thử lại sau ít phút."
)
_ADJUSTMENT_CONTEXT_TERMS = (
    "bị từ chối",
    "bi tu choi",
    "không được duyệt",
    "khong duoc duyet",
)
_ADJUSTMENT_DIRECT_ACTION_TERMS = (
    "đổi kỳ hạn",
    "doi ky han",
    "đổi thời hạn",
    "doi thoi han",
)
_ADJUSTMENT_TERM_QUESTION_TERMS = (
    "kỳ hạn nào",
    "ky han nao",
    "thời hạn nào",
    "thoi han nao",
)
_ADJUSTMENT_WORDING_TERMS = (
    "kỳ hạn",
    "ky han",
    "thời hạn",
    "thoi han",
)
_ADJUSTMENT_HELP_TERMS = (
    "đề xuất",
    "de xuat",
    "gợi ý",
    "goi y",
    "phương án",
    "phuong an",
)
_ADJUSTMENT_PERSONAL_ACTION_TERMS = (
    "giúp tôi",
    "giup toi",
    "cho tôi",
    "cho toi",
    "hồ sơ của tôi",
    "ho so cua toi",
)
_ADJUSTMENT_RESUBMIT_TERMS = (
    "nộp lại",
    "nop lai",
    "nộp đơn",
    "nop don",
    "gửi lại",
    "gui lai",
    "nộp theo",
    "nop theo",
    "tự động nộp",
    "tu dong nop",
    "nộp khoản vay",
    "nop khoan vay",
    # Phrases that the AI itself suggests as quick-replies — must trigger the tool
    "gói vay phù hợp",
    "goi vay phu hop",
    "khoản vay phù hợp",
    "khoan vay phu hop",
    "đề xuất gói",
    "de xuat goi",
    "đề xuất khoản vay",
    "de xuat khoan vay",
    "đề xuất phương án",
    "de xuat phuong an",
    "gợi ý gói",
    "goi y goi",
    "phương án khác",
    "phuong an khac",
    "phương án vay",
    "phuong an vay",
)
_AFFIRMATIVE_KEYWORDS = (
    "đồng ý",
    "dong y",
    "xác nhận",
    "xac nhan",
    "nộp lại",
    "nop lai",
    "gửi lại",
    "gui lai",
    "ok",
    "duyệt phương án",
    "duyet phuong an",
)
_NEGATIVE_KEYWORDS = (
    "chưa",
    "chua",
    "đừng",
    "dung",
    "không đồng ý",
    "khong dong y",
    "không xác nhận",
    "khong xac nhan",
    "không",
    "khong",
    "hủy",
    "huy",
    "bỏ qua",
    "bo qua",
    "đổi phương án khác",
    "doi phuong an khac",
)
_PUNCTUATION_CHARS = ",.;:!?()[]{}\"'“”‘’"
_CONFIRMATION_PUNCTUATION_TRANSLATION = str.maketrans(_PUNCTUATION_CHARS, " " * len(_PUNCTUATION_CHARS))


class _LoanAdjustmentToolError(Exception):
    pass


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

    direct_answer = _handle_pending_loan_adjustment_response(db, user_email, user.id, session, payload_message)
    if direct_answer is not None:
        db.add(ChatMessage(
            session_id=session.id,
            role="assistant",
            content=direct_answer,
            sources=[],
            error=False,
        ))
        session.updated_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist assistant message")
            raise HTTPException(503, _RAG_ERROR_MESSAGE)
        return {
            "response": direct_answer,
            "session_id": session.id,
            "sources": [],
            "pending_action": _serialize_pending_loan_adjustment_action(session),
        }

    has_pending_loan_adjustment = _has_pending_loan_adjustment_action(session)
    error_flag = False
    sources: list[dict[str, Any]] = []
    try:
        tool_result = None
        pending_action = None
        if not has_pending_loan_adjustment and _is_loan_adjustment_request(payload_message):
            try:
                tool_result = loan_adjustment_tool.find_best_reapplication_option(db, user.id)
                if tool_result.proposal is not None:
                    pending_action = loan_adjustment_tool.build_pending_action(tool_result)
            except Exception as exc:
                raise _LoanAdjustmentToolError from exc

        context = build_user_context(db, user.id)
        if tool_result is not None:
            try:
                context = f"{context}\n\n{_format_loan_adjustment_context(tool_result)}"
            except Exception as exc:
                raise _LoanAdjustmentToolError from exc
        personalization = build_personalization(user, app)
        response_payload = _rag_invoke(
            payload_message, context, memory.recent_messages,
            personalization=personalization,
            conversation_summary=memory.summary,
        )
        answer = (response_payload.get("answer") or "").strip()
        sources = _extract_sources(response_payload.get("source_documents", []))
        if not answer:
            answer = _RAG_ERROR_MESSAGE
            error_flag = True
            sources = []
        if pending_action is not None and not error_flag:
            session.pending_action = pending_action
    except _LoanAdjustmentToolError:
        logger.exception("Loan adjustment tool failed")
        answer = _LOAN_ADJUSTMENT_ERROR_MESSAGE
        error_flag = True
    except (RAGError, ml_service.ModelPredictionError):
        logger.exception("Chat pipeline failed")
        answer = _RAG_ERROR_MESSAGE
        error_flag = True
    except Exception as exc:
        logger.exception("Chat pipeline unknown error")
        answer = f"Lỗi không xác định: {exc}"
        error_flag = True

    # 3) Save the assistant turn (success or error placeholder).
    db.add(ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources=sources,
        error=error_flag,
    ))
    session.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist assistant message")
        raise HTTPException(503, _RAG_ERROR_MESSAGE)

    if error_flag:
        raise HTTPException(status_code=503, detail=answer)

    return {
        "response": answer,
        "session_id": session.id,
        "sources": sources,
        "pending_action": _serialize_pending_loan_adjustment_action(session),
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
        "pending_action": _serialize_pending_loan_adjustment_action(session),
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


def list_sessions(db: Session, user_email: str) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    rows = (
        db.query(
            ChatSession.id,
            ChatSession.title,
            ChatSession.created_at,
            ChatSession.updated_at,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .filter(ChatSession.user_id == user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .all()
    )
    return {
        "sessions": [
            {
                "id": str(r.id),
                "title": r.title or "Đoạn chat mới",
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "message_count": int(r.message_count or 0),
            }
            for r in rows
        ]
    }


def create_session(db: Session, user_email: str) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    session = ChatSession(user_id=user.id, title=None)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": str(session.id),
        "title": session.title or "Đoạn chat mới",
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": 0,
    }


def delete_session(db: Session, user_email: str, session_id: Any) -> dict:
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.delete(session)
    db.commit()
    return {"deleted": True, "id": str(session_id)}


def _enforce_rate_limit(db: Session, user_id: Any) -> None:
    one_min_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
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
    if app.status in ("APPROVED", "ADMIN_REJECTED", "AUTO_REJECTED"):
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
        education_ordinal=app.education_ordinal or 3,
        is_married_flag=app.is_married_flag or False,
    )


def _handle_pending_loan_adjustment_response(
    db: Session,
    user_email: str,
    user_id: Any,
    session: ChatSession,
    message: str,
) -> str | None:
    action = getattr(session, "pending_action", None) or {}
    if action.get("type") != "loan_term_adjustment":
        return None
    if action.get("status") != "pending_confirmation":
        return None

    if loan_adjustment_tool.is_pending_action_expired(action):
        session.pending_action = None
        return "Phương án nộp lại đã hết hạn. Bạn hãy yêu cầu mình mô phỏng lại để lấy kết quả mới nhất."

    if _is_negative_response(message):
        session.pending_action = None
        return "Mình đã hủy phương án nộp lại đang chờ xác nhận. Hồ sơ bị từ chối cũ không bị thay đổi."

    if _is_affirmative_response(message):
        selected_index = _extract_selected_proposal_index(message)
        return _confirm_pending_loan_adjustment(
            db, user_email, user_id, session, action,
            selected_index=selected_index,
        )

    return None


def _has_pending_loan_adjustment_action(session: ChatSession) -> bool:
    action = getattr(session, "pending_action", None) or {}
    return (
        action.get("type") == "loan_term_adjustment"
        and action.get("status") == "pending_confirmation"
    )


def _serialize_pending_loan_adjustment_action(session: ChatSession) -> dict[str, Any] | None:
    action = getattr(session, "pending_action", None) or {}
    if action.get("type") != "loan_term_adjustment":
        return None
    if action.get("status") != "pending_confirmation":
        return None
    if loan_adjustment_tool.is_pending_action_expired(action):
        return None

    proposal = action.get("proposal")
    if not isinstance(proposal, dict):
        return None

    proposal_options = action.get("proposals")
    if not isinstance(proposal_options, list) or not proposal_options:
        proposal_options = [proposal]

    return {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": action.get("source_application_id"),
        "current_loan_amount": action.get("current_loan_amount"),
        "current_term": action.get("current_term"),
        "created_at": action.get("created_at"),
        "expires_at": action.get("expires_at"),
        "proposal": {
            "loan_amount": proposal.get("loan_amount"),
            "term": proposal.get("term"),
            "default_probability": proposal.get("default_probability"),
            "risk_level": proposal.get("risk_level"),
            "risk_score": proposal.get("risk_score"),
            "model_version": proposal.get("model_version"),
            "adjustment_strategy": proposal.get("adjustment_strategy"),
        },
        "proposals": [
            {
                "loan_amount": item.get("loan_amount"),
                "term": item.get("term"),
                "default_probability": item.get("default_probability"),
                "risk_level": item.get("risk_level"),
                "risk_score": item.get("risk_score"),
                "model_version": item.get("model_version"),
                "adjustment_strategy": item.get("adjustment_strategy"),
            }
            for item in proposal_options
            if isinstance(item, dict)
        ],
    }


def _confirm_pending_loan_adjustment(
    db: Session,
    user_email: str,
    user_id: Any,
    session: ChatSession,
    action: dict[str, Any],
    selected_index: int = 0,
) -> str:
    source_application_id = str(action.get("source_application_id") or "")
    source_app = loan_adjustment_tool.get_source_application(db, user_id, source_application_id)
    if source_app is None:
        session.pending_action = None
        return "Không tìm thấy hồ sơ gốc của phương án này. Mình đã hủy phương án cũ; bạn hãy yêu cầu mô phỏng lại."

    proposal_values = _extract_pending_proposal_values(action, selected_index=selected_index)
    if proposal_values is None:
        session.pending_action = None
        return "Phương án nộp lại đang chờ xác nhận không còn hợp lệ. Mình đã hủy phương án cũ; bạn hãy yêu cầu mô phỏng lại."

    loan_amount, term = proposal_values
    payload = loan_adjustment_tool.application_to_confirm_payload(
        source_app,
        loan_amount=loan_amount,
        term=term,
    )

    from db.session import BureauSessionLocal
    bureau_db = BureauSessionLocal()
    try:
        result = application_service.confirm(db, bureau_db, user_email, payload)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
            session.pending_action = None
        return f"Chưa thể nộp lại phương án này: {exc.detail}"
    finally:
        bureau_db.close()

    session.pending_action = None
    return (
        "Đã nộp lại hồ sơ mới với "
        f"số tiền {payload.loan_amount} và kỳ hạn {payload.term} tháng. "
        f"Mã hồ sơ mới: {result['application_id']}. "
        f"Trạng thái hiện tại: {result['status']}. "
        f"Xác suất vỡ nợ dự kiến: {float(result['default_probability']):.4f}. "
        "Hồ sơ bị từ chối trước đó không bị chỉnh sửa."
    )


def _extract_pending_proposal_values(
    action: dict[str, Any],
    selected_index: int = 0,
) -> tuple[Decimal, int] | None:
    proposal = None
    if selected_index > 0:
        proposals = action.get("proposals")
    else:
        proposals = None
    if isinstance(proposals, list) and selected_index < len(proposals):
        candidate = proposals[selected_index]
        if isinstance(candidate, dict):
            proposal = candidate
    if proposal is None:
        proposal = action.get("proposal")
    if not isinstance(proposal, dict):
        return None
    try:
        loan_amount = Decimal(str(proposal["loan_amount"]))
        term = int(proposal["term"])
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if not loan_amount.is_finite() or loan_amount <= 0 or term <= 0:
        return None
    return loan_amount, term


def _extract_selected_proposal_index(message: str) -> int:
    text = _normalize_message(message)
    match = re.search(r"(?:phương án|phuong an|gói|goi)\s+([123])\b", text)
    if not match:
        return 0
    return int(match.group(1)) - 1


def _is_affirmative_response(message: str) -> bool:
    text = _normalize_message(message)
    if any(_contains_phrase(text, keyword) for keyword in _NEGATIVE_KEYWORDS):
        return False
    return any(_contains_phrase(text, keyword) for keyword in _AFFIRMATIVE_KEYWORDS)


def _is_negative_response(message: str) -> bool:
    text = _normalize_message(message)
    return any(_contains_phrase(text, keyword) for keyword in _NEGATIVE_KEYWORDS)


def _is_loan_adjustment_request(message: str) -> bool:
    text = _normalize_message(message)
    has_context = any(term in text for term in _ADJUSTMENT_CONTEXT_TERMS)
    has_direct_action = any(term in text for term in _ADJUSTMENT_DIRECT_ACTION_TERMS)
    has_term_question = any(term in text for term in _ADJUSTMENT_TERM_QUESTION_TERMS)
    has_adjustment_wording = any(term in text for term in _ADJUSTMENT_WORDING_TERMS)
    has_help_action = any(term in text for term in _ADJUSTMENT_HELP_TERMS)
    has_personal_action = any(term in text for term in _ADJUSTMENT_PERSONAL_ACTION_TERMS)
    has_resubmit = any(term in text for term in _ADJUSTMENT_RESUBMIT_TERMS)
    is_resubmit_policy_question = (
        has_resubmit
        and any(term in text for term in ("có thể", "co the", "được không", "duoc khong"))
        and not has_help_action
        and not has_direct_action
    )
    return (
        has_direct_action
        and (has_context or has_help_action or has_personal_action)
    ) or (
        has_context
        and has_help_action
        and (has_direct_action or has_term_question or has_adjustment_wording)
    ) or (
        has_resubmit and not is_resubmit_policy_question
    )


def _normalize_message(message: str) -> str:
    text = message.strip().lower().translate(_CONFIRMATION_PUNCTUATION_TRANSLATION)
    return " ".join(text.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if phrase == "dung":
        text = f" {text} ".replace(" su dung ", " ")
        return f" {phrase} " in text
    return f" {phrase} " in f" {text} "


def _format_loan_adjustment_context(
    result: loan_adjustment_tool.LoanAdjustmentResult,
) -> str:
    lines = [
        "Kết quả tool mô phỏng điều chỉnh khoản vay:",
        loan_adjustment_tool.format_result_for_rag(result),
    ]
    if result.best_observed is not None:
        best = result.best_observed
        lines.extend([
            "Phương án tốt nhất quan sát được:",
            f"- Số tiền vay: {best.loan_amount}",
            f"- Kỳ hạn: {best.term} tháng",
            f"- Xác suất vỡ nợ: {best.default_probability:.2%}",
            f"- Mức rủi ro: {best.risk_level}",
        ])
    
    if result.proposal is not None and result.status == "fallback_proposal":
        lines.append(
            "\n[HƯỚNG DẪN QUAN TRỌNG CHO AI]: Hệ thống KHÔNG tìm được khoản vay nào dưới ngưỡng tự động duyệt (40%). "
            "Các phương án trên đã KHÁC form cũ: ưu tiên tăng kỳ hạn trước; khi đã tới kỳ hạn tối đa 60 tháng thì giảm số tiền vay. "
            "Hãy trình bày đúng thay đổi của từng phương án, CẢNH BÁO rõ rằng xác suất vỡ nợ vẫn trên ngưỡng an toàn, "
            "và khuyến nghị khách hàng chỉnh form theo hướng này hoặc cải thiện hồ sơ trước khi nộp lại."
        )
    elif result.proposal is not None:
        lines.append(
            "\n[HƯỚNG DẪN QUAN TRỌNG CHO AI]: Hệ thống vừa thiết lập các phương án nộp lại đang chờ xác nhận. "
            "Bạn CÓ THỂ nộp lại khoản vay đã chọn thay khách hàng. Hãy thông báo các phương án đề xuất ở trên cho khách hàng, "
            "nêu rõ phương án nào tăng kỳ hạn và phương án nào giảm số tiền vay. "
            "Nhấn mạnh rằng hồ sơ nộp lại chỉ thay đổi số tiền vay và kỳ hạn, không sửa các số liệu khác. "
            "Hướng dẫn họ nhắn 'Đồng ý', 'Xác nhận', hoặc chọn một phương án để bạn tự động nộp đơn mới; nhắn 'Hủy' để bỏ qua. "
            "Tuyệt đối KHÔNG BẢO khách hàng tự thao tác."
        )

    return "\n".join(lines)


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
