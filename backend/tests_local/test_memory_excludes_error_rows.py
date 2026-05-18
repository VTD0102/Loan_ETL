"""Rows with error=True must not appear in the window or summarize input."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import rag.memory as memory_mod
from rag.memory import load_memory


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        for arg in args:
            text = str(arg)
            if "error" in text.lower() and "false" in text.lower():
                self._items = [m for m in self._items if not getattr(m, "error", False)]
        return self

    def order_by(self, *args, **kwargs):
        if self._items and hasattr(self._items[0], "created_at"):
            self._items = sorted(self._items, key=lambda item: item.created_at, reverse=True)
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


def test_error_rows_excluded_from_window_and_summary():
    msgs = []
    for i in range(20):
        role = "user" if i % 2 == 0 else "assistant"
        content = "ERR PLACEHOLDER" if i == 3 else f"message-{i}-" + ("x" * 800)
        msgs.append(_msg(role, content, idx=i, error=(i == 3)))

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )
    db = FakeDB(msgs)

    summarize_calls = []

    def fake_summarize(db, sess, to_summarize, prev):
        summarize_calls.append(list(to_summarize))
        sess.summary = "stub"
        sess.summary_covers_until_id = to_summarize[-1].id
        sess.summary_updated_at = datetime.utcnow()
        return "stub"

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    contents = [m.content for m in ctx.recent_messages]
    assert "ERR PLACEHOLDER" not in contents, "error row leaked into window"

    assert len(summarize_calls) == 1, (
        f"expected exactly 1 summarize call, got {len(summarize_calls)}"
    )
    assert all(m.content != "ERR PLACEHOLDER" for m in summarize_calls[0]), (
        "error row leaked into summarize input"
    )


if __name__ == "__main__":
    test_error_rows_excluded_from_window_and_summary()
    print("memory excludes-error-rows test passed")
