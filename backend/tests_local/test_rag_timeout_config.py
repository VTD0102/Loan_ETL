"""Verify timeout/max_retries are propagated to LLM/embedding/Qdrant clients."""
from langchain_core.runnables import Runnable

import rag.chain as chain_mod
import rag.retriever as retriever_mod
import rag.router as router_mod
from core.config import settings


_captured = {}


class FakeChatOpenAI(Runnable):
    """Runnable stub so it composes with `chat_prompt | llm | parser`."""
    def __init__(self, **kwargs):
        _captured.setdefault("chat", []).append(kwargs)

    def invoke(self, input, config=None, **kwargs):
        return "stub"


class FakeEmbeddings:
    def __init__(self, **kwargs):
        _captured["embeddings"] = kwargs


class FakeQdrantClient:
    def __init__(self, **kwargs):
        _captured["qdrant"] = kwargs


class FakeVectorStore:
    def __init__(self, **kwargs):
        pass

    def as_retriever(self, **kwargs):
        return self


def test_chat_chain_timeout_kwargs():
    chain_mod._chain = None
    original = chain_mod.ChatOpenAI
    chain_mod.ChatOpenAI = FakeChatOpenAI
    try:
        chain_mod.get_chain()
    finally:
        chain_mod.ChatOpenAI = original
        chain_mod._chain = None

    chat_kwargs = _captured["chat"][-1]
    assert chat_kwargs["timeout"] == settings.rag_llm_timeout_seconds
    assert chat_kwargs["max_retries"] == settings.rag_llm_max_retries


def test_router_classifier_timeout_kwargs():
    router_mod._classifier_llm = None
    original = router_mod.ChatOpenAI
    router_mod.ChatOpenAI = FakeChatOpenAI
    try:
        router_mod._get_classifier_llm()
    finally:
        router_mod.ChatOpenAI = original
        router_mod._classifier_llm = None

    chat_kwargs = _captured["chat"][-1]
    assert chat_kwargs["timeout"] == settings.rag_llm_timeout_seconds
    assert chat_kwargs["max_retries"] == settings.rag_llm_max_retries


def test_retriever_timeout_kwargs():
    retriever_mod._retriever = None
    original_emb = retriever_mod.OpenAIEmbeddings
    original_client = retriever_mod.QdrantClient
    original_vs = retriever_mod.QdrantVectorStore
    retriever_mod.OpenAIEmbeddings = FakeEmbeddings
    retriever_mod.QdrantClient = FakeQdrantClient
    retriever_mod.QdrantVectorStore = FakeVectorStore
    try:
        retriever_mod.get_retriever()
    finally:
        retriever_mod.OpenAIEmbeddings = original_emb
        retriever_mod.QdrantClient = original_client
        retriever_mod.QdrantVectorStore = original_vs
        retriever_mod._retriever = None

    assert _captured["embeddings"]["timeout"] == settings.rag_embedding_timeout_seconds
    assert _captured["embeddings"]["max_retries"] == settings.rag_embedding_max_retries
    assert _captured["qdrant"]["timeout"] == settings.rag_qdrant_timeout_seconds


if __name__ == "__main__":
    test_chat_chain_timeout_kwargs()
    test_router_classifier_timeout_kwargs()
    test_retriever_timeout_kwargs()
    print("rag timeout config tests passed")
