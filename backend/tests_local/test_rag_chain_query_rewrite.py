"""Verify RAG chain uses rewritten queries only for retrieval."""

import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import rag.chain as chain


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return [
            Document(
                page_content="Kỳ hạn dài hơn có thể giảm DTI và rủi ro trả nợ.",
                metadata={"source": "policy.md", "section_title": "Kỳ hạn vay"},
            )
        ]


class FakeChain:
    def __init__(self):
        self.payloads = []

    def invoke(self, payload):
        self.payloads.append(payload)
        return "Bạn có thể cân nhắc kỳ hạn dài hơn."


def _patch_chain(
    fake_chain,
    fake_retriever=None,
    rewrite_func=None,
    intent="personal_advice",
    needs_retrieval=True,
):
    originals = {
        "get_chain": chain.get_chain,
        "get_retriever": chain.get_retriever,
        "classify_intent": chain.classify_intent,
        "needs_retrieval": chain.needs_retrieval,
        "rewrite_for_retrieval": chain.rewrite_for_retrieval,
    }
    chain.get_chain = lambda: fake_chain
    if fake_retriever is not None:
        chain.get_retriever = lambda: fake_retriever
    chain.classify_intent = lambda question, chat_history: intent
    chain.needs_retrieval = lambda routed_intent: needs_retrieval
    if rewrite_func is not None:
        chain.rewrite_for_retrieval = rewrite_func

    def restore():
        chain.get_chain = originals["get_chain"]
        chain.get_retriever = originals["get_retriever"]
        chain.classify_intent = originals["classify_intent"]
        chain.needs_retrieval = originals["needs_retrieval"]
        chain.rewrite_for_retrieval = originals["rewrite_for_retrieval"]

    return restore


def test_chain_retrieves_with_rewritten_query_but_answers_original_question():
    fake_chain = FakeChain()
    fake_retriever = FakeRetriever()
    rewrite_calls = []
    history = [HumanMessage(content="Tôi bị từ chối khoản vay 50 triệu kỳ hạn 12 tháng.")]

    def fake_rewrite(question, chat_history, conversation_summary=None):
        rewrite_calls.append((question, list(chat_history), conversation_summary))
        return "Hồ sơ vay bị từ chối 50 triệu kỳ hạn 12 tháng nên chọn kỳ hạn nào?"

    restore = _patch_chain(fake_chain, fake_retriever, fake_rewrite)
    try:
        result = chain.invoke(
            "vậy kỳ hạn nào tốt hơn?",
            "customer context",
            history,
            conversation_summary="Khách có hồ sơ AUTO_REJECTED.",
        )
    finally:
        restore()

    assert fake_retriever.queries == [
        "Hồ sơ vay bị từ chối 50 triệu kỳ hạn 12 tháng nên chọn kỳ hạn nào?"
    ]
    assert fake_chain.payloads[0]["question"] == "vậy kỳ hạn nào tốt hơn?"
    assert "Kỳ hạn dài hơn" in fake_chain.payloads[0]["context"]
    assert rewrite_calls == [
        (
            "vậy kỳ hạn nào tốt hơn?",
            history,
            "Khách có hồ sơ AUTO_REJECTED.",
        )
    ]
    assert result["answer"] == "Bạn có thể cân nhắc kỳ hạn dài hơn."
    assert result["retrieval_query"] == "Hồ sơ vay bị từ chối 50 triệu kỳ hạn 12 tháng nên chọn kỳ hạn nào?"
    assert len(result["source_documents"]) == 1


def test_chain_skips_rewriter_for_non_retrieval_intent():
    fake_chain = FakeChain()
    rewrite_calls = []

    def fake_rewrite(question, chat_history, conversation_summary=None):
        rewrite_calls.append(question)
        return "should not be used"

    restore = _patch_chain(
        fake_chain,
        fake_retriever=None,
        rewrite_func=fake_rewrite,
        intent="greeting",
        needs_retrieval=False,
    )
    try:
        result = chain.invoke(
            "Xin chào",
            "customer context",
            [HumanMessage(content="Tôi hỏi về khoản vay hôm qua.")],
            conversation_summary="Khách hỏi về khoản vay.",
        )
    finally:
        restore()

    assert rewrite_calls == []
    assert fake_chain.payloads[0]["question"] == "Xin chào"
    assert fake_chain.payloads[0]["context"] == "Không tìm thấy tài liệu liên quan trong kho kiến thức."
    assert result["intent"] == "greeting"
    assert result["retrieval_query"] == "Xin chào"
    assert result["source_documents"] == []


def test_chain_falls_back_to_original_query_when_rewriter_raises():
    fake_chain = FakeChain()
    fake_retriever = FakeRetriever()

    def failing_rewrite(question, chat_history, conversation_summary=None):
        raise RuntimeError("rewrite failed")

    restore = _patch_chain(fake_chain, fake_retriever, failing_rewrite)
    try:
        result = chain.invoke(
            "vì sao vậy?",
            "customer context",
            [HumanMessage(content="DTI của tôi quá cao.")],
            conversation_summary=None,
        )
    finally:
        restore()

    assert fake_retriever.queries == ["vì sao vậy?"]
    assert fake_chain.payloads[0]["question"] == "vì sao vậy?"
    assert result["retrieval_query"] == "vì sao vậy?"


if __name__ == "__main__":
    test_chain_retrieves_with_rewritten_query_but_answers_original_question()
    test_chain_skips_rewriter_for_non_retrieval_intent()
    test_chain_falls_back_to_original_query_when_rewriter_raises()
    print("rag chain query rewrite tests passed")
