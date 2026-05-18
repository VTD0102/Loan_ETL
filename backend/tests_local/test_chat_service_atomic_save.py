"""Verify user message persists when RAG fails, and assistant row is marked error."""
import uuid
from types import SimpleNamespace

from fastapi import HTTPException

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession
from rag.exceptions import LLMError


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def scalar(self):
        return 0  # rate-limit count = 0

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, user):
        self._user = user
        self.added = []
        self.committed = 0

    def query(self, model):
        name = getattr(model, "__name__", None)
        if name == "User":
            return FakeQuery([self._user])
        if name == "LoanApplication":
            return FakeQuery([])
        if name == "ChatMessage":
            return FakeQuery([])
        if name == "ChatSession":
            return FakeQuery([])
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def flush(self):
        for obj in self.added:
            if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self):
        self.committed += 1


def test_user_message_persists_when_rag_fails():
    user = SimpleNamespace(id=uuid.uuid4(), email="a@b.com", username="Minh")
    db = FakeDB(user)

    def fake_invoke(*args, **kwargs):
        raise LLMError("openrouter timeout")

    def fake_build_user_context(db, user_id):
        return "fake context block"

    def fake_load_memory(db, session, exclude_message_id=None):
        from rag.memory import MemoryContext

        return MemoryContext(summary=None, recent_messages=[])

    original_invoke = chat_service._rag_invoke
    original_ctx = chat_service.build_user_context
    original_load_memory = chat_service.load_memory
    chat_service._rag_invoke = fake_invoke
    chat_service.build_user_context = fake_build_user_context
    chat_service.load_memory = fake_load_memory
    try:
        raised = None
        try:
            chat_service.send(db, "a@b.com", "Tôi muốn vay 100 triệu")
        except HTTPException as exc:
            raised = exc
        assert raised is not None, "expected HTTPException"
        assert raised.status_code == 503
        assert "thử lại" in raised.detail.lower() or "sự cố" in raised.detail.lower()
    finally:
        chat_service._rag_invoke = original_invoke
        chat_service.build_user_context = original_ctx
        chat_service.load_memory = original_load_memory

    user_msgs = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "user"]
    assistant_msgs = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]

    assert len(user_msgs) == 1, "user message must persist"
    assert user_msgs[0].content == "Tôi muốn vay 100 triệu"
    assert len(assistant_msgs) == 1, "assistant placeholder must be saved"
    assert assistant_msgs[0].error is True
    assert db.committed >= 2, "expected two commits (user first, then assistant)"


if __name__ == "__main__":
    test_user_message_persists_when_rag_fails()
    print("chat_service atomic save test passed")
