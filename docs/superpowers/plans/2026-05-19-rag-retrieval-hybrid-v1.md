# RAG Retrieval V1 — Hybrid (BM25 + Vector) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Swap pure dense retrieval for Qdrant native hybrid (BM25 + vector, RRF fusion) and prove no regression via the V1 eval framework.

**Architecture:** Add `fastembed` dependency for the `Qdrant/bm25` sparse encoder. Switch `QdrantVectorStore` construction (in `retriever.py` and `ingest.py`) to `RetrievalMode.HYBRID` with a `FastEmbedSparse` sparse embedding alongside the existing OpenAI dense embedding. Re-ingest required (`--recreate`). Gate the change on the V1 eval framework: commit pre-hybrid baseline + post-hybrid results + diff.

**Tech Stack:** Python 3.11+, `langchain-qdrant>=0.1.0`, `qdrant-client>=1.7.0`, `fastembed`, `langchain-openai`, FastAPI, Qdrant 1.18 server. Tests are standalone scripts in `backend/tests_local/`.

**Spec:** [docs/superpowers/specs/2026-05-19-rag-retrieval-hybrid-v1-design.md](../specs/2026-05-19-rag-retrieval-hybrid-v1-design.md)

---

## File Structure

**Modified files:**
- `backend/requirements.txt` — add `fastembed>=0.3.0`.
- `backend/core/config.py` — add `rag_bm25_model` setting.
- `backend/rag/config.py` — re-export `BM25_SPARSE_MODEL`.
- `backend/rag/retriever.py` — switch `get_retriever()` to `RetrievalMode.HYBRID` with `FastEmbedSparse`.
- `backend/rag/ingest.py` — `upsert_to_qdrant` writes sparse vectors on both branches.
- `CLAUDE.md` — add a hybrid-upgrade note next to the existing `--recreate` warning.
- `backend/tests_local/test_rag_timeout_config.py` — extend `FakeVectorStore` stub if it breaks after the constructor gains `sparse_embedding`.

**New files:**
- `backend/tests_local/test_rag_retriever_hybrid_config.py` — assert retriever wires hybrid mode.
- `backend/tests_local/test_rag_ingest_hybrid_writes_sparse.py` — assert ingest passes hybrid kwargs on both branches.

**New artefacts (committed, not code):**
- `docs/rag_eval_baseline_pre_hybrid.json` — pre-change eval, capture as the very first task.
- `docs/rag_eval_results_hybrid.json` — post-change eval.
- `docs/rag_eval_diff_hybrid.json` — diff vs the baseline.

---

## Operator note

This plan calls live external services twice:

1. **Once at Task 1** — run the eval against the *current* (dense-only) RAG to capture the baseline. Requires `qdrant` container up + `OPENROUTER_API_KEY` in `backend/.env`.
2. **Once at Task 8** — re-run the eval after hybrid is wired and Qdrant is re-ingested. Same dependencies.

The TDD tasks in between (Tasks 2-7) do not require Qdrant or OpenRouter — they monkey-patch the SDKs.

---

## Task 1: Capture pre-hybrid eval baseline

**Files:**
- Create: `docs/rag_eval_baseline_pre_hybrid.json` (output artefact)

This task runs the existing eval runner against the *current* (dense-only) retriever and commits the result as the comparison baseline for Task 8.

- [ ] **Step 1: Confirm services are up**

```bash
docker ps | grep creditintel-qdrant   # must show "Up"
grep OPENROUTER_API_KEY /home/taitu/GitHub/Loan_ETL/backend/.env  # must have a key
```

If either is missing, fix before proceeding. Without both, the eval runner will fail.

- [ ] **Step 2: Run the eval against the current (dense-only) retriever**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_baseline_pre_hybrid.json
```

Expected: terminal prints something like `Eval complete: 31 cases, avg_overall=<float>`. The JSON file is written at the path above.

If a per-case error appears, the runner still records it and continues. That's fine — the baseline captures the current state, errors included.

- [ ] **Step 3: Inspect the baseline briefly**

```bash
jq '.summary' /home/taitu/GitHub/Loan_ETL/docs/rag_eval_baseline_pre_hybrid.json
```

Expected: a JSON object with `avg_faithfulness`, `avg_context_precision`, `avg_overall`, per-group breakdown. If `case_count != 31`, stop and investigate before continuing.

- [ ] **Step 4: Commit the baseline**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add docs/rag_eval_baseline_pre_hybrid.json
git commit -m "eval: capture pre-hybrid baseline (dense-only retriever)"
```

---

## Task 2: Add `fastembed` dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add the line**

Open `backend/requirements.txt` and append:

```
fastembed>=0.3.0
```

Place it near the other RAG-related entries (`langchain-qdrant`, `qdrant-client`).

- [ ] **Step 2: Install in venv**

```bash
cd /home/taitu/GitHub/Loan_ETL
./.venv/bin/pip install -r backend/requirements.txt
```

Expected: pip installs `fastembed` (~30 MB) plus any transitive deps. No errors.

- [ ] **Step 3: Verify import works**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -c "from langchain_qdrant import FastEmbedSparse, RetrievalMode; print('OK')"
```

Expected: `OK`. (If `ImportError`, the installed `langchain-qdrant` is too old — check the pinned version in `requirements.txt` and bump it explicitly to a known-good `>=0.1.4` if needed.)

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/requirements.txt
git commit -m "build: add fastembed dependency for Qdrant hybrid retrieval"
```

---

## Task 3: Add `rag_bm25_model` setting + module constant

**Files:**
- Modify: `backend/core/config.py`
- Modify: `backend/rag/config.py`

- [ ] **Step 1: Add the setting**

Open `backend/core/config.py`. After the line `rag_qdrant_timeout_seconds: float = 5.0`, add:

```python
    # RAG retrieval (V1: hybrid BM25 + vector)
    rag_bm25_model: str = "Qdrant/bm25"
```

- [ ] **Step 2: Re-export as a module constant**

Open `backend/rag/config.py` and append:

```python
BM25_SPARSE_MODEL = settings.rag_bm25_model
```

- [ ] **Step 3: Verify imports**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -c "from rag.config import BM25_SPARSE_MODEL; print(BM25_SPARSE_MODEL)"
```

Expected: `Qdrant/bm25`.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/core/config.py backend/rag/config.py
git commit -m "feat: rag_bm25_model setting + BM25_SPARSE_MODEL constant"
```

---

## Task 4: Hybrid retriever — TDD

**Files:**
- Test: `backend/tests_local/test_rag_retriever_hybrid_config.py` (new)
- Modify: `backend/rag/retriever.py`
- Modify: `backend/tests_local/test_rag_timeout_config.py` (extend `FakeVectorStore` stub to accept `sparse_embedding=` and `retrieval_mode=`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_retriever_hybrid_config.py`:

```python
"""Verify get_retriever() wires Qdrant in HYBRID mode with FastEmbedSparse."""
from langchain_core.runnables import Runnable

import rag.retriever as retriever_mod
from core.config import settings


_captured = {"vectorstore": None, "sparse": None}


class FakeSparse:
    def __init__(self, model_name):
        _captured["sparse"] = {"model_name": model_name}


class FakeQdrantClient:
    def __init__(self, **kwargs):
        pass


class FakeVectorStore(Runnable):
    def __init__(self, **kwargs):
        _captured["vectorstore"] = kwargs

    def as_retriever(self, **kwargs):
        return self

    def invoke(self, input, config=None, **kwargs):
        return []


def test_retriever_uses_hybrid_mode_with_fastembed_sparse():
    retriever_mod._retriever = None
    original_vs = retriever_mod.QdrantVectorStore
    original_client = retriever_mod.QdrantClient
    original_sparse = retriever_mod.FastEmbedSparse
    original_embeddings = retriever_mod.OpenAIEmbeddings
    retriever_mod.QdrantVectorStore = FakeVectorStore
    retriever_mod.QdrantClient = FakeQdrantClient
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

    vs_kwargs = _captured["vectorstore"]
    assert vs_kwargs is not None, "QdrantVectorStore was not instantiated"
    assert "sparse_embedding" in vs_kwargs, "sparse_embedding kwarg missing"
    assert isinstance(vs_kwargs["sparse_embedding"], FakeSparse), \
        "sparse_embedding must be a FastEmbedSparse instance"
    # retrieval_mode is a RetrievalMode enum; compare via name to avoid importing the enum here.
    assert getattr(vs_kwargs["retrieval_mode"], "name", str(vs_kwargs["retrieval_mode"])) == "HYBRID"
    assert _captured["sparse"]["model_name"] == settings.rag_bm25_model


if __name__ == "__main__":
    test_retriever_uses_hybrid_mode_with_fastembed_sparse()
    print("rag retriever hybrid config tests passed")
```

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_hybrid_config.py
```

Expected: `AttributeError: module 'rag.retriever' has no attribute 'FastEmbedSparse'`. The current `retriever.py` doesn't import `FastEmbedSparse`.

- [ ] **Step 3: Update `backend/rag/retriever.py`**

Replace the file with:

```python
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from rag.chunking import expand_child_documents_to_parents
from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
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

- [ ] **Step 4: Run the new test — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_hybrid_config.py
```

Expected: `rag retriever hybrid config tests passed`.

- [ ] **Step 5: Extend `test_rag_timeout_config.py` if it breaks**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Likely outcome: it passes because the test only patches the LLM/embeddings/client constructors, not `QdrantVectorStore` internals. If it fails with `TypeError: __init__() got an unexpected keyword argument 'sparse_embedding'`, extend the `FakeVectorStore` stub in that file:

```python
class FakeVectorStore:
    def __init__(self, **kwargs):
        pass

    def as_retriever(self, **kwargs):
        return self
```

(Accept arbitrary kwargs; current behaviour unchanged.) Also patch `retriever_mod.FastEmbedSparse` in the test so it doesn't try to download a real model:

```python
retriever_mod.FastEmbedSparse = lambda **kw: object()
```

inside the test where `OpenAIEmbeddings`/`QdrantClient`/`QdrantVectorStore` are already patched.

Re-run after the edit; expect pass.

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/retriever.py \
        backend/tests_local/test_rag_retriever_hybrid_config.py \
        backend/tests_local/test_rag_timeout_config.py
git commit -m "feat: retriever uses Qdrant HYBRID mode with FastEmbedSparse"
```

---

## Task 5: Hybrid ingest — TDD

**Files:**
- Test: `backend/tests_local/test_rag_ingest_hybrid_writes_sparse.py` (new)
- Modify: `backend/rag/ingest.py` (`upsert_to_qdrant`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_ingest_hybrid_writes_sparse.py`:

```python
"""Verify upsert_to_qdrant passes sparse_embedding + HYBRID on both branches."""
from types import SimpleNamespace

import rag.ingest as ingest


_captured = {"from_documents": None, "store_init": None, "store_add": None, "sparse_init": None}


class FakeSparse:
    def __init__(self, model_name):
        _captured["sparse_init"] = {"model_name": model_name}


class FakeClient:
    def __init__(self, **kwargs):
        self._exists = False

    def collection_exists(self, collection_name):
        return self._exists

    def delete_collection(self, collection_name):
        self._exists = False


class FakeVectorStore:
    def __init__(self, **kwargs):
        _captured["store_init"] = kwargs

    def add_documents(self, chunks):
        _captured["store_add"] = list(chunks)

    @classmethod
    def from_documents(cls, **kwargs):
        _captured["from_documents"] = kwargs


def _reset():
    for key in _captured:
        _captured[key] = None


def _patch():
    import langchain_qdrant
    import qdrant_client
    original = {
        "qvs": langchain_qdrant.QdrantVectorStore,
        "fes": langchain_qdrant.FastEmbedSparse,
        "qc": qdrant_client.QdrantClient,
    }
    langchain_qdrant.QdrantVectorStore = FakeVectorStore
    langchain_qdrant.FastEmbedSparse = FakeSparse
    qdrant_client.QdrantClient = FakeClient
    return original, langchain_qdrant, qdrant_client


def _unpatch(original, langchain_qdrant, qdrant_client):
    langchain_qdrant.QdrantVectorStore = original["qvs"]
    langchain_qdrant.FastEmbedSparse = original["fes"]
    qdrant_client.QdrantClient = original["qc"]


def _chunks():
    return [SimpleNamespace(page_content="x", metadata={"source": "fake.md"})]


def test_recreate_branch_uses_from_documents_with_sparse_and_hybrid():
    _reset()
    original, lcq, qc = _patch()
    try:
        ingest.upsert_to_qdrant(_chunks(), embeddings=object(),
                                collection_name="kb", recreate=True)
    finally:
        _unpatch(original, lcq, qc)

    kwargs = _captured["from_documents"]
    assert kwargs is not None, "from_documents must be called for recreate"
    assert "sparse_embedding" in kwargs
    assert isinstance(kwargs["sparse_embedding"], FakeSparse)
    assert getattr(kwargs["retrieval_mode"], "name",
                   str(kwargs["retrieval_mode"])) == "HYBRID"


def test_incremental_branch_uses_add_documents_with_hybrid_store():
    _reset()
    original, lcq, qc = _patch()

    # Pretend the collection already exists so the incremental branch runs.
    class FakeClientExists(FakeClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._exists = True

    qc.QdrantClient = FakeClientExists
    try:
        ingest.upsert_to_qdrant(_chunks(), embeddings=object(),
                                collection_name="kb", recreate=False)
    finally:
        _unpatch(original, lcq, qc)

    kwargs = _captured["store_init"]
    assert kwargs is not None, "QdrantVectorStore must be instantiated"
    assert "sparse_embedding" in kwargs
    assert isinstance(kwargs["sparse_embedding"], FakeSparse)
    assert getattr(kwargs["retrieval_mode"], "name",
                   str(kwargs["retrieval_mode"])) == "HYBRID"
    assert _captured["store_add"] is not None, "add_documents must be called"


if __name__ == "__main__":
    test_recreate_branch_uses_from_documents_with_sparse_and_hybrid()
    test_incremental_branch_uses_add_documents_with_hybrid_store()
    print("rag ingest hybrid tests passed")
```

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_hybrid_writes_sparse.py
```

Expected: `AssertionError` — current ingest doesn't pass `sparse_embedding` or `retrieval_mode`.

- [ ] **Step 3: Update `upsert_to_qdrant`**

Replace `upsert_to_qdrant` in `backend/rag/ingest.py`:

```python
def upsert_to_qdrant(chunks, embeddings, collection_name=QDRANT_COLLECTION, recreate=False):
    """Upsert chunks into Qdrant in HYBRID mode (dense + BM25 sparse).

    With ``recreate=True``, deletes the collection first (destructive).
    With ``recreate=False`` (default), appends to the existing collection.
    """
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

Add the import at the top of the file (after the other `rag.config` imports):

```python
from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
)
```

- [ ] **Step 4: Run the new test — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_hybrid_writes_sparse.py
```

Expected: `rag ingest hybrid tests passed`.

- [ ] **Step 5: Verify the existing ingest CLI test still passes**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_cli.py
```

Expected: `rag ingest CLI tests passed`. (It mocks `upsert_to_qdrant` directly, so the new internal behaviour doesn't affect it.)

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/ingest.py backend/tests_local/test_rag_ingest_hybrid_writes_sparse.py
git commit -m "feat: ingest writes BM25 sparse vectors alongside dense (hybrid mode)"
```

---

## Task 6: Update `CLAUDE.md` migration note

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Locate the existing `--recreate` note**

```bash
grep -n "recreate" /home/taitu/GitHub/Loan_ETL/CLAUDE.md
```

The existing note (from the earlier KB v1.1 work) says you must `--recreate` after upgrading chunking. Hybrid adds another reason.

- [ ] **Step 2: Tighten the note**

Open `CLAUDE.md`. Find the existing note and replace it with the hybrid-aware version:

```markdown
> **Note (V1+/hybrid):** After upgrading either (a) the chunking algorithm or (b) to hybrid retrieval, you MUST re-run `python -m rag.ingest --recreate` once. Hybrid mode requires both dense and BM25 sparse named vectors on every Qdrant point; the old collection has only dense and will error on hybrid query.
```

If your file has the old note in two places, update both.

- [ ] **Step 3: Verify markdown is balanced**

```bash
grep -A 1 "Note (V1+/hybrid)" /home/taitu/GitHub/Loan_ETL/CLAUDE.md
```

Expected: the note appears with the surrounding markdown intact.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add CLAUDE.md
git commit -m "docs: tighten --recreate note for hybrid retrieval upgrade"
```

---

## Task 7: Test sweep before live re-ingest

**Files:** none (verification only)

- [ ] **Step 1: Run every RAG/chat/eval test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All RAG / chat / memory tests passed"
```

Expected: every test prints its pass line. If any fail, stop and fix before live re-ingest.

- [ ] **Step 2: No commit** (verification only).

---

## Task 8: Live re-ingest with hybrid

**Files:** none — operates on live Qdrant.

- [ ] **Step 1: Verify Qdrant is up and confirm intent to wipe**

```bash
docker ps | grep creditintel-qdrant   # must show "Up"
```

This task DROPS the existing `creditintel-kb` collection. The KB content is reproducible from `backend/rag/knowledge/` + `docs/data_dictionary/` so the wipe is recoverable, but you do lose any ad-hoc additions if there were any.

- [ ] **Step 2: Dry-run to confirm chunk count looks reasonable**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --dry-run
```

Expected: prints `Loaded N documents -> M chunks` with a non-zero M, and 2 sample chunks. If `M == 0`, stop — knowledge dir is empty or unreachable.

- [ ] **Step 3: Recreate the collection in hybrid mode**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --recreate
```

Expected: prints `Recreating collection 'creditintel-kb' (destructive)` then `Done. Ingested M chunks.`. First run downloads the `Qdrant/bm25` model into `~/.cache/fastembed/` (~10 MB; only on first call).

- [ ] **Step 4: Smoke-check a hybrid query**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -c "
from rag.retriever import get_retriever
docs = get_retriever().invoke('DTI là gì')
print(f'Got {len(docs)} docs')
for d in docs[:2]:
    print('-', d.metadata.get('source'), '::', d.metadata.get('section_title'))
"
```

Expected: prints `Got N docs` with N ≥ 1 and some docs about DTI / policy. If you get an error like `Qdrant returned 400: Sparse vector named '...' not found`, the recreate didn't write sparse vectors — go back to Task 5 and check the diff.

- [ ] **Step 5: No commit yet** — proceed to Task 9 for the eval comparison.

---

## Task 9: Post-hybrid eval + diff vs baseline

**Files:**
- Create: `docs/rag_eval_results_hybrid.json`
- Create: `docs/rag_eval_diff_hybrid.json`

- [ ] **Step 1: Run eval with the hybrid retriever**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results_hybrid.json \
  --baseline ../docs/rag_eval_baseline_pre_hybrid.json \
  --diff ../docs/rag_eval_diff_hybrid.json
```

Expected: terminal prints `Eval complete: 31 cases ...` and writes the two JSON files. Exit code 0 means no regression detected. Exit code 1 means `has_regression == true` — read the diff to understand which group regressed.

- [ ] **Step 2: Inspect the diff**

```bash
jq '.summary, .regressed_case_ids, .improved_case_ids' /home/taitu/GitHub/Loan_ETL/docs/rag_eval_diff_hybrid.json
```

Expected: `summary.avg_overall_delta >= -0.005` (small noise tolerance) AND `regressed_case_ids` is short (preferably empty). If a meaningful regression appears, stop and investigate — likely culprits: BM25 over-weighting short keywords, FastEmbed tokenizer mishandling Vietnamese diacritics.

- [ ] **Step 3: Decide pass / fail**

- **PASS** (no regression): proceed to Step 4 (commit + finish).
- **FAIL** (regression): do NOT commit the result JSONs as a "win". Instead, file a follow-up V1.1 spec to investigate. Options to surface in the follow-up: tune `k` value in `as_retriever(search_kwargs={"k": ...})`, swap BM25 model variant, or revert hybrid for the specific failing intent.

This plan only succeeds if Step 3 says PASS.

- [ ] **Step 4: Commit the eval artefacts**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add docs/rag_eval_results_hybrid.json docs/rag_eval_diff_hybrid.json
git commit -m "eval: hybrid retrieval results + diff vs pre-hybrid baseline"
```

---

## Task 10: Final verification

- [ ] **Step 1: Re-run the full test sweep**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All tests passed"
```

- [ ] **Step 2: Confirm git log shows the expected 9 commits**

```bash
cd /home/taitu/GitHub/Loan_ETL
git log --oneline 25757c4..HEAD
```

Expected: 9 commits (Task 1 baseline, Task 2 dep, Task 3 settings, Task 4 retriever, Task 5 ingest, Task 6 docs, Tasks 7-8 are no-commit, Task 9 eval results).

- [ ] **Step 3: No commit** (verification only).

---

## Acceptance criteria

1. `fastembed` installed; `from langchain_qdrant import FastEmbedSparse, RetrievalMode` works.
2. `get_retriever()` constructs `QdrantVectorStore` with `retrieval_mode=RetrievalMode.HYBRID` + `sparse_embedding=FastEmbedSparse(BM25_SPARSE_MODEL)`.
3. `upsert_to_qdrant` writes hybrid (dense + sparse) on BOTH branches.
4. Re-ingest with `--recreate` produces a queryable hybrid collection.
5. `test_rag_retriever_hybrid_config.py` and `test_rag_ingest_hybrid_writes_sparse.py` pass.
6. All existing RAG / chat / memory / eval tests still pass.
7. `docs/rag_eval_baseline_pre_hybrid.json`, `docs/rag_eval_results_hybrid.json`, and `docs/rag_eval_diff_hybrid.json` committed.
8. `rag_eval_diff_hybrid.json` shows `summary.avg_overall_delta >= -0.005` AND no per-group regression past the configured threshold.
9. `CLAUDE.md` migration note mentions hybrid.

If criterion 8 fails, this stage is **not done** — open a V1.1 follow-up spec, don't merge a regression.
