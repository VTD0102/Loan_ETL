"""
reranker.py — Cross-encoder reranker for the RAG retrieval pipeline.

Wraps fastembed.rerank.cross_encoder.TextCrossEncoder with a singleton
cache and a lazy-load constructor. Reuses fastembed already pulled in
for Stage 1 (hybrid sparse vectors).
"""
from __future__ import annotations

import logging

from rag.config import RERANKER_MODEL
logger = logging.getLogger(__name__)

_singleton: "Reranker | None" = None


class Reranker:
    """Score (query, candidate_text) pairs; return docs sorted desc, top_k."""

    def __init__(self, model_name: str = RERANKER_MODEL):
        self._model_name = model_name
        self._encoder = None  # lazy

    def _ensure_loaded(self):
        if self._encoder is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self._encoder = TextCrossEncoder(model_name=self._model_name)
        return self._encoder

    def rerank(self, query: str, docs: list, top_k: int) -> list:
        """Return docs sorted desc by relevance score, sliced to top_k.

        Empty input returns empty list (no model load).
        Exceptions propagate to caller (RerankedRetriever catches).
        """
        if not docs:
            return docs
        encoder = self._ensure_loaded()
        texts = [getattr(d, "page_content", str(d)) for d in docs]
        scores = list(encoder.rerank(query, texts))
        scored = sorted(zip(scores, docs), key=lambda t: t[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]


def get_reranker() -> "Reranker | None":
    """Singleton accessor. Returns None if rerank is disabled by config."""
    global _singleton
    from rag import config as rag_config
    if not rag_config.RERANKER_ENABLED:
        return None
    if _singleton is None:
        _singleton = Reranker()
    return _singleton
