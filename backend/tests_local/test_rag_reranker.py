"""Unit tests for rag.reranker.Reranker — sort + slice via mocked encoder."""
from types import SimpleNamespace

from rag.reranker import Reranker


def test_reranker_sorts_by_score_and_slices_to_top_k():
    docs = [
        SimpleNamespace(page_content="bad match"),
        SimpleNamespace(page_content="great match"),
        SimpleNamespace(page_content="ok match"),
    ]

    class FakeEncoder:
        def rerank(self, query, texts):
            # Scores aligned with texts order: bad=0.1, great=0.9, ok=0.5
            return [0.1, 0.9, 0.5]

    r = Reranker()
    r._encoder = FakeEncoder()  # bypass lazy load
    result = r.rerank("any query", docs, top_k=2)

    assert len(result) == 2
    assert result[0].page_content == "great match"
    assert result[1].page_content == "ok match"


def test_reranker_returns_empty_for_no_docs():
    r = Reranker()
    r._encoder = object()  # untouched
    assert r.rerank("q", [], top_k=5) == []


def test_reranker_lazy_loads_encoder():
    """Constructor must NOT trigger model download."""
    r = Reranker()
    assert r._encoder is None


def test_reranker_top_k_larger_than_docs_returns_all_sorted():
    docs = [
        SimpleNamespace(page_content="a"),
        SimpleNamespace(page_content="b"),
    ]

    class FakeEncoder:
        def rerank(self, query, texts):
            return [0.3, 0.7]

    r = Reranker()
    r._encoder = FakeEncoder()
    out = r.rerank("q", docs, top_k=10)
    assert len(out) == 2
    assert out[0].page_content == "b"  # higher score first


if __name__ == "__main__":
    test_reranker_sorts_by_score_and_slices_to_top_k()
    test_reranker_returns_empty_for_no_docs()
    test_reranker_lazy_loads_encoder()
    test_reranker_top_k_larger_than_docs_returns_all_sorted()
    print("rag reranker tests passed")
