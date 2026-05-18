"""Verify rough char-based token estimation in rag.memory."""
from rag.memory import _estimate_tokens


def test_empty_string():
    assert _estimate_tokens("") == 0


def test_short_text():
    # "Hello world" is 11 chars -> 11 // 4 = 2
    assert _estimate_tokens("Hello world") == 2


def test_long_text():
    text = "a" * 1000
    assert _estimate_tokens(text) == 250


def test_handles_unicode():
    # Vietnamese with diacritics, all characters count by char length.
    text = "Xin chào, tôi muốn vay 100 triệu"
    assert _estimate_tokens(text) == len(text) // 4


if __name__ == "__main__":
    test_empty_string()
    test_short_text()
    test_long_text()
    test_handles_unicode()
    print("memory token estimation tests passed")
