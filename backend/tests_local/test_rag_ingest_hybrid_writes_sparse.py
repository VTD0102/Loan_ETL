"""Verify upsert_to_qdrant writes HYBRID vectors using explicit dense/sparse slots."""
from types import SimpleNamespace

import rag.ingest as ingest


_captured = {
    "create_collection": None,
    "store_init": None,
    "store_add": None,
    "sparse_init": None,
}


class FakeSparse:
    def __init__(self, model_name):
        _captured["sparse_init"] = {"model_name": model_name}


class FakeClient:
    def __init__(self, **kwargs):
        self._exists = False

    def collection_exists(self, collection_name):
        return self._exists

    def delete_collection(self, collection_name):
        self._exists = False

    def create_collection(self, **kwargs):
        _captured["create_collection"] = kwargs
        self._exists = True


class FakeVectorStore:
    def __init__(self, **kwargs):
        _captured["store_init"] = kwargs

    def add_documents(self, chunks):
        _captured["store_add"] = list(chunks)


def _reset():
    for key in _captured:
        _captured[key] = None


def _patch():
    import langchain_qdrant
    import qdrant_client

    original = {
        "qvs": langchain_qdrant.QdrantVectorStore,
        "fes": langchain_qdrant.FastEmbedSparse,
        "qc": qdrant_client.QdrantClient,
    }
    langchain_qdrant.QdrantVectorStore = FakeVectorStore
    langchain_qdrant.FastEmbedSparse = FakeSparse
    qdrant_client.QdrantClient = FakeClient
    return original, langchain_qdrant, qdrant_client


def _unpatch(original, langchain_qdrant, qdrant_client):
    langchain_qdrant.QdrantVectorStore = original["qvs"]
    langchain_qdrant.FastEmbedSparse = original["fes"]
    qdrant_client.QdrantClient = original["qc"]


def _chunks():
    return [SimpleNamespace(page_content="x", metadata={"source": "fake.md"})]


def test_recreate_branch_creates_collection_with_named_vectors():
    _reset()
    original, lcq, qc = _patch()
    try:
        ingest.upsert_to_qdrant(_chunks(), embeddings=object(), collection_name="kb", recreate=True)
    finally:
        _unpatch(original, lcq, qc)

    create_kwargs = _captured["create_collection"]
    assert create_kwargs is not None, "create_collection must be called for recreate"
    assert create_kwargs["collection_name"] == "kb"
    assert "dense" in create_kwargs["vectors_config"]
    assert "sparse" in create_kwargs["sparse_vectors_config"]

    kwargs = _captured["store_init"]
    assert kwargs is not None, "QdrantVectorStore must be instantiated"
    assert "sparse_embedding" in kwargs
    assert isinstance(kwargs["sparse_embedding"], FakeSparse)
    assert getattr(kwargs["retrieval_mode"], "name", str(kwargs["retrieval_mode"])) == "HYBRID"
    assert kwargs.get("vector_name") == "dense"
    assert kwargs.get("sparse_vector_name") == "sparse"
    assert _captured["store_add"] is not None, "add_documents must be called"


def test_incremental_branch_uses_add_documents_with_hybrid_store():
    _reset()
    original, lcq, qc = _patch()

    # Pretend the collection already exists so the incremental branch runs.
    class FakeClientExists(FakeClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._exists = True

    qc.QdrantClient = FakeClientExists
    try:
        ingest.upsert_to_qdrant(_chunks(), embeddings=object(), collection_name="kb", recreate=False)
    finally:
        _unpatch(original, lcq, qc)

    kwargs = _captured["store_init"]
    assert kwargs is not None, "QdrantVectorStore must be instantiated"
    assert "sparse_embedding" in kwargs
    assert isinstance(kwargs["sparse_embedding"], FakeSparse)
    assert getattr(kwargs["retrieval_mode"], "name", str(kwargs["retrieval_mode"])) == "HYBRID"
    assert kwargs.get("vector_name") == "dense"
    assert kwargs.get("sparse_vector_name") == "sparse"
    assert _captured["store_add"] is not None, "add_documents must be called"


if __name__ == "__main__":
    test_recreate_branch_creates_collection_with_named_vectors()
    test_incremental_branch_uses_add_documents_with_hybrid_store()
    print("rag ingest hybrid tests passed")
