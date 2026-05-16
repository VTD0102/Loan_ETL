"""
One-shot script to build the Qdrant knowledge base.
Run: python -m backend.rag.ingest
"""
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
)
from core.config import settings

KNOWLEDGE_DIRS = [
    Path(__file__).parent / "knowledge",
    Path(__file__).parents[2] / "docs" / "data_dictionary",
]


def load_documents():
    docs = []
    for directory in KNOWLEDGE_DIRS:
        if not directory.exists():
            continue
        loader = DirectoryLoader(
            str(directory),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        loaded = loader.load()
        for doc in loaded:
            doc.metadata["source"] = Path(doc.metadata["source"]).name
        docs.extend(loaded)
    return docs


def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    return splitter.split_documents(docs)


def get_embeddings():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=OPENROUTER_BASE_URL,
    )


def upsert_to_qdrant(chunks, embeddings):
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    if client.collection_exists(collection_name=QDRANT_COLLECTION):
        client.delete_collection(collection_name=QDRANT_COLLECTION)

    QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        collection_name=QDRANT_COLLECTION,
    )


if __name__ == "__main__":
    docs = load_documents()
    chunks = split_documents(docs)
    embeddings = get_embeddings()
    upsert_to_qdrant(chunks, embeddings)
    print(f"Ingested {len(chunks)} chunks into Qdrant collection '{QDRANT_COLLECTION}'")
