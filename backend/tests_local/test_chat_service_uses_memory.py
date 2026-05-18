"""chat_service.send must pass rag.memory output into _rag_invoke."""
import uuid
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession
from rag.memory import MemoryContext


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
        return 0

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


def test_chat_service_passes_summary_and_window_to_rag():
    user = SimpleNamespace(id=uuid.uuid4(), email="b@b.com", username="Mai")
    db = FakeDB(user)

    rag_call = {}

    def fake_invoke(question, context, chat_history, **kwargs):
        rag_call["question"] = question
        rag_call["chat_history"] = list(chat_history)
        rag_call["conversation_summary"] = kwargs.get("conversation_summary")
        return {"answer": "OK", "source_documents": []}

    def fake_load_memory(db, session):
        return MemoryContext(
            summary="Khách đã hỏi vay 30tr hôm trước.",
            recent_messages=[HumanMessage(content="câu hỏi cũ")],
        )

    def fake_build_user_context(db, user_id):
        return "ctx"

    original_invoke = chat_service._rag_invoke
    original_load_memory = chat_service.load_memory
    original_ctx = chat_service.build_user_context
    chat_service._rag_invoke = fake_invoke
    chat_service.load_memory = fake_load_memory
    chat_service.build_user_context = fake_build_user_context
    try:
        result = chat_service.send(db, "b@b.com", "Tôi muốn vay 50tr")
    finally:
        chat_service._rag_invoke = original_invoke
        chat_service.load_memory = original_load_memory
        chat_service.build_user_context = original_ctx

    assert result["response"] == "OK"
    assert rag_call["conversation_summary"] == "Khách đã hỏi vay 30tr hôm trước."
    assert len(rag_call["chat_history"]) == 1
    assert rag_call["chat_history"][0].content == "câu hỏi cũ"


if __name__ == "__main__":
    test_chat_service_passes_summary_and_window_to_rag()
    print("chat_service uses memory test passed")
