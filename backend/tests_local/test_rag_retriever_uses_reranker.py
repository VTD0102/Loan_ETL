"""Integration tests for the RerankedRetriever wrapper + get_retriever pipeline."""
from types import SimpleNamespace

from rag.retriever import RerankedRetriever


def test_reranked_retriever_passthrough_when_reranker_is_none():
    """reranker=None => slice candidates to top_k, preserve order."""
    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(20)]

    rr = RerankedRetriever(FakeBase(), reranker=None, top_k=12)
    out = rr.invoke("q")
    assert len(out) == 12
    assert out[0].page_content == "0"
    assert out[-1].page_content == "11"


def test_reranked_retriever_uses_reranker_when_provided():
    """reranker.rerank called with the candidates and top_k."""
    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content="a"), SimpleNamespace(page_content="b")]

    captured = {}

    class FakeReranker:
        def rerank(self, query, docs, top_k):
            captured["query"] = query
            captured["doc_count"] = len(docs)
            captured["top_k"] = top_k
            return list(reversed(docs))  # reverse to prove rerank ran

    rr = RerankedRetriever(FakeBase(), reranker=FakeReranker(), top_k=2)
    out = rr.invoke("hello")

    assert captured == {"query": "hello", "doc_count": 2, "top_k": 2}
    assert out[0].page_content == "b"  # reversed


def test_reranked_retriever_falls_back_on_rerank_failure():
    """If reranker raises, return raw candidates sliced to top_k."""
    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(5)]

    class FailingReranker:
        def rerank(self, query, docs, top_k):
            raise RuntimeError("model not loaded")

    rr = RerankedRetriever(FakeBase(), reranker=FailingReranker(), top_k=3)
    out = rr.invoke("q")
    assert len(out) == 3
    assert [d.page_content for d in out] == ["0", "1", "2"]


if __name__ == "__main__":
    test_reranked_retriever_passthrough_when_reranker_is_none()
    test_reranked_retriever_uses_reranker_when_provided()
    test_reranked_retriever_falls_back_on_rerank_failure()
    print("rag retriever uses reranker (wrapper) tests passed")
