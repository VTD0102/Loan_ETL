"""
test_router.py

Unit tests for rag.router — intent classification (keyword fast-path only).
LLM-based classification is not tested here to avoid API costs.
Run:  cd backend && python tests_local/test_router.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.router import classify_intent, needs_retrieval, VALID_INTENTS


def _assert(condition: bool, label: str):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}]: {label}")
    if not condition:
        raise AssertionError(label)


def test_greeting_fastpath():
    """Short greetings should be classified via keyword fast-path."""
    greetings = ["Xin chào", "Hello", "Hi", "Cảm ơn", "Tạm biệt", "Bạn là ai?"]
    for msg in greetings:
        intent = classify_intent(msg)
        _assert(intent == "greeting", f"'{msg}' -> greeting (got {intent})")


def test_off_topic_fastpath():
    """Short off-topic messages should be caught by keyword patterns."""
    off_topics = [
        "Thời tiết hôm nay thế nào?",
        "Bạn biết nấu ăn không?",
        "Viết code python giúp tôi",
    ]
    for msg in off_topics:
        intent = classify_intent(msg)
        _assert(intent == "off_topic", f"'{msg}' -> off_topic (got {intent})")


def test_policy_fastpath():
    """Common FAQ/policy questions should not depend on the LLM classifier."""
    cases = [
        "Tại sao đơn vay của tôi bị AUTO_REJECTED?",
        "Đơn tôi bị AUTO_REJECTED, tôi có thể yêu cầu Admin xem xét lại không?",
        "Tại sao thu nhập của tôi khá cao nhưng vẫn bị từ chối?",
        "Sau khi đơn chuyển sang AWAITING_INFO tôi cần làm gì?",
    ]
    for msg in cases:
        intent = classify_intent(msg)
        _assert(intent == "policy_question", f"'{msg}' -> policy_question (got {intent})")


def test_personalized_fastpath():
    """Questions about concrete user ML fields should be routed to personal context."""
    cases = [
        "Xác suất vỡ nợ của tôi là bao nhiêu?",
        "Hệ thống đề xuất tôi vay bao nhiêu tiền với kỳ hạn bao lâu?",
        "Điểm mạnh và điểm yếu trong hồ sơ tài chính của tôi là gì?",
        "Tại sao mức vay đề xuất của tôi lại thấp hơn số tiền tôi xin vay?",
    ]
    for msg in cases:
        intent = classify_intent(msg)
        _assert(intent == "risk_explanation", f"'{msg}' -> risk_explanation (got {intent})")


def test_clarification_fastpath():
    """Vague help messages should ask for clarification, not analyze the current loan."""
    intent = classify_intent("giúp với")
    _assert(intent == "greeting", f"'giúp với' -> greeting (got {intent})")


def test_valid_intents():
    """All defined intents should be in VALID_INTENTS."""
    expected = {"loan_inquiry", "risk_explanation", "policy_question",
                "personal_advice", "greeting", "off_topic"}
    _assert(VALID_INTENTS == expected, "VALID_INTENTS matches expected set")


def test_needs_retrieval():
    """Retrieval should be required for domain intents, not for greeting/off_topic."""
    _assert(needs_retrieval("loan_inquiry"), "loan_inquiry needs retrieval")
    _assert(needs_retrieval("risk_explanation"), "risk_explanation needs retrieval")
    _assert(needs_retrieval("policy_question"), "policy_question needs retrieval")
    _assert(needs_retrieval("personal_advice"), "personal_advice needs retrieval")
    _assert(not needs_retrieval("greeting"), "greeting skips retrieval")
    _assert(not needs_retrieval("off_topic"), "off_topic skips retrieval")


if __name__ == "__main__":
    tests = [
        test_greeting_fastpath,
        test_off_topic_fastpath,
        test_policy_fastpath,
        test_personalized_fastpath,
        test_clarification_fastpath,
        test_valid_intents,
        test_needs_retrieval,
    ]

    print("=" * 60)
    print("  Router Test Suite (keyword fast-path only)")
    print("=" * 60)

    passed = 0
    failed = 0
    for test_fn in tests:
        print(f"\n-> {test_fn.__name__}")
        try:
            test_fn()
            passed += 1
        except AssertionError:
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'=' * 60}")
    sys.exit(1 if failed else 0)
