"""Long conversation over the token budget -> summary updated, recent window kept."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
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


def _msg(role, content, idx=0, error=False):
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=error,
        created_at=datetime.utcnow() + timedelta(seconds=idx),
    )


def test_long_conversation_triggers_summary():
    # 20 messages, each 800 chars -> 20 * 200 = 4000 tokens total.
    # Budget = 2000 -> most recent ~10 in window, ~10 in older portion.
    msgs = []
    for i in range(20):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(_msg(role, "x" * 800, idx=i))

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )
    db = FakeDB(msgs)

    summarize_calls = []

    def fake_summarize(db_arg, session_arg, messages_to_summarize, previous_summary):
        summarize_calls.append({
            "count": len(messages_to_summarize),
            "previous_summary": previous_summary,
        })
        session_arg.summary = "TÓM TẮT MỚI"
        session_arg.summary_covers_until_id = messages_to_summarize[-1].id
        session_arg.summary_updated_at = datetime.utcnow()
        db_arg.commit()
        return "TÓM TẮT MỚI"

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    assert len(summarize_calls) == 1, "summarize should run once for over-budget convo"
    assert summarize_calls[0]["previous_summary"] is None
    assert summarize_calls[0]["count"] >= 6, "older portion should have >= min messages"
    assert ctx.summary == "TÓM TẮT MỚI"
    assert len(ctx.recent_messages) > 0
    assert len(ctx.recent_messages) < 20, "recent window must be strictly smaller than full history"
    assert db.committed >= 1, "summary update must commit"


if __name__ == "__main__":
    test_long_conversation_triggers_summary()
    print("memory long-conversation summarise test passed")
