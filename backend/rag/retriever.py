from langchain_community.vectorstores import Pinecone as PineconeVectorStore
from langchain_openai import OpenAIEmbeddings

from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL, PINECONE_INDEX, TOP_K,
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
        vectorstore = PineconeVectorStore.from_existing_index(
            index_name=PINECONE_INDEX,
            embedding=embeddings,
        )
        _retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
    return _retriever
