from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from rag.chunking import expand_child_documents_to_parents
from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL, TOP_K,
)
from core.config import settings


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
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=settings.rag_qdrant_timeout_seconds,
        )
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
        )
        child_retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K * 3})
        _retriever = ParentDocumentRetriever(child_retriever, max_parent_docs=TOP_K)
    return _retriever
