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


def test_reapplication_faq_does_not_trigger_adjustment_tool():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common(rag_answer="Bạn có thể nộp lại sau khi cập nhật hồ sơ.")

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    find_calls = []
    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda db, user_id: find_calls.append((db, user_id))
    )

    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Tôi có thể nộp lại sau khi bị từ chối không?",
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        restore_common()

    assert result["response"] == "Bạn có thể nộp lại sau khi cập nhật hồ sơ."
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


if __name__ == "__main__":
    test_adjustment_question_stores_pending_action_without_submitting()
    test_adjustment_question_without_proposal_does_not_store_pending_action()
    test_adjustment_tool_model_error_persists_assistant_error()
    test_reapplication_faq_does_not_trigger_adjustment_tool()
    test_whitespace_rag_answer_does_not_store_pending_action()
    print("chat service loan adjustment tests passed")
