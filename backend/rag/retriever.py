import logging
import time
from threading import Lock

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from rag.chunking import expand_child_documents_to_parents
from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
    RERANKER_CANDIDATE_K, RERANKER_TOP_K, TOP_K,
)
from rag.reranker import get_reranker
from core.config import settings

logger = logging.getLogger(__name__)

# Observability counters for rerank fallback. Read via get_rerank_fallback_count().
_rerank_fallback_count = 0
_rerank_call_count = 0


def get_rerank_stats() -> dict:
    """Return cumulative rerank stats since process start.

    Useful for /admin or a simple liveness endpoint to surface silent
    reranker degradation. Reset on process restart.
    """
    return {
        "rerank_calls": _rerank_call_count,
        "rerank_fallbacks": _rerank_fallback_count,
        "fallback_rate": (
            _rerank_fallback_count / _rerank_call_count
            if _rerank_call_count else 0.0
        ),
    }


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

        global _rerank_call_count, _rerank_fallback_count
        _rerank_call_count += 1
        try:
            return self.reranker.rerank(query, candidates, self.top_k)
        except Exception as exc:
            _rerank_fallback_count += 1
            logger.warning(
                "Reranker failed (fallback %d/%d), returning raw candidates: %s",
                _rerank_fallback_count, _rerank_call_count,
                exc,
            )
            return candidates[: self.top_k]

    def get_relevant_documents(self, query):
        return self.invoke(query)


class SelfHealingHybridRetriever:
    """A hybrid retriever wrapper that acts as a placeholder when Qdrant is offline.
    It periodically retries to establish a connection to Qdrant in the background,
    enabling self-healing once the Qdrant service is started.
    """
    def __init__(self, embeddings, sparse_embeddings):
        self.embeddings = embeddings
        self.sparse_embeddings = sparse_embeddings
        self.real_retriever = None
        self.last_attempt_time = time.time()  # Start cooldown from initialization
        self.cooldown = 60.0  # seconds

    def _try_init_real_retriever(self) -> bool:
        now = time.time()
        if now - self.last_attempt_time < self.cooldown:
            return False

        self.last_attempt_time = now
        try:
            logger.info("Attempting to reconnect to Qdrant...")
            client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
                timeout=settings.rag_qdrant_timeout_seconds,
            )
            # Fetch collections to verify connectivity
            client.get_collections()

            vectorstore = QdrantVectorStore(
                client=client,
                collection_name=QDRANT_COLLECTION,
                embedding=self.embeddings,
                sparse_embedding=self.sparse_embeddings,
                retrieval_mode=RetrievalMode.HYBRID,
                vector_name="dense",
                sparse_vector_name="sparse",
            )
            self.real_retriever = vectorstore.as_retriever(search_kwargs={"k": RERANKER_CANDIDATE_K})
            logger.info("Successfully reconnected to Qdrant and initialized vector store.")
            return True
        except Exception as exc:
            logger.debug("Qdrant reconnection attempt failed: %s", exc)
            return False

    def invoke(self, query, *args, **kwargs):
        if self.real_retriever is None:
            self._try_init_real_retriever()

        if self.real_retriever is not None:
            try:
                if hasattr(self.real_retriever, "invoke"):
                    return self.real_retriever.invoke(query, *args, **kwargs)
                return self.real_retriever.get_relevant_documents(query, *args, **kwargs)
            except Exception as exc:
                logger.warning("Qdrant retrieval failed during call: %s. Resetting retriever.", exc)
                self.real_retriever = None

        return []

    def get_relevant_documents(self, query, *args, **kwargs):
        return self.invoke(query, *args, **kwargs)


_retriever_lock = Lock()
_retriever = None


def get_retriever():
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                embeddings = OpenAIEmbeddings(
                    model=EMBEDDING_MODEL,
                    openai_api_key=settings.openrouter_api_key,
                    openai_api_base=OPENROUTER_BASE_URL,
                    timeout=settings.rag_embedding_timeout_seconds,
                    max_retries=settings.rag_embedding_max_retries,
                )
                retrieval_mode = RetrievalMode.HYBRID
                sparse_embeddings = None
                try:
                    sparse_embeddings = FastEmbedSparse(model_name=BM25_SPARSE_MODEL)
                except Exception as exc:
                    retrieval_mode = RetrievalMode.DENSE
                    logger.warning(
                        "Sparse BM25 embeddings unavailable; falling back to dense retrieval: %s",
                        exc,
                    )
                client = QdrantClient(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY,
                    timeout=settings.rag_qdrant_timeout_seconds,
                )
                vectorstore_kwargs = {
                    "client": client,
                    "collection_name": QDRANT_COLLECTION,
                    "embedding": embeddings,
                    "retrieval_mode": retrieval_mode,
                    "vector_name": "dense",
                }
                if sparse_embeddings is not None:
                    vectorstore_kwargs.update(
                        {
                            "sparse_embedding": sparse_embeddings,
                            "sparse_vector_name": "sparse",
                        }
                    )
                vectorstore = QdrantVectorStore(**vectorstore_kwargs)
                base_retriever = vectorstore.as_retriever(
                    search_kwargs={"k": RERANKER_CANDIDATE_K}
                )
                reranked = RerankedRetriever(
                    base_retriever,
                    reranker=get_reranker(),
                    top_k=RERANKER_TOP_K,
                )
                _retriever = ParentDocumentRetriever(reranked, max_parent_docs=TOP_K)
    return _retriever
