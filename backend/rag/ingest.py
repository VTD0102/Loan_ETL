"""
One-shot script to build the Pinecone knowledge base.
Run: python -m backend.rag.ingest
"""
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

from backend.rag.config import (
    EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    PINECONE_API_KEY, PINECONE_CLOUD, PINECONE_INDEX, PINECONE_REGION,
)
from backend.core.config import settings

KNOWLEDGE_DIRS = [
    Path(__file__).parent / "knowledge",
    Path(__file__).parents[2] / "docs" / "data_dictionary",
]


def load_documents():
    # TODO: load .md files from KNOWLEDGE_DIRS
    raise NotImplementedError


def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    # TODO: return splitter.split_documents(docs)
    raise NotImplementedError


def get_embeddings():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=OPENROUTER_BASE_URL,
    )


def upsert_to_pinecone(chunks, embeddings):
    # TODO: init Pinecone, create/clear index, upsert chunks
    raise NotImplementedError


if __name__ == "__main__":
    docs = load_documents()
    chunks = split_documents(docs)
    embeddings = get_embeddings()
    upsert_to_pinecone(chunks, embeddings)
    print(f"Ingested {len(chunks)} chunks into Pinecone index '{PINECONE_INDEX}'")
