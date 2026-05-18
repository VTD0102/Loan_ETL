"""Exception hierarchy for the RAG pipeline.

Catching ``RAGError`` covers any RAG-layer failure (retrieval, LLM, timeout).
Catch a specific subclass when you want to handle a single failure mode.
"""


class RAGError(Exception):
    """Base exception for RAG pipeline failures."""


class RetrievalError(RAGError):
    """Qdrant or embedding service failure."""


class LLMError(RAGError):
    """OpenRouter / LLM call failure."""


class RAGTimeoutError(RAGError):
    """Upstream call exceeded its timeout budget."""
