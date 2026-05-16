"""RAG package exports for CreditIntel."""

_EXPORTS = {
    "build_user_context": ("rag.context_builder", "build_user_context"),
    "get_chain": ("rag.chain", "get_chain"),
    "get_embeddings": ("rag.ingest", "get_embeddings"),
    "get_or_create_session": ("rag.memory", "get_or_create_session"),
    "get_retriever": ("rag.retriever", "get_retriever"),
    "invoke": ("rag.chain", "invoke"),
    "load_chat_history": ("rag.memory", "load_chat_history"),
    "load_documents": ("rag.ingest", "load_documents"),
    "split_documents": ("rag.ingest", "split_documents"),
    "upsert_to_qdrant": ("rag.ingest", "upsert_to_qdrant"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'rag' has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
