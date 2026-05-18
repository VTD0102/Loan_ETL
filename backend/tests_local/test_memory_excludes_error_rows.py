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
    msgs = [
        _msg("user", "câu hỏi đầu", idx=0),
        _msg("assistant", "câu trả lời 1", idx=1),
        _msg("user", "câu hỏi 2", idx=2),
        _msg("assistant", "ERR PLACEHOLDER", idx=3, error=True),
        _msg("user", "câu hỏi 3", idx=4),
        _msg("assistant", "câu trả lời 3", idx=5),
    ]

    session = SimpleNamespace(
        id=uuid.uuid4(),
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
    )
    db = FakeDB(msgs)

    captured = {}

    def fake_summarize(db, sess, to_summarize, prev):
        captured["to_summarize"] = list(to_summarize)
        return "stub"

    original = memory_mod._summarize
    memory_mod._summarize = fake_summarize
    try:
        ctx = load_memory(db, session)
    finally:
        memory_mod._summarize = original

    contents = [m.content for m in ctx.recent_messages]
    assert "ERR PLACEHOLDER" not in contents, "error row leaked into window"

    if "to_summarize" in captured:
        assert all(m.content != "ERR PLACEHOLDER" for m in captured["to_summarize"]), (
            "error row leaked into summarize input"
        )


if __name__ == "__main__":
    test_error_rows_excluded_from_window_and_summary()
    print("memory excludes-error-rows test passed")
