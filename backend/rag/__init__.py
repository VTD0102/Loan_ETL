"""RAG package exports for CreditIntel."""

_EXPORTS = {
    "build_user_context": ("rag.context_builder", "build_user_context"),
    "get_chain": ("rag.chain", "get_chain"),
    "get_embeddings": ("rag.ingest", "get_embeddings"),
    "get_retriever": ("rag.retriever", "get_retriever"),
    "invoke": ("rag.chain", "invoke"),
    "load_memory": ("rag.memory", "load_memory"),
    "load_documents": ("rag.ingest", "load_documents"),
    "split_documents": ("rag.ingest", "split_documents"),
    "upsert_to_qdrant": ("rag.ingest", "upsert_to_qdrant"),
    # Routing
    "classify_intent": ("rag.router", "classify_intent"),
    "needs_retrieval": ("rag.router", "needs_retrieval"),
    # Guardrails
    "check_input": ("rag.guardrails", "check_input"),
    "check_output": ("rag.guardrails", "check_output"),
    # Personalization
    "build_personalization": ("rag.personalizer", "build_personalization"),
    "get_intent_instructions": ("rag.personalizer", "get_intent_instructions"),
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
