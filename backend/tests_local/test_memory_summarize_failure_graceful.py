"""If _summarize raises, load_memory keeps old summary and returns the window."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.exceptions import LLMError
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


def _msg(role, content, idx=0):
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=False,
        created_at=datetime.utcnow() + timedelta(seconds=idx),
    )


def test_summary_llm_failure_returns_old_summary():
    msgs = [_msg("user" if i % 2 == 0 else "assistant", "z" * 800, idx=i) for i in range(20)]
    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary="OLD SUMMARY",
        summary_covers_until_id=None,
        summary_updated_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db = FakeDB(msgs)

    def fake_summarize(*args, **kwargs):
        raise LLMError("openrouter down")

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    assert ctx.summary == "OLD SUMMARY", "old summary must be preserved on failure"
    assert len(ctx.recent_messages) > 0, "window must still be returned"
    assert session.summary == "OLD SUMMARY", "session.summary must not be cleared"
    assert db.committed == 0, "failed summary update must not commit"


if __name__ == "__main__":
    test_summary_llm_failure_returns_old_summary()
    print("memory summary-failure-graceful test passed")
