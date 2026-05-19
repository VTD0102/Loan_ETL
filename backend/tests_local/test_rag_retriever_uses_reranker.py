"""Integration tests for the RerankedRetriever wrapper + get_retriever pipeline."""
from types import SimpleNamespace

from langchain_core.runnables import Runnable

import rag.retriever as retriever_mod
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


class FakeSparseEmbed:
    def __init__(self, **kw):
        pass


class FakeClient:
    def __init__(self, **kw):
        pass


class FakeVectorStore(Runnable):
    captured_k: int | None = None

    def __init__(self, **kw):
        pass

    def as_retriever(self, **kw):
        FakeVectorStore.captured_k = kw.get("search_kwargs", {}).get("k")
        return self

    def invoke(self, input, config=None, **kw):
        return []


def _patch_retriever_module():
    """Patch all external constructors and reset the singleton.
    Returns the dict of originals so the caller can restore."""
    retriever_mod._retriever = None
    originals = {
        "qvs": retriever_mod.QdrantVectorStore,
        "qc": retriever_mod.QdrantClient,
        "fes": retriever_mod.FastEmbedSparse,
        "oe": retriever_mod.OpenAIEmbeddings,
    }
    retriever_mod.QdrantVectorStore = FakeVectorStore
    retriever_mod.QdrantClient = FakeClient
    retriever_mod.FastEmbedSparse = FakeSparseEmbed
    retriever_mod.OpenAIEmbeddings = lambda **kw: object()
    return originals


def _unpatch_retriever_module(originals):
    retriever_mod.QdrantVectorStore = originals["qvs"]
    retriever_mod.QdrantClient = originals["qc"]
    retriever_mod.FastEmbedSparse = originals["fes"]
    retriever_mod.OpenAIEmbeddings = originals["oe"]
    retriever_mod._retriever = None


def test_get_retriever_requests_candidate_k_from_hybrid():
    """Hybrid retriever should be asked for RERANKER_CANDIDATE_K candidates."""
    from core.config import settings
    originals = _patch_retriever_module()
    try:
        retriever_mod.get_retriever()
    finally:
        _unpatch_retriever_module(originals)

    assert FakeVectorStore.captured_k == settings.rag_reranker_candidate_k


def test_get_retriever_chain_is_parent_of_reranked_of_hybrid():
    """Pipeline must be ParentDocumentRetriever wrapping RerankedRetriever wrapping hybrid."""
    from rag.retriever import ParentDocumentRetriever, RerankedRetriever
    originals = _patch_retriever_module()
    try:
        r = retriever_mod.get_retriever()
    finally:
        _unpatch_retriever_module(originals)

    assert isinstance(r, ParentDocumentRetriever)
    assert isinstance(r.child_retriever, RerankedRetriever)


def test_get_retriever_respects_reranker_disabled():
    """When rag_reranker_enabled=False, RerankedRetriever has reranker=None."""
    from rag.retriever import RerankedRetriever
    from rag import config as rag_config
    from core.config import settings

    original_enabled = rag_config.RERANKER_ENABLED
    rag_config.RERANKER_ENABLED = False

    # Reset reranker singleton too so the next get_reranker() respects the new flag.
    import rag.reranker as reranker_mod
    original_singleton = reranker_mod._singleton
    reranker_mod._singleton = None

    originals = _patch_retriever_module()
    try:
        r = retriever_mod.get_retriever()
        rr = r.child_retriever
        assert isinstance(rr, RerankedRetriever)
        assert rr.reranker is None
    finally:
        _unpatch_retriever_module(originals)
        rag_config.RERANKER_ENABLED = original_enabled
        reranker_mod._singleton = original_singleton


if __name__ == "__main__":
    test_reranked_retriever_passthrough_when_reranker_is_none()
    test_reranked_retriever_uses_reranker_when_provided()
    test_reranked_retriever_falls_back_on_rerank_failure()
    test_get_retriever_requests_candidate_k_from_hybrid()
    test_get_retriever_chain_is_parent_of_reranked_of_hybrid()
    test_get_retriever_respects_reranker_disabled()
    print("rag retriever uses reranker tests passed")
