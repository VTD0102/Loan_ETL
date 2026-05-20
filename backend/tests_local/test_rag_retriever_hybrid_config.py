"""Verify get_retriever() wires Qdrant in HYBRID mode with FastEmbedSparse."""
from langchain_core.runnables import Runnable

import rag.retriever as retriever_mod
from core.config import settings


_captured = {"vectorstore": None, "sparse": None}


class FakeSparse:
    def __init__(self, model_name):
        _captured["sparse"] = {"model_name": model_name}


class FakeQdrantClient:
    def __init__(self, **kwargs):
        pass


class FakeVectorStore(Runnable):
    def __init__(self, **kwargs):
        _captured["vectorstore"] = kwargs

    def as_retriever(self, **kwargs):
        return self

    def invoke(self, input, config=None, **kwargs):
        return []


def test_retriever_uses_hybrid_mode_with_fastembed_sparse():
    retriever_mod._retriever = None
    original_vs = retriever_mod.QdrantVectorStore
    original_client = retriever_mod.QdrantClient
    original_sparse = retriever_mod.FastEmbedSparse
    original_embeddings = retriever_mod.OpenAIEmbeddings
    retriever_mod.QdrantVectorStore = FakeVectorStore
    retriever_mod.QdrantClient = FakeQdrantClient
    retriever_mod.FastEmbedSparse = FakeSparse
    retriever_mod.OpenAIEmbeddings = lambda **kw: object()
    try:
        retriever_mod.get_retriever()
    finally:
        retriever_mod.QdrantVectorStore = original_vs
        retriever_mod.QdrantClient = original_client
        retriever_mod.FastEmbedSparse = original_sparse
        retriever_mod.OpenAIEmbeddings = original_embeddings
        retriever_mod._retriever = None

    vs_kwargs = _captured["vectorstore"]
    assert vs_kwargs is not None, "QdrantVectorStore was not instantiated"
    assert "sparse_embedding" in vs_kwargs, "sparse_embedding kwarg missing"
    assert isinstance(vs_kwargs["sparse_embedding"], FakeSparse), (
        "sparse_embedding must be a FastEmbedSparse instance"
    )
    # retrieval_mode is a RetrievalMode enum; compare via name to avoid importing the enum here.
    assert getattr(vs_kwargs["retrieval_mode"], "name", str(vs_kwargs["retrieval_mode"])) == "HYBRID"
    assert vs_kwargs.get("vector_name") == "dense"
    assert vs_kwargs.get("sparse_vector_name") == "sparse"
    assert _captured["sparse"]["model_name"] == settings.rag_bm25_model


if __name__ == "__main__":
    test_retriever_uses_hybrid_mode_with_fastembed_sparse()
    print("rag retriever hybrid config tests passed")
