"""Conversation-aware RAG query rewriter tests."""

import sys
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import rag.query_rewriter as query_rewriter


class FakeRewriteLLM:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(content=self.response)


def _patch_llm(fake_llm):
    original_get = query_rewriter._get_rewrite_llm
    query_rewriter._get_rewrite_llm = lambda: fake_llm

    def restore():
        query_rewriter._get_rewrite_llm = original_get

    return restore


def test_no_memory_returns_original_without_llm_call():
    original_get = query_rewriter._get_rewrite_llm
    query_rewriter._get_rewrite_llm = lambda: (_ for _ in ()).throw(
        AssertionError("rewrite LLM should not be loaded without memory")
    )
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "DTI là gì?",
            [],
            conversation_summary=None,
        )
    finally:
        query_rewriter._get_rewrite_llm = original_get

    assert result == "DTI là gì?"


def test_follow_up_with_memory_rewrites_to_standalone_query():
    fake_llm = FakeRewriteLLM(
        "Với hồ sơ vay bị từ chối khoản vay 50 triệu kỳ hạn 12 tháng, kỳ hạn nào có thể giúp tăng khả năng được duyệt?"
    )
    restore = _patch_llm(fake_llm)
    history = [
        HumanMessage(content="Tôi bị từ chối khoản vay 50 triệu kỳ hạn 12 tháng."),
        AIMessage(content="Bạn có thể thử kỳ hạn dài hơn để giảm áp lực trả nợ."),
    ]
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "vậy kỳ hạn nào tốt hơn?",
            history,
            conversation_summary="Khách đang hỏi về khoản vay bị AUTO_REJECTED.",
        )
    finally:
        restore()

    assert result.startswith("Với hồ sơ vay bị từ chối")
    assert "kỳ hạn nào" in result
    assert len(fake_llm.calls) == 1
    rendered_prompt = str(fake_llm.calls[0])
    assert "vậy kỳ hạn nào tốt hơn?" in rendered_prompt
    assert "AUTO_REJECTED" in rendered_prompt
    assert "Tôi bị từ chối khoản vay 50 triệu" in rendered_prompt


def test_blank_rewrite_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM("   ")
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "vì sao vậy?",
            [HumanMessage(content="DTI của tôi cao.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "vì sao vậy?"


def test_llm_error_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM(raises=RuntimeError("rewrite model unavailable"))
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "vì sao vậy?",
            [HumanMessage(content="Hồ sơ bị từ chối vì DTI cao.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "vì sao vậy?"


def test_overlong_rewrite_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM("a" * 501)
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "còn gì nữa?",
            [HumanMessage(content="Tôi muốn biết cách cải thiện hồ sơ vay.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "còn gì nữa?"


def test_multiline_or_labeled_rewrite_falls_back_to_original_question():
    fake_llm = FakeRewriteLLM("Query:\nKỳ hạn nào tốt hơn cho hồ sơ bị từ chối?")
    restore = _patch_llm(fake_llm)
    try:
        result = query_rewriter.rewrite_for_retrieval(
            "kỳ hạn nào?",
            [HumanMessage(content="Tôi bị từ chối khoản vay 50 triệu.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert result == "kỳ hạn nào?"


if __name__ == "__main__":
    test_no_memory_returns_original_without_llm_call()
    test_follow_up_with_memory_rewrites_to_standalone_query()
    test_blank_rewrite_falls_back_to_original_question()
    test_llm_error_falls_back_to_original_question()
    test_overlong_rewrite_falls_back_to_original_question()
    test_multiline_or_labeled_rewrite_falls_back_to_original_question()
    print("rag query rewriter tests passed")
