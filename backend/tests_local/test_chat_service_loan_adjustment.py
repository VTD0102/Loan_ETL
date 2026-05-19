"""Chat service orchestration for loan adjustment proposals."""

import sys
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession
from services.loan_adjustment_tool import LoanAdjustmentProposal, LoanAdjustmentResult


class FakeQuery:
    def __init__(self, items, scalar_value=0):
        self._items = list(items)
        self._scalar_value = scalar_value

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def scalar(self):
        return self._scalar_value

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, user, session=None, applications=None, messages=None):
        self._user = user
        self._session = session
        self._applications = list(applications or [])
        self._messages = list(messages or [])
        self.added = []
        self.committed = 0

    def query(self, model):
        name = getattr(model, "__name__", None)
        if name == "User":
            return FakeQuery([self._user])
        if name == "LoanApplication":
            return FakeQuery(self._applications)
        if name == "ChatSession":
            return FakeQuery([self._session] if self._session is not None else [])
        if name == "ChatMessage":
            return FakeQuery(self._messages)
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
            self._session = obj
        if isinstance(obj, ChatMessage):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.utcnow()
            self._messages.append(obj)

    def flush(self):
        if self._session is not None and getattr(self._session, "id", None) is None:
            self._session.id = uuid.uuid4()

    def commit(self):
        self.committed += 1

    def rollback(self):
        pass


def _session(user_id=None, pending_action=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        title="chat",
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
        pending_action=pending_action,
        updated_at=None,
    )


def _proposal_result(source_application_id):
    return LoanAdjustmentResult(
        status="proposal",
        source_application_id=str(source_application_id),
        current_loan_amount=Decimal("50000"),
        current_term=12,
        current_default_probability=0.55,
        proposal=LoanAdjustmentProposal(
            loan_amount=Decimal("35000"),
            term=36,
            default_probability=0.28,
            risk_level="Medium",
            risk_score=72,
            model_version="test-model",
        ),
        best_observed=None,
        message="proposal",
    )


def _source_app(app_id, user_id):
    return SimpleNamespace(
        id=app_id,
        user_id=user_id,
        status="AUTO_REJECTED",
        monthly_income=Decimal("8000"),
        loan_amount=Decimal("50000"),
        term=12,
        employment_status="Employed",
        occupation_type="Laborers",
        years_employed=Decimal("5"),
        dti=Decimal("0.35"),
        is_homeowner=False,
        listing_category="personal",
        credit_score=680,
        num_bureau_records=3,
        num_active_credit=2,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=35,
        gender_male_flag=False,
        education_ordinal=4,
        cnt_children=0,
        cnt_fam_members=2,
        is_married_flag=True,
        recommended_amount=Decimal("35000"),
        recommended_term=36,
        default_probability=Decimal("0.55"),
        risk_level="High",
        risk_score=45,
        model_version="test-model",
        feature_snapshot={},
        imputed_features=[],
    )


def _pending_action(app_id):
    action = chat_service.loan_adjustment_tool.build_pending_action(_proposal_result(app_id))
    action["created_at"] = "2026-05-19T10:00:00"
    action["expires_at"] = "2099-05-19T10:30:00"
    return action


def _patch_common(rag_answer="Đề xuất kỳ hạn 36 tháng. Bạn có muốn nộp lại với phương án này không?"):
    originals = {
        "rag": chat_service._rag_invoke,
        "ctx": chat_service.build_user_context,
        "memory": chat_service.load_memory,
        "personalization": chat_service.build_personalization,
    }
    rag_calls = []

    def fake_rag(question, context, chat_history, **kwargs):
        rag_calls.append({"question": question, "context": context, "kwargs": kwargs})
        return {"answer": rag_answer, "source_documents": []}

    def fake_memory(db, session, exclude_message_id=None):
        from rag.memory import MemoryContext

        return MemoryContext(summary=None, recent_messages=[])

    chat_service._rag_invoke = fake_rag
    chat_service.build_user_context = lambda db, user_id: "base user context"
    chat_service.load_memory = fake_memory
    chat_service.build_personalization = lambda user, app: None

    def restore():
        chat_service._rag_invoke = originals["rag"]
        chat_service.build_user_context = originals["ctx"]
        chat_service.load_memory = originals["memory"]
        chat_service.build_personalization = originals["personalization"]

    return rag_calls, restore


def test_adjustment_question_stores_pending_action_without_submitting():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    source_application_id = uuid.uuid4()
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common()

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda db, user_id: _proposal_result(source_application_id)
    )
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "proposal": {
            "loan_amount": "35000",
            "term": 36,
            "default_probability": 0.28,
            "risk_level": "Medium",
            "risk_score": 72,
            "model_version": "test-model",
        },
        "created_at": "2026-05-19T10:00:00",
        "expires_at": "2026-05-19T10:30:00",
    }

    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Tôi bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn?",
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        restore_common()

    assert result["response"].startswith("Đề xuất kỳ hạn 36 tháng")
    assert session.pending_action is not None
    assert session.pending_action["type"] == "loan_term_adjustment"
    assert session.pending_action["proposal"]["term"] == 36
    assert len(rag_calls) == 1
    assert "Kết quả tool mô phỏng điều chỉnh khoản vay" in rag_calls[0]["context"]
    assistant_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]
    assert len(assistant_messages) == 1
    assert db.committed >= 2


def test_adjustment_question_without_proposal_does_not_store_pending_action():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common(rag_answer="Chưa có phương án đủ điều kiện.")

    no_proposal = LoanAdjustmentResult(
        status="no_passing_option",
        source_application_id=str(uuid.uuid4()),
        current_loan_amount=Decimal("50000"),
        current_term=12,
        current_default_probability=0.55,
        proposal=None,
        best_observed=LoanAdjustmentProposal(
            loan_amount=Decimal("35000"),
            term=36,
            default_probability=0.43,
            risk_level="High",
            risk_score=57,
            model_version="test-model",
        ),
        message="no proposal",
    )

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    build_calls = []
    chat_service.loan_adjustment_tool.find_best_reapplication_option = lambda db, user_id: no_proposal
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: build_calls.append(result)
    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Tôi bị từ chối, đổi kỳ hạn giúp tôi",
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        restore_common()

    assert result["response"] == "Chưa có phương án đủ điều kiện."
    assert session.pending_action is None
    assert build_calls == []
    assert len(rag_calls) == 1
    assert "Phương án tốt nhất quan sát được" in rag_calls[0]["context"]


def test_direct_term_change_with_personal_help_triggers_adjustment_tool():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    source_application_id = uuid.uuid4()
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common()

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    find_calls = []

    def fake_find(db, user_id):
        find_calls.append((db, user_id))
        return _proposal_result(source_application_id)

    chat_service.loan_adjustment_tool.find_best_reapplication_option = fake_find
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "proposal": {"term": 36},
    }

    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Đổi kỳ hạn giúp tôi",
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        restore_common()

    assert result["response"].startswith("Đề xuất kỳ hạn 36 tháng")
    assert len(find_calls) == 1
    assert len(rag_calls) == 1
    assert "Kết quả tool mô phỏng điều chỉnh khoản vay" in rag_calls[0]["context"]
    assert session.pending_action is not None


def test_adjustment_tool_model_error_persists_assistant_error():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common()

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option

    def raise_model_error(db, user_id):
        raise chat_service.ml_service.ModelPredictionError("boom")

    chat_service.loan_adjustment_tool.find_best_reapplication_option = raise_model_error
    try:
        raised = None
        try:
            chat_service.send(
                db,
                "loan@example.com",
                "Tôi bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn?",
                session_id=session.id,
            )
        except HTTPException as exc:
            raised = exc
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        restore_common()

    assert raised is not None
    assert raised.status_code == 503
    assert raised.detail == chat_service._RAG_ERROR_MESSAGE
    assert rag_calls == []
    assert session.pending_action is None
    user_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "user"]
    assistant_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]
    assert len(user_messages) == 1
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == chat_service._RAG_ERROR_MESSAGE
    assert assistant_messages[0].error is True
    assert db.committed >= 2


def test_adjustment_tool_unexpected_error_persists_assistant_error():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common()

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option

    def raise_unexpected_error(db, user_id):
        raise RuntimeError("boom")

    chat_service.loan_adjustment_tool.find_best_reapplication_option = raise_unexpected_error
    try:
        raised = None
        try:
            chat_service.send(
                db,
                "loan@example.com",
                "Tôi bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn?",
                session_id=session.id,
            )
        except HTTPException as exc:
            raised = exc
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        restore_common()

    assert raised is not None
    assert raised.status_code == 503
    assert raised.detail == chat_service._RAG_ERROR_MESSAGE
    assert rag_calls == []
    assert session.pending_action is None
    user_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "user"]
    assistant_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]
    assert len(user_messages) == 1
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == chat_service._RAG_ERROR_MESSAGE
    assert assistant_messages[0].error is True


def test_adjustment_formatter_unexpected_error_persists_assistant_error():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    source_application_id = uuid.uuid4()
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common()

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    original_format = chat_service.loan_adjustment_tool.format_result_for_rag

    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda db, user_id: _proposal_result(source_application_id)
    )
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "proposal": {"term": 36},
    }

    def raise_format_error(result):
        raise RuntimeError("format boom")

    chat_service.loan_adjustment_tool.format_result_for_rag = raise_format_error
    try:
        raised = None
        try:
            chat_service.send(
                db,
                "loan@example.com",
                "Tôi bị từ chối, đổi kỳ hạn giúp tôi",
                session_id=session.id,
            )
        except HTTPException as exc:
            raised = exc
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        chat_service.loan_adjustment_tool.format_result_for_rag = original_format
        restore_common()

    assert raised is not None
    assert raised.status_code == 503
    assert raised.detail == chat_service._RAG_ERROR_MESSAGE
    assert rag_calls == []
    assert session.pending_action is None
    assistant_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == chat_service._RAG_ERROR_MESSAGE
    assert assistant_messages[0].error is True


def test_reapplication_faq_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Tôi có thể nộp lại sau khi bị từ chối không?",
        "Bạn có thể nộp lại sau khi cập nhật hồ sơ.",
    )


def test_rejected_loan_profile_improvement_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Tôi bị từ chối, làm sao cải thiện hồ sơ vay?",
        "Bạn có thể cải thiện hồ sơ vay bằng cách bổ sung giấy tờ thu nhập.",
    )


def test_rejected_credit_score_improvement_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Tôi bị từ chối, làm sao cải thiện điểm tín dụng?",
        "Bạn có thể cải thiện điểm tín dụng bằng cách thanh toán đúng hạn.",
    )


def test_rejected_credit_score_adjustment_hint_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Tôi bị từ chối, gợi ý điều chỉnh điểm tín dụng",
        "Bạn có thể cải thiện điểm tín dụng bằng cách thanh toán đúng hạn.",
    )


def test_rejected_supported_terms_faq_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Sau khi bị từ chối, kỳ hạn nào hiện được hỗ trợ?",
        "Các kỳ hạn hiện được hỗ trợ là 12, 24, 36, 48 và 60 tháng.",
    )


def test_generic_credit_score_improvement_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Làm sao cải thiện điểm tín dụng?",
        "Bạn có thể cải thiện điểm tín dụng bằng cách thanh toán đúng hạn.",
    )


def test_generic_loan_profile_improvement_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Làm sao cải thiện hồ sơ vay?",
        "Bạn có thể cải thiện hồ sơ vay bằng cách bổ sung giấy tờ thu nhập.",
    )


def test_supported_terms_faq_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Kỳ hạn nào hiện được hỗ trợ?",
        "Các kỳ hạn hiện được hỗ trợ là 12, 24, 36, 48 và 60 tháng.",
    )


def test_term_policy_faq_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Kỳ hạn nào ảnh hưởng đến kết quả xét duyệt?",
        "Kỳ hạn là một trong các yếu tố được xem xét trong hồ sơ vay.",
    )


def test_term_approval_chance_faq_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Kỳ hạn nào giúp tăng khả năng được duyệt?",
        "Kỳ hạn dài hơn có thể giảm áp lực trả nợ nhưng còn phụ thuộc toàn bộ hồ sơ.",
    )


def test_easier_approval_term_faq_does_not_trigger_adjustment_tool():
    _assert_message_does_not_trigger_adjustment_tool(
        "Kỳ hạn nào dễ được duyệt hơn?",
        "Khả năng được duyệt phụ thuộc vào thu nhập, DTI, lịch sử tín dụng và hồ sơ vay.",
    )


def _assert_message_does_not_trigger_adjustment_tool(message, rag_answer):
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common(rag_answer=rag_answer)

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    find_calls = []
    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda db, user_id: find_calls.append((db, user_id))
    )

    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            message,
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        restore_common()

    assert result["response"] == rag_answer
    assert find_calls == []
    assert len(rag_calls) == 1
    assert rag_calls[0]["context"] == "base user context"
    assert session.pending_action is None


def test_whitespace_rag_answer_does_not_store_pending_action():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    source_application_id = uuid.uuid4()
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common(rag_answer="   ")

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda db, user_id: _proposal_result(source_application_id)
    )
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "proposal": {"term": 36},
    }

    try:
        raised = None
        try:
            chat_service.send(
                db,
                "loan@example.com",
                "Tôi bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn?",
                session_id=session.id,
            )
        except HTTPException as exc:
            raised = exc
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        restore_common()

    assert raised is not None
    assert raised.status_code == 503
    assert raised.detail == chat_service._RAG_ERROR_MESSAGE
    assert session.pending_action is None
    assert len(rag_calls) == 1
    assistant_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == chat_service._RAG_ERROR_MESSAGE
    assert assistant_messages[0].error is True


def test_affirmative_response_confirms_pending_action_and_clears_it():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    session = _session(user.id, pending_action=_pending_action(app_id))
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common()

    original_confirm = chat_service.application_service.confirm
    confirm_payloads = []

    def fake_confirm(db, user_email, payload):
        confirm_payloads.append(payload)
        return {
            "application_id": str(uuid.uuid4()),
            "status": "PENDING_REVIEW",
            "default_probability": 0.28,
            "risk_level": "Medium",
            "risk_score": 72,
            "suggested_amount": 35000,
            "suggested_term": 36,
        }

    chat_service.application_service.confirm = fake_confirm
    try:
        result = chat_service.send(db, "loan@example.com", "đồng ý nộp lại", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "Đã nộp lại hồ sơ mới" in result["response"]
    assert session.pending_action is None
    assert len(confirm_payloads) == 1
    assert confirm_payloads[0].loan_amount == Decimal("35000")
    assert confirm_payloads[0].term == 36
    assert rag_calls == []


def test_negative_response_clears_pending_action_without_confirming():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    session = _session(user.id, pending_action=_pending_action(app_id))
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common()

    original_confirm = chat_service.application_service.confirm
    confirm_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "không, hủy giúp tôi", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "đã hủy" in result["response"].lower()
    assert session.pending_action is None
    assert confirm_calls == []
    assert rag_calls == []


def test_negated_affirmative_does_not_confirm_pending_action():
    for message in ("tôi chưa đồng ý", "đừng xác nhận"):
        user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
        app_id = uuid.uuid4()
        session = _session(user.id, pending_action=_pending_action(app_id))
        db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
        rag_calls, restore_common = _patch_common(rag_answer="Câu trả lời RAG bình thường")

        original_confirm = chat_service.application_service.confirm
        confirm_calls = []
        chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
        try:
            chat_service.send(db, "loan@example.com", message, session_id=session.id)
        finally:
            chat_service.application_service.confirm = original_confirm
            restore_common()

        assert confirm_calls == []


def test_expired_pending_action_clears_without_confirming():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    action = _pending_action(app_id)
    action["expires_at"] = "2000-01-01T00:00:00"
    session = _session(user.id, pending_action=action)
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common()

    original_confirm = chat_service.application_service.confirm
    confirm_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "đồng ý", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "hết hạn" in result["response"].lower()
    assert session.pending_action is None
    assert confirm_calls == []
    assert rag_calls == []


def test_expired_pending_action_clears_before_rag_for_non_confirmation():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    action = _pending_action(app_id)
    action["expires_at"] = "2000-01-01T00:00:00"
    session = _session(user.id, pending_action=action)
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common(rag_answer="Câu trả lời RAG bình thường")

    original_confirm = chat_service.application_service.confirm
    confirm_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "DTI là gì?", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "hết hạn" in result["response"].lower()
    assert session.pending_action is None
    assert confirm_calls == []
    assert rag_calls == []


def test_pending_adjustment_request_returns_reminder_without_overwriting_action():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    pending_action = _pending_action(app_id)
    session = _session(user.id, pending_action=pending_action)
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common(rag_answer="Câu trả lời RAG bình thường")

    original_confirm = chat_service.application_service.confirm
    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    confirm_calls = []
    find_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda *args, **kwargs: find_calls.append(args)
    )
    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Tôi bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn?",
            session_id=session.id,
        )
    finally:
        chat_service.application_service.confirm = original_confirm
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        restore_common()

    assert "đang chờ xác nhận" in result["response"].lower()
    assert session.pending_action is pending_action
    assert confirm_calls == []
    assert find_calls == []
    assert rag_calls == []


def test_pending_action_non_confirmation_keeps_existing_rag_path():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    session = _session(user.id, pending_action=_pending_action(app_id))
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common(rag_answer="Câu trả lời RAG bình thường")

    original_confirm = chat_service.application_service.confirm
    confirm_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "DTI là gì?", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert result["response"] == "Câu trả lời RAG bình thường"
    assert session.pending_action is not None
    assert confirm_calls == []
    assert len(rag_calls) == 1


if __name__ == "__main__":
    test_adjustment_question_stores_pending_action_without_submitting()
    test_adjustment_question_without_proposal_does_not_store_pending_action()
    test_direct_term_change_with_personal_help_triggers_adjustment_tool()
    test_adjustment_tool_model_error_persists_assistant_error()
    test_adjustment_tool_unexpected_error_persists_assistant_error()
    test_adjustment_formatter_unexpected_error_persists_assistant_error()
    test_reapplication_faq_does_not_trigger_adjustment_tool()
    test_rejected_loan_profile_improvement_does_not_trigger_adjustment_tool()
    test_rejected_credit_score_improvement_does_not_trigger_adjustment_tool()
    test_rejected_credit_score_adjustment_hint_does_not_trigger_adjustment_tool()
    test_rejected_supported_terms_faq_does_not_trigger_adjustment_tool()
    test_generic_credit_score_improvement_does_not_trigger_adjustment_tool()
    test_generic_loan_profile_improvement_does_not_trigger_adjustment_tool()
    test_supported_terms_faq_does_not_trigger_adjustment_tool()
    test_term_policy_faq_does_not_trigger_adjustment_tool()
    test_term_approval_chance_faq_does_not_trigger_adjustment_tool()
    test_easier_approval_term_faq_does_not_trigger_adjustment_tool()
    test_whitespace_rag_answer_does_not_store_pending_action()
    test_affirmative_response_confirms_pending_action_and_clears_it()
    test_negative_response_clears_pending_action_without_confirming()
    test_negated_affirmative_does_not_confirm_pending_action()
    test_expired_pending_action_clears_without_confirming()
    test_expired_pending_action_clears_before_rag_for_non_confirmation()
    test_pending_adjustment_request_returns_reminder_without_overwriting_action()
    test_pending_action_non_confirmation_keeps_existing_rag_path()
    print("chat service loan adjustment tests passed")
