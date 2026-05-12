"""
One-shot script to build the Pinecone knowledge base.
Run: python -m backend.rag.ingest
"""
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec

from rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    PINECONE_API_KEY, PINECONE_CLOUD, PINECONE_INDEX, PINECONE_REGION,
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


def upsert_to_pinecone(chunks, embeddings):
    import os
    from langchain_pinecone import PineconeVectorStore

    os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

    pc = Pinecone(api_key=PINECONE_API_KEY)

    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX not in existing_indexes:
        pc.create_index(
            name=PINECONE_INDEX,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )

    index = pc.Index(PINECONE_INDEX)
    try:
        index.delete(delete_all=True)
    except Exception:
        pass  # index is empty (no namespace yet) — safe to skip

    PineconeVectorStore.from_documents(chunks, embeddings, index_name=PINECONE_INDEX)


if __name__ == "__main__":
    docs = load_documents()
    chunks = split_documents(docs)
    embeddings = get_embeddings()
    upsert_to_pinecone(chunks, embeddings)
    print(f"Ingested {len(chunks)} chunks into Pinecone index '{PINECONE_INDEX}'")
