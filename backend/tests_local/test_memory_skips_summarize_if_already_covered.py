"""If summary_covers_until_id already matches the old window, skip the LLM call."""
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


def _msg(role, content, idx=0):
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        sources=None,
        error=False,
        created_at=datetime.utcnow() + timedelta(seconds=idx),
    )


def test_no_summary_call_when_already_covered():
    msgs = [_msg("user" if i % 2 == 0 else "assistant", "y" * 800, idx=i) for i in range(20)]
    captured = {}

    def fake_summarize_first_run(db, session, messages_to_summarize, previous_summary):
        captured["last_id"] = messages_to_summarize[-1].id
        session.summary = "first"
        session.summary_covers_until_id = messages_to_summarize[-1].id
        session.summary_updated_at = datetime.utcnow()
        return "first"

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize_first_run
    try:
        load_memory(FakeDB(msgs), session)
    finally:
        memory_mod._summarize = original

    assert session.summary_covers_until_id == captured["last_id"]

    second_calls = []

    def fake_summarize_second_run(*args, **kwargs):
        second_calls.append(1)
        return "should not run"

    memory_mod._summarize = fake_summarize_second_run
    try:
        ctx = load_memory(FakeDB(msgs), session)
    finally:
        memory_mod._summarize = original

    assert second_calls == [], "summarize must not be called when summary already covers"
    assert ctx.summary == "first"


if __name__ == "__main__":
    test_no_summary_call_when_already_covered()
    print("memory skip-when-covered test passed")
