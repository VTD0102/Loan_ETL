"""Verify ingest CLI flags: --dry-run skips upsert, --recreate calls delete."""
import sys

from langchain_core.documents import Document

import rag.ingest as ingest


_calls = {"delete": 0, "upsert": 0, "embeddings": 0}


def _fake_load_documents():
    return [Document(page_content="# Fake\n\nhello", metadata={"source": "/tmp/fake.md"})]


def _fake_split_documents(docs):
    return docs


def _fake_get_embeddings():
    _calls["embeddings"] += 1
    return object()


def _fake_upsert(chunks, embeddings, collection_name, recreate):
    _calls["upsert"] += 1
    _calls["recreate"] = recreate
    _calls["collection"] = collection_name


def _run_main(argv):
    original_argv = sys.argv
    sys.argv = argv
    try:
        ingest.main()
    finally:
        sys.argv = original_argv


def test_dry_run_skips_upsert():
    _calls.update({"delete": 0, "upsert": 0, "embeddings": 0})
    original_load = ingest.load_documents
    original_split = ingest.split_documents
    original_emb = ingest.get_embeddings
    original_upsert = ingest.upsert_to_qdrant
    ingest.load_documents = _fake_load_documents
    ingest.split_documents = _fake_split_documents
    ingest.get_embeddings = _fake_get_embeddings
    ingest.upsert_to_qdrant = _fake_upsert
    try:
        _run_main(["ingest", "--dry-run"])
    finally:
        ingest.load_documents = original_load
        ingest.split_documents = original_split
        ingest.get_embeddings = original_emb
        ingest.upsert_to_qdrant = original_upsert

    assert _calls["upsert"] == 0, "dry-run must not call upsert"
    assert _calls["embeddings"] == 0, "dry-run must not initialise embeddings"


def test_default_upsert_no_recreate():
    _calls.update({"delete": 0, "upsert": 0, "embeddings": 0})
    original_load = ingest.load_documents
    original_split = ingest.split_documents
    original_emb = ingest.get_embeddings
    original_upsert = ingest.upsert_to_qdrant
    ingest.load_documents = _fake_load_documents
    ingest.split_documents = _fake_split_documents
    ingest.get_embeddings = _fake_get_embeddings
    ingest.upsert_to_qdrant = _fake_upsert
    try:
        _run_main(["ingest"])
    finally:
        ingest.load_documents = original_load
        ingest.split_documents = original_split
        ingest.get_embeddings = original_emb
        ingest.upsert_to_qdrant = original_upsert

    assert _calls["upsert"] == 1
    assert _calls["recreate"] is False


def test_recreate_flag_sets_recreate_true():
    _calls.update({"delete": 0, "upsert": 0, "embeddings": 0})
    original_load = ingest.load_documents
    original_split = ingest.split_documents
    original_emb = ingest.get_embeddings
    original_upsert = ingest.upsert_to_qdrant
    ingest.load_documents = _fake_load_documents
    ingest.split_documents = _fake_split_documents
    ingest.get_embeddings = _fake_get_embeddings
    ingest.upsert_to_qdrant = _fake_upsert
    try:
        _run_main(["ingest", "--recreate"])
    finally:
        ingest.load_documents = original_load
        ingest.split_documents = original_split
        ingest.get_embeddings = original_emb
        ingest.upsert_to_qdrant = original_upsert

    assert _calls["upsert"] == 1
    assert _calls["recreate"] is True


if __name__ == "__main__":
    test_dry_run_skips_upsert()
    test_default_upsert_no_recreate()
    test_recreate_flag_sets_recreate_true()
    print("rag ingest CLI tests passed")
