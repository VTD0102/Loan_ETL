"""Build / update the Qdrant knowledge base.

Run:
    python -m rag.ingest             # incremental upsert (default)
    python -m rag.ingest --dry-run   # list docs + chunks, no writes
    python -m rag.ingest --recreate  # destructive: delete collection first
"""
import argparse
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_openai import OpenAIEmbeddings

from rag.chunking import split_documents_semantically

from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    FASTEMBED_CACHE_DIR,
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
        docs.extend(loaded)
    return docs


def split_documents(docs):
    return split_documents_semantically(docs)


def get_embeddings():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=OPENROUTER_BASE_URL,
    )


def upsert_to_qdrant(chunks, embeddings, collection_name=QDRANT_COLLECTION, recreate=False):
    from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
    from qdrant_client import QdrantClient, models

    sparse_embeddings = FastEmbedSparse(
        model_name=BM25_SPARSE_MODEL,
        cache_dir=FASTEMBED_CACHE_DIR,
    )
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    if recreate and client.collection_exists(collection_name=collection_name):
        client.delete_collection(collection_name=collection_name)

    if not client.collection_exists(collection_name=collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(size=1536, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(),
            },
        )

    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )
    store.add_documents(chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge base into Qdrant")
    parser.add_argument("--dry-run", action="store_true",
                        help="List documents & chunk count; do not call Qdrant or embeddings.")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete the collection before upsert (destructive).")
    parser.add_argument("--collection", default=QDRANT_COLLECTION,
                        help="Override the Qdrant collection name.")
    args = parser.parse_args()

    docs = load_documents()
    chunks = split_documents(docs)
    print(f"Loaded {len(docs)} documents -> {len(chunks)} chunks")

    if args.dry_run:
        for i, chunk in enumerate(chunks[:2]):
            source = chunk.metadata.get("source", "?")
            section = chunk.metadata.get("section_title", "?")
            source_type = chunk.metadata.get("source_type", "?")
            parent_id = chunk.metadata.get("parent_id", "?")
            print(f"--- Chunk {i + 1} ({source} | {source_type} | {section} | parent={parent_id}) ---")
            print(chunk.page_content[:200])
        print(f"\nDry run: would upsert {len(chunks)} chunks to '{args.collection}'")
        return

    embeddings = get_embeddings()
    if args.recreate:
        print(f"Recreating collection '{args.collection}' (destructive)")
    else:
        print(f"Upserting (incremental) to '{args.collection}'")
    upsert_to_qdrant(chunks, embeddings, collection_name=args.collection, recreate=args.recreate)
    print(f"Done. Ingested {len(chunks)} chunks.")


if __name__ == "__main__":
    main()
