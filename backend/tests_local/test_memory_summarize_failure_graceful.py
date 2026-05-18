"""If _summarize raises, load_memory keeps old summary and returns the window."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.exceptions import LLMError
from rag.memory import load_memory
from sqlalchemy.exc import SQLAlchemyError


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        if self._items and hasattr(self._items[0], "created_at"):
            self._items = sorted(self._items, key=lambda item: item.created_at, reverse=True)
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, messages, fail_commit=False):
        self._messages = messages
        self.committed = 0
        self.rolled_back = 0
        self.fail_commit = fail_commit

    def query(self, model):
        from models.chat import ChatMessage

        if model is ChatMessage:
            return FakeQuery(list(self._messages))
        return FakeQuery([])

    def commit(self):
        if self.fail_commit:
            raise SQLAlchemyError("database unavailable")
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


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


def test_summary_commit_failure_rolls_back_in_memory_state():
    msgs = [_msg("user" if i % 2 == 0 else "assistant", "c" * 800, idx=i) for i in range(20)]
    previous_updated_at = datetime.utcnow() - timedelta(minutes=1)
    previous_cover_id = uuid.uuid4()
    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary="OLD SUMMARY",
        summary_covers_until_id=previous_cover_id,
        summary_updated_at=previous_updated_at,
    )
    db = FakeDB(msgs, fail_commit=True)

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            return SimpleNamespace(content="NEW SUMMARY")

    import langchain_openai

    original_chat_openai = langchain_openai.ChatOpenAI
    langchain_openai.ChatOpenAI = FakeChatOpenAI
    try:
        ctx = load_memory(db, session)
    finally:
        langchain_openai.ChatOpenAI = original_chat_openai

    assert ctx.summary == "OLD SUMMARY"
    assert session.summary == "OLD SUMMARY"
    assert session.summary_covers_until_id == previous_cover_id
    assert session.summary_updated_at == previous_updated_at
    assert db.rolled_back == 1


if __name__ == "__main__":
    test_summary_llm_failure_returns_old_summary()
    test_summary_commit_failure_rolls_back_in_memory_state()
    print("memory summary-failure-graceful test passed")
