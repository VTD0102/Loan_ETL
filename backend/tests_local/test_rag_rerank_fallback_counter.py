"""Verify reranker fallback counter increments on failure."""
from types import SimpleNamespace

import rag.retriever as retriever_mod
from rag.retriever import RerankedRetriever, get_rerank_stats


def _reset_counters():
    retriever_mod._rerank_call_count = 0
    retriever_mod._rerank_fallback_count = 0


def test_counter_zero_before_any_call():
    _reset_counters()
    stats = get_rerank_stats()
    assert stats["rerank_calls"] == 0
    assert stats["rerank_fallbacks"] == 0
    assert stats["fallback_rate"] == 0.0


def test_counter_increments_on_success_and_failure():
    _reset_counters()

    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(5)]

    class FlakyReranker:
        def __init__(self):
            self.calls = 0

        def rerank(self, query, docs, top_k):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("transient error")
            return docs[:top_k]

    rr = RerankedRetriever(FakeBase(), reranker=FlakyReranker(), top_k=3)
    rr.invoke("q1")  # success
    rr.invoke("q2")  # fails -> fallback
    rr.invoke("q3")  # success

    stats = get_rerank_stats()
    assert stats["rerank_calls"] == 3
    assert stats["rerank_fallbacks"] == 1
    assert abs(stats["fallback_rate"] - 1 / 3) < 1e-6


def test_counter_not_incremented_when_reranker_is_none():
    _reset_counters()

    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(5)]

    rr = RerankedRetriever(FakeBase(), reranker=None, top_k=3)
    rr.invoke("q1")
    rr.invoke("q2")

    stats = get_rerank_stats()
    assert stats["rerank_calls"] == 0
    assert stats["rerank_fallbacks"] == 0


if __name__ == "__main__":
    test_counter_zero_before_any_call()
    test_counter_increments_on_success_and_failure()
    test_counter_not_incremented_when_reranker_is_none()
    print("rerank fallback counter tests passed")
