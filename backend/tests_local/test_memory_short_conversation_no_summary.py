"""Short conversation under the token budget -> no summary triggered."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages):
        self._messages = messages
        self.committed = 0

    def query(self, model):
        from models.chat import ChatMessage

        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        self.committed += 1


def _msg(role, content, error=False, idx=0):
    return SimpleNamespace(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=error,
        created_at=datetime.utcnow() + timedelta(seconds=idx),
    )


def test_short_conversation_returns_all_messages_no_summary():
    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )
    messages = [
        _msg("user", "Xin chào", idx=0),
        _msg("assistant", "Chào bạn, tôi giúp gì được?", idx=1),
        _msg("user", "Tôi muốn vay 50 triệu", idx=2),
    ]
    db = FakeDB(messages)

    ctx = load_memory(db, session)

    assert ctx.summary is None
    assert len(ctx.recent_messages) == 3
    assert isinstance(ctx.recent_messages[0], HumanMessage)
    assert ctx.recent_messages[0].content == "Xin chào"
    assert isinstance(ctx.recent_messages[1], AIMessage)
    assert ctx.recent_messages[2].content == "Tôi muốn vay 50 triệu"
    assert db.committed == 0, "no commit when no summarization needed"


if __name__ == "__main__":
    test_short_conversation_returns_all_messages_no_summary()
    print("memory short-conversation test passed")
