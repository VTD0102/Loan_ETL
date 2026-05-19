import logging

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from rag.chunking import expand_child_documents_to_parents
from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
    RERANKER_CANDIDATE_K, TOP_K,
)
from rag.reranker import get_reranker
from core.config import settings

logger = logging.getLogger(__name__)


class ParentDocumentRetriever:
    """Search child chunks, return de-duplicated parent documents."""

    def __init__(self, child_retriever, max_parent_docs: int):
        self.child_retriever = child_retriever
        self.max_parent_docs = max_parent_docs

    def invoke(self, query):
        if hasattr(self.child_retriever, "invoke"):
            child_docs = self.child_retriever.invoke(query)
        else:
            child_docs = self.child_retriever.get_relevant_documents(query)
        return expand_child_documents_to_parents(
            child_docs,
            max_parent_docs=self.max_parent_docs,
        )

    def get_relevant_documents(self, query):
        return self.invoke(query)


class RerankedRetriever:
    """Pulls candidates from base_retriever; if a reranker is provided,
    scores+sorts via reranker; otherwise pure slice to top_k.

    Any reranker exception is caught and we fall back to the raw
    candidate slice — never let a reranker failure break retrieval.
    """

    def __init__(self, base_retriever, reranker, top_k: int):
        self.base_retriever = base_retriever
        self.reranker = reranker
        self.top_k = top_k

    def invoke(self, query):
        if hasattr(self.base_retriever, "invoke"):
            candidates = self.base_retriever.invoke(query)
        else:
            candidates = self.base_retriever.get_relevant_documents(query)

        if self.reranker is None:
            return candidates[: self.top_k]

        try:
            return self.reranker.rerank(query, candidates, self.top_k)
        except Exception:
            logger.exception("Reranker failed, falling back to candidates")
            return candidates[: self.top_k]

    def get_relevant_documents(self, query):
        return self.invoke(query)


_retriever = None


def get_retriever():
    global _retriever
    if _retriever is None:
        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            timeout=settings.rag_embedding_timeout_seconds,
            max_retries=settings.rag_embedding_max_retries,
        )
        sparse_embeddings = FastEmbedSparse(model_name=BM25_SPARSE_MODEL)
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=settings.rag_qdrant_timeout_seconds,
        )
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )
        hybrid = vectorstore.as_retriever(search_kwargs={"k": RERANKER_CANDIDATE_K})
        reranked = RerankedRetriever(hybrid, reranker=get_reranker(), top_k=TOP_K * 3)
        _retriever = ParentDocumentRetriever(reranked, max_parent_docs=TOP_K)
    return _retriever
