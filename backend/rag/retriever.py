from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings

from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL, TOP_K,
)
from core.config import settings

_retriever = None


def get_retriever():
    global _retriever
    if _retriever is None:
        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
        )
        vectorstore = QdrantVectorStore.from_existing_collection(
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )
        _retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    return _retriever
