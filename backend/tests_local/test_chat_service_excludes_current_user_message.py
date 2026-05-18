"""chat_service.send must exclude the current user message from memory history."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        if self._items and hasattr(self._items[0], "created_at"):
            self._items = sorted(self._items, key=lambda item: item.created_at, reverse=True)
        return self

    def limit(self, n):
        return self

    def scalar(self):
        return 0

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, user, session=None, messages=None):
        self._user = user
        self._session = session
        self._messages = list(messages or [])
        self.added = []
        self.committed = 0

    def query(self, model):
        name = getattr(model, "__name__", None)
        if name == "User":
            return FakeQuery([self._user])
        if name == "LoanApplication":
            return FakeQuery([])
        if name == "ChatMessage":
            return FakeQuery(list(self._messages))
        if name == "ChatSession":
            return FakeQuery([self._session] if self._session is not None else [])
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, ChatMessage):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.utcnow()
            self._messages.append(obj)

    def flush(self):
        for obj in self.added:
            if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self):
        self.committed += 1


def _message(session_id, role, content, idx=0):
    return SimpleNamespace(
        id=uuid.uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        sources=None,
        error=False,
        created_at=datetime.utcnow() + timedelta(seconds=idx),
    )


def test_chat_service_excludes_current_user_message_from_memory_window():
    session = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="old session",
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
        updated_at=None,
    )
    user = SimpleNamespace(id=session.user_id, email="c@d.com", username="Lan")
    db = FakeDB(
        user,
        session=session,
        messages=[
            _message(session.id, "user", "Câu hỏi trước đó", idx=0),
            _message(session.id, "assistant", "Câu trả lời trước đó", idx=1),
        ],
    )

    rag_call = {}

    def fake_invoke(question, context, chat_history, **kwargs):
        rag_call["question"] = question
        rag_call["chat_history"] = [message.content for message in chat_history]
        return {"answer": "OK", "source_documents": []}

    def fake_build_user_context(db, user_id):
        return "ctx"

    original_invoke = chat_service._rag_invoke
    original_ctx = chat_service.build_user_context
    chat_service._rag_invoke = fake_invoke
    chat_service.build_user_context = fake_build_user_context
    try:
        chat_service.send(db, "c@d.com", "Tôi muốn vay 50tr", session_id=session.id)
    finally:
        chat_service._rag_invoke = original_invoke
        chat_service.build_user_context = original_ctx

    assert rag_call["question"] == "Tôi muốn vay 50tr"
    assert "Tôi muốn vay 50tr" not in rag_call["chat_history"]
    assert rag_call["chat_history"] == ["Câu hỏi trước đó", "Câu trả lời trước đó"]


if __name__ == "__main__":
    test_chat_service_excludes_current_user_message_from_memory_window()
    print("chat_service excludes-current-user-message test passed")
