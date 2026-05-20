# RAG Retrieval V1 — Hybrid (BM25 + Vector) Design

**Date**: 2026-05-19
**Status**: Approved
**Stage**: 1 of 3 in the retrieval-quality axis
- Stage 1 (this spec) — Hybrid BM25 + Vector
- Stage 2 (future) — Cross-encoder reranker
- Stage 3 (future) — Query rewriting with chat history

**Scope**: `backend/rag/retriever.py`, `backend/rag/ingest.py`, `backend/rag/config.py`, `backend/core/config.py`, `backend/requirements.txt`, `CLAUDE.md`, plus 2 new tests + 1 eval-baseline commit + 1 eval-result commit.

## Goal

Replace the pure dense-vector retriever with **Qdrant native hybrid search** (BM25 sparse + dense vector, fused via RRF). Use FastEmbed's `Qdrant/bm25` model as the sparse encoder. Measure impact end-to-end with the V1 eval framework (`docs/rag_eval_dataset.json`, 31 cases).

## Why now

KB chunking V1+V1.1 produced rich child-parent chunks with `document_title` + `section_title` metadata. Pure dense retrieval still misses domain-specific keywords (e.g., "AUTO_REJECTED", "DTI", "PENDING_REVIEW") that BM25 handles trivially. Hybrid is the cheapest, highest-confidence win in the retrieval axis.

## Non-goals

- No reranker (Stage 2).
- No query rewriting (Stage 3).
- No custom Vietnamese tokenizer — use the default BM25 whitespace+punctuation split. If eval shows regression on Vietnamese-heavy questions, V1.1 can swap in `pyvi` or `vncorenlp`.
- No fusion-tuning. RRF constant `k=60` is the Qdrant default; keep it.
- No removal of `ParentDocumentRetriever` wrapper from V1.1 — hybrid replaces only the *child* retriever inside it.

---

## Architecture

### Dependency

Add to `backend/requirements.txt`:

```
fastembed>=0.3.0
```

`fastembed` is ~30MB installed. First call downloads the `Qdrant/bm25` model (~10MB) into `~/.cache/fastembed/` and caches it. Subsequent calls are instant.

### Settings (`backend/core/config.py`)

After existing `rag_qdrant_timeout_seconds`:

```python
# RAG retrieval (V1: hybrid BM25 + vector)
rag_bm25_model: str = "Qdrant/bm25"
```

We add **one** setting. No need for `rag_hybrid_rrf_k` — Qdrant defaults to 60 and tuning is out of scope.

### Module constants (`backend/rag/config.py`)

After existing entries:

```python
BM25_SPARSE_MODEL = settings.rag_bm25_model
```

### Retriever (`backend/rag/retriever.py`)

Switch `get_retriever()` to construct a hybrid `QdrantVectorStore`:

```python
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode

# ...

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
        sparse_embeddings = FastEmbedSparse(model_name=BM25_SPARSE_MODEL)
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=settings.rag_qdrant_timeout_seconds,
        )
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
        )
        child_retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K * 3})
        _retriever = ParentDocumentRetriever(child_retriever, max_parent_docs=TOP_K)
    return _retriever
```

The `ParentDocumentRetriever` wrapper from V1.1 is unchanged. Hybrid happens inside `child_retriever`.

### Ingest (`backend/rag/ingest.py`)

Both code paths in `upsert_to_qdrant` need the sparse encoder. The `from_documents` branch (used for recreate / first-time create) must pass `sparse_embedding=` + `retrieval_mode=HYBRID` so Qdrant creates the collection with both named vectors. The `add_documents` branch (incremental upsert) must also instantiate `QdrantVectorStore` in hybrid mode so newly-added chunks get sparse vectors too.

```python
def upsert_to_qdrant(chunks, embeddings, collection_name=QDRANT_COLLECTION, recreate=False):
    from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
    from qdrant_client import QdrantClient

    sparse_embeddings = FastEmbedSparse(model_name=BM25_SPARSE_MODEL)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    if recreate and client.collection_exists(collection_name=collection_name):
        client.delete_collection(collection_name=collection_name)

    if recreate or not client.collection_exists(collection_name=collection_name):
        QdrantVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=collection_name,
        )
        return

    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
    )
    store.add_documents(chunks)
```

### Migration

Re-ingest with `--recreate` is mandatory. The existing `creditintel-kb` collection has only dense named vectors; querying it in `HYBRID` mode will error. Update `CLAUDE.md`'s existing `--recreate` note to mention the hybrid upgrade explicitly:

```markdown
> **Note (V1+/hybrid)**: After upgrading to hybrid retrieval, you MUST re-run `python -m rag.ingest --recreate` once. The new collection has both dense and sparse named vectors; the old collection has only dense and will error on hybrid query.
```

---

## Eval workflow (this is part of the deliverable)

This is the first stage where we use the eval framework to gate a change. Pattern:

1. **Capture pre-change baseline**:
   ```bash
   cd backend
   PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
     --dataset ../docs/rag_eval_dataset.json \
     --output ../docs/rag_eval_baseline_pre_hybrid.json
   ```
   Commit `docs/rag_eval_baseline_pre_hybrid.json` so the diff is auditable.

2. **Apply hybrid changes + re-ingest** (`--recreate`).

3. **Run eval against baseline**:
   ```bash
   cd backend
   PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
     --dataset ../docs/rag_eval_dataset.json \
     --output ../docs/rag_eval_results_hybrid.json \
     --baseline ../docs/rag_eval_baseline_pre_hybrid.json \
     --diff ../docs/rag_eval_diff_hybrid.json
   ```
   Commit both `rag_eval_results_hybrid.json` and `rag_eval_diff_hybrid.json`.

4. **Inspect diff**. Acceptance: `summary.avg_overall_delta >= 0` (no regression) AND at least one group's `avg_overall` improves OR no group regresses.

If diff shows regression, the change is rolled back (or a follow-up V1.1 spec addresses it). Do not merge a regression silently.

The two committed JSON files are the empirical evidence the change actually helped — same idea as a benchmark table in an ML paper.

---

## Tests

Standalone scripts in `backend/tests_local/`, following the existing pattern.

### `test_rag_retriever_hybrid_config.py` (NEW)

Verify `get_retriever()` instantiates `QdrantVectorStore` with hybrid mode + a `FastEmbedSparse` instance using `settings.rag_bm25_model`.

Monkey-patch `QdrantVectorStore`, `FastEmbedSparse`, `QdrantClient` to capture their constructor kwargs. Reset `_retriever` to None before and after. Assert:
- `retrieval_mode == RetrievalMode.HYBRID`
- `sparse_embedding` argument is the `FastEmbedSparse` instance
- `FastEmbedSparse` was instantiated with `model_name = settings.rag_bm25_model`

### `test_rag_ingest_hybrid_writes_sparse.py` (NEW)

Verify `upsert_to_qdrant` (both `recreate=True` and `recreate=False` branches) passes `sparse_embedding` and `retrieval_mode=HYBRID` to whatever vector-store call it makes.

Monkey-patch `QdrantVectorStore.from_documents`, `QdrantVectorStore.__init__`, and `QdrantClient` to capture kwargs.

### Update existing tests

- `test_rag_timeout_config.py` — should still pass; if patching `QdrantVectorStore` constructor breaks because of the new `sparse_embedding` kwarg, extend the fake.
- `test_rag_ingest_cli.py` — should still pass (it patches `upsert_to_qdrant` directly).

---

## Acceptance criteria

1. `fastembed` in requirements + venv installable.
2. `get_retriever()` constructs the store in `RetrievalMode.HYBRID` with a `FastEmbedSparse` sparse embedding.
3. `upsert_to_qdrant` writes sparse vectors on both branches.
4. `--recreate` re-ingest produces a collection that supports hybrid query.
5. New tests `test_rag_retriever_hybrid_config.py` + `test_rag_ingest_hybrid_writes_sparse.py` pass.
6. All existing RAG/chat tests still pass.
7. `docs/rag_eval_baseline_pre_hybrid.json` + `docs/rag_eval_results_hybrid.json` + `docs/rag_eval_diff_hybrid.json` committed.
8. `rag_eval_diff_hybrid.json` shows no regression: `summary.avg_overall_delta >= -0.005` (small noise tolerance) AND no group regresses past the per-case threshold.
9. `CLAUDE.md` migration note updated to mention hybrid upgrade.

If criterion 8 fails, this stage is **not done** — investigate and either tune (V1.1) or revert.

---

## Order of work

1. Run eval to capture pre-hybrid baseline. Commit the JSON.
2. Add `fastembed` to `requirements.txt`, install in venv.
3. Add `rag_bm25_model` setting + `BM25_SPARSE_MODEL` constant.
4. Write `test_rag_retriever_hybrid_config.py` (failing).
5. Update `retriever.py` to hybrid mode. Test passes.
6. Write `test_rag_ingest_hybrid_writes_sparse.py` (failing).
7. Update `ingest.py` for hybrid both branches. Test passes.
8. Re-ingest locally with `--recreate`.
9. Run eval against the pre-hybrid baseline. Commit results + diff.
10. Update CLAUDE.md note.
11. Final sweep — all standalone tests.

Each step is its own commit.

---

## Out of scope (V1.1+)

- Custom Vietnamese tokenizer for BM25.
- Tunable RRF `k` value.
- Per-query mode selection (always hybrid).
- Per-collection hybrid toggle.
- Fallback to dense-only if Qdrant collection doesn't have sparse vectors (operator must re-ingest; don't silently degrade).
- Pre-warming the FastEmbed model at server startup (let it lazy-load on first query).
