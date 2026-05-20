# RAG Retrieval V1 — Stage 2: Cross-Encoder Reranker

**Date**: 2026-05-19
**Status**: Approved
**Stage**: 2 of 3 in the retrieval-quality axis
- Stage 1 (done, commit `7e6b9b1`) — Hybrid BM25 + Vector
- Stage 2 (this spec) — Cross-encoder reranker
- Stage 3 (future) — Query rewriting

**Scope**: `backend/rag/reranker.py` (new), `backend/rag/retriever.py`, `backend/rag/config.py`, `backend/core/config.py`, `CLAUDE.md`, plus 2 new tests + 2 eval artefacts.

## Goal

Add a cross-encoder reranker between hybrid retrieval and parent expansion. The hybrid retriever returns 20 candidate child chunks; the reranker scores each against the query and keeps the top 12; the ParentDocumentRetriever then expands those into 4 parent docs for the LLM.

The reranker model is `jinaai/jina-reranker-v2-base-multilingual` loaded via `fastembed.rerank.cross_encoder.TextCrossEncoder` — no new heavy dependencies (we already use fastembed for sparse vectors in Stage 1).

## Why now

Stage 1 hybrid was retrieval-neutral on the eval (26/31 cases identical context). Hybrid is foundational — it enables exact-keyword matching for tokens that dense embeddings miss (e.g. `AUTO_REJECTED`, `PENDING_REVIEW`). Stage 2 is where measurable lift is expected: reranking lets us pull a wider candidate set (20 instead of 12) without the LLM ever seeing the noise, since cross-encoder scoring filters down to the actually-relevant 12 before parent expansion.

## Non-goals

- No query rewriting (Stage 3).
- No threshold-based filtering — keep top-K, not top-score-above-T.
- No per-intent reranker selection.
- No caching of rerank scores.
- No GPU acceleration.
- No swap to alternative reranker model (deferred to V1.1 if eval regresses).

---

## Architecture

### New module `backend/rag/reranker.py`

```python
"""
reranker.py — Cross-encoder reranker for the RAG retrieval pipeline.

Wraps fastembed.rerank.cross_encoder.TextCrossEncoder with a singleton
cache. Reuses the fastembed dependency already added in Stage 1 (hybrid).
"""
import logging
from typing import Any

from rag.config import RERANKER_MODEL

logger = logging.getLogger(__name__)

_encoder = None


class Reranker:
    """Score (query, candidate_text) pairs and return the top-K candidates.

    Lazy-loaded: the underlying ONNX model is fetched on first .rerank() call.
    Singleton via module-level cache so it's only loaded once per process.
    """

    def __init__(self, model_name: str = RERANKER_MODEL):
        self._model_name = model_name
        self._encoder = None  # lazy

    def _ensure_loaded(self):
        if self._encoder is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self._encoder = TextCrossEncoder(model_name=self._model_name)
        return self._encoder

    def rerank(self, query: str, docs: list, top_k: int) -> list:
        """Return docs sorted desc by relevance, sliced to top_k.

        Errors propagate to caller (Retriever wraps with try/except).
        """
        if not docs:
            return docs
        encoder = self._ensure_loaded()
        texts = [getattr(d, "page_content", str(d)) for d in docs]
        scores = list(encoder.rerank(query, texts))
        scored = sorted(zip(scores, docs), key=lambda t: t[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]


def get_reranker() -> Reranker | None:
    """Singleton accessor. Returns None if rerank is disabled at startup."""
    global _encoder
    if not _is_enabled():
        return None
    if _encoder is None:
        _encoder = Reranker()
    return _encoder


def _is_enabled() -> bool:
    from rag.config import RERANKER_ENABLED
    return bool(RERANKER_ENABLED)
```

### New wrapper class `RerankedRetriever` (in `backend/rag/retriever.py`)

```python
class RerankedRetriever:
    """Pulls candidates from base_retriever, scores them with reranker,
    returns top_k. If reranker is None or fails, passes through candidates
    untouched (sliced to top_k).
    """

    def __init__(self, base_retriever, reranker, top_k: int):
        self.base_retriever = base_retriever
        self.reranker = reranker
        self.top_k = top_k

    def invoke(self, query):
        if hasattr(self.base_retriever, "invoke"):
            candidates = self.base_retriever.invoke(query)
        else:
            candidates = self.base_retriever.get_relevant_documents(query)

        if self.reranker is None:
            return candidates[: self.top_k]

        try:
            return self.reranker.rerank(query, candidates, self.top_k)
        except Exception:
            logger.exception("Reranker failed, falling back to candidates")
            return candidates[: self.top_k]

    def get_relevant_documents(self, query):
        return self.invoke(query)
```

### Updated `get_retriever()` in `backend/rag/retriever.py`

```python
def get_retriever():
    global _retriever
    if _retriever is None:
        embeddings = OpenAIEmbeddings(...)  # unchanged
        sparse_embeddings = FastEmbedSparse(model_name=BM25_SPARSE_MODEL)
        client = QdrantClient(...)  # unchanged
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )

        # Stage 2 change: hybrid returns RERANKER_CANDIDATE_K candidates,
        # rerank to TOP_K * 3, parent-expand to TOP_K.
        hybrid = vectorstore.as_retriever(search_kwargs={"k": RERANKER_CANDIDATE_K})
        reranker = get_reranker()
        reranked = RerankedRetriever(hybrid, reranker=reranker, top_k=TOP_K * 3)
        _retriever = ParentDocumentRetriever(reranked, max_parent_docs=TOP_K)
    return _retriever
```

Note: when `rag_reranker_enabled=False`, `get_reranker()` returns `None` and `RerankedRetriever` becomes a slice-only pass-through. This is the A/B-test escape hatch for eval comparison without code changes.

### Settings (`backend/core/config.py`)

```python
# RAG retrieval Stage 2 (reranker)
rag_reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
rag_reranker_enabled: bool = True
rag_reranker_candidate_k: int = 20
```

### Module constants (`backend/rag/config.py`)

```python
RERANKER_MODEL = settings.rag_reranker_model
RERANKER_ENABLED = settings.rag_reranker_enabled
RERANKER_CANDIDATE_K = settings.rag_reranker_candidate_k
```

---

## Failure modes

| Failure | Behavior |
|---|---|
| TextCrossEncoder model download fails (no network) | First `rerank()` call raises; `RerankedRetriever` catches → returns top_k of raw candidates. Logged. |
| TextCrossEncoder inference fails mid-query | Same — caught, fallback to raw candidates sliced. |
| `RERANKER_ENABLED=False` | `get_reranker()` returns None → `RerankedRetriever` slice-only. |
| Disk full when caching model | `TextCrossEncoder.__init__` raises → caught, logged, fallback to non-rerank. |

In all cases the user sees ≥1 retrieved doc (modulo upstream hybrid failure, which is its own Stage 1 concern).

---

## Tests

Standalone scripts in `backend/tests_local/`.

### `test_rag_reranker.py` (NEW)

Unit test on `Reranker` class with a mock `TextCrossEncoder`.

```python
"""Verify Reranker scores + sorts + slices via mocked TextCrossEncoder."""
from types import SimpleNamespace
import rag.reranker as reranker_mod
from rag.reranker import Reranker


def test_reranker_sorts_by_score_and_slices():
    docs = [
        SimpleNamespace(page_content="bad match"),
        SimpleNamespace(page_content="great match"),
        SimpleNamespace(page_content="ok match"),
    ]
    # Mock the encoder.
    class FakeEncoder:
        def rerank(self, query, texts):
            # Return scores: 0.1, 0.9, 0.5 → great match should be first.
            return [0.1, 0.9, 0.5]

    r = Reranker()
    r._encoder = FakeEncoder()
    result = r.rerank("any query", docs, top_k=2)
    assert len(result) == 2
    assert result[0].page_content == "great match"
    assert result[1].page_content == "ok match"


def test_reranker_returns_empty_for_no_docs():
    r = Reranker()
    r._encoder = object()  # should not be touched
    assert r.rerank("q", [], top_k=5) == []


def test_reranker_lazy_loads_encoder():
    # Verify the encoder is NOT loaded at __init__.
    r = Reranker()
    assert r._encoder is None


if __name__ == "__main__":
    test_reranker_sorts_by_score_and_slices()
    test_reranker_returns_empty_for_no_docs()
    test_reranker_lazy_loads_encoder()
    print("rag reranker tests passed")
```

### `test_rag_retriever_uses_reranker.py` (NEW)

Integration test: verify `get_retriever()` wires the 3-stage pipeline correctly.

```python
"""Verify get_retriever pipeline = Hybrid(k=20) -> RerankedRetriever(k=12) -> ParentDocumentRetriever(k=4)."""
from langchain_core.runnables import Runnable

import rag.retriever as retriever_mod
import rag.reranker as reranker_mod


class FakeSparse:
    def __init__(self, **kw):
        pass


class FakeClient:
    def __init__(self, **kw):
        pass


class FakeVectorStore(Runnable):
    captured_k: int | None = None

    def __init__(self, **kw):
        pass

    def as_retriever(self, **kw):
        FakeVectorStore.captured_k = kw.get("search_kwargs", {}).get("k")
        return self

    def invoke(self, input, config=None, **kw):
        return []


def test_get_retriever_uses_rerank_candidate_k():
    """Hybrid is asked for RERANKER_CANDIDATE_K candidates, not the old TOP_K*3."""
    from core.config import settings
    retriever_mod._retriever = None
    original_vs = retriever_mod.QdrantVectorStore
    original_client = retriever_mod.QdrantClient
    original_sparse = retriever_mod.FastEmbedSparse
    original_embeddings = retriever_mod.OpenAIEmbeddings
    retriever_mod.QdrantVectorStore = FakeVectorStore
    retriever_mod.QdrantClient = FakeClient
    retriever_mod.FastEmbedSparse = FakeSparse
    retriever_mod.OpenAIEmbeddings = lambda **kw: object()
    try:
        retriever_mod.get_retriever()
    finally:
        retriever_mod.QdrantVectorStore = original_vs
        retriever_mod.QdrantClient = original_client
        retriever_mod.FastEmbedSparse = original_sparse
        retriever_mod.OpenAIEmbeddings = original_embeddings
        retriever_mod._retriever = None

    assert FakeVectorStore.captured_k == settings.rag_reranker_candidate_k


def test_get_retriever_wraps_with_reranked_retriever():
    """Verify the wrapper chain: ParentDocumentRetriever wraps RerankedRetriever
    which wraps the hybrid retriever."""
    from rag.retriever import RerankedRetriever, ParentDocumentRetriever
    retriever_mod._retriever = None
    original_vs = retriever_mod.QdrantVectorStore
    original_client = retriever_mod.QdrantClient
    original_sparse = retriever_mod.FastEmbedSparse
    original_embeddings = retriever_mod.OpenAIEmbeddings
    retriever_mod.QdrantVectorStore = FakeVectorStore
    retriever_mod.QdrantClient = FakeClient
    retriever_mod.FastEmbedSparse = FakeSparse
    retriever_mod.OpenAIEmbeddings = lambda **kw: object()
    try:
        r = retriever_mod.get_retriever()
    finally:
        retriever_mod.QdrantVectorStore = original_vs
        retriever_mod.QdrantClient = original_client
        retriever_mod.FastEmbedSparse = original_sparse
        retriever_mod.OpenAIEmbeddings = original_embeddings
        retriever_mod._retriever = None

    assert isinstance(r, ParentDocumentRetriever)
    assert isinstance(r.child_retriever, RerankedRetriever)


def test_reranked_retriever_passthrough_when_reranker_is_none():
    """When reranker=None (toggle off), RerankedRetriever just slices candidates to top_k."""
    from types import SimpleNamespace
    from rag.retriever import RerankedRetriever

    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(20)]

    rr = RerankedRetriever(FakeBase(), reranker=None, top_k=12)
    out = rr.invoke("q")
    assert len(out) == 12
    assert out[0].page_content == "0"  # original order preserved


if __name__ == "__main__":
    test_get_retriever_uses_rerank_candidate_k()
    test_get_retriever_wraps_with_reranked_retriever()
    test_reranked_retriever_passthrough_when_reranker_is_none()
    print("rag retriever uses reranker tests passed")
```

### Update existing tests

- `test_rag_retriever_hybrid_config.py` — child retriever now wrapped by RerankedRetriever. The existing assertions about `QdrantVectorStore` kwargs still hold, but adjust if the test traversed `.child_retriever` directly.
- `test_rag_timeout_config.py` — should still pass (it patches constructors; the rerank layer is downstream). If `FakeVectorStore.as_retriever()` returns something that breaks `RerankedRetriever`, extend the stub.

---

## Eval workflow

Same pattern as Stage 1.

1. **Baseline = Stage 1 result**, already committed at `docs/rag_eval_results_hybrid.json`.
2. **Run post-rerank eval**:
   ```bash
   cd backend
   PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
     --dataset ../docs/rag_eval_dataset.json \
     --output ../docs/rag_eval_results_rerank.json \
     --baseline ../docs/rag_eval_results_hybrid.json \
     --diff ../docs/rag_eval_diff_rerank.json
   ```
3. **Inspect diff**.

### Acceptance

- **Strict pass**: `summary.avg_overall_delta > +0.02` (rerank should give measurable lift, not just be neutral)
- **Soft pass**: `+0.005 ≤ avg_overall_delta ≤ +0.02` — commit but file V1.1 follow-up to investigate
- **Neutral**: `-0.005 ≤ avg_overall_delta < +0.005` — rerank is no help on this dataset. Commit with caveat, consider whether `bge-reranker-v2-m3` (the swap-model option from brainstorm) is warranted.
- **Regression**: `< -0.005` — STOP. Investigate then decide V1.1 fix or revert.

Stage 1 was retrieval-neutral. Stage 2 must show signal (strict or soft pass) for the retrieval axis investment to be justified. If neutral or worse, brainstorm a V1.1 model swap.

---

## Order of work

1. Add settings + module constants.
2. Add new `reranker.py` (TDD: write test first).
3. Add `RerankedRetriever` class in `retriever.py` (TDD).
4. Update `get_retriever()` to wire the 3-stage pipeline (TDD).
5. Update CLAUDE.md note (first-run downloads ~1.11GB model).
6. Test sweep — all 31+ standalone tests pass.
7. Live eval — capture results + diff.
8. Inspect diff, decide pass/fail per acceptance bands.
9. Commit eval artefacts.
10. Final verification sweep.

Each step is one commit.

---

## Acceptance criteria

1. `backend/rag/reranker.py` exists with `Reranker` class + `get_reranker()`.
2. `backend/rag/retriever.py` has `RerankedRetriever` wrapper class.
3. `get_retriever()` returns `ParentDocumentRetriever(RerankedRetriever(hybrid, ...))` pipeline.
4. Hybrid stage requests `RERANKER_CANDIDATE_K` candidates (20).
5. With `rag_reranker_enabled=False`, pipeline behaves identically to Stage 1 (rerank is no-op).
6. New tests pass: `test_rag_reranker.py`, `test_rag_retriever_uses_reranker.py`.
7. All existing RAG / chat / memory / eval tests still pass.
8. `docs/rag_eval_results_rerank.json` + `docs/rag_eval_diff_rerank.json` committed.
9. Eval diff falls in strict-pass or soft-pass band (delta ≥ +0.005). If neutral or regression, open V1.1 follow-up before merging.
10. CLAUDE.md notes the ~1.11GB first-run model download for the reranker.

---

## Out of scope (V1.1+)

- Swap to `BAAI/bge-reranker-v2-m3` via sentence-transformers if jina v2-multilingual under-performs on Vietnamese. (Would add `sentence-transformers + torch` deps ~1.5 GB.)
- Caching rerank scores per `(query_hash, doc_id)` for repeated queries.
- Threshold filtering: drop docs where `score < some_threshold` instead of fixed top-K.
- GPU acceleration via onnxruntime-gpu.
- Per-intent rerank toggle.
- Batched cross-encoder inference tuning.
