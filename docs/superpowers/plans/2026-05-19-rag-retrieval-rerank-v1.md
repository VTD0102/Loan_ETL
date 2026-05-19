# RAG Retrieval V1 — Stage 2: Cross-Encoder Reranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a cross-encoder reranker (jina-reranker-v2-base-multilingual via fastembed) between Stage 1's hybrid retrieval and parent-document expansion, then gate on the V1 eval framework with the Stage 1 result as baseline.

**Architecture:** New `backend/rag/reranker.py` wraps `fastembed.rerank.cross_encoder.TextCrossEncoder` (singleton, lazy-loaded). New `RerankedRetriever` wrapper class in `backend/rag/retriever.py` sits between hybrid (top-20 candidates) and `ParentDocumentRetriever` (top-4 parents), reranking down to top-12 child chunks. Failure-graceful: any reranker failure (init or per-query) falls back to raw top-K slice; `rag_reranker_enabled=False` short-circuits to a pure pass-through for A/B testing.

**Tech Stack:** Python 3.12.13 (venv migrated in Stage 1), `fastembed>=0.8.0` (already installed), `langchain-qdrant`, `qdrant-client`. Tests are standalone scripts in `backend/tests_local/`.

**Spec:** [docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1-design.md](../specs/2026-05-19-rag-retrieval-rerank-v1-design.md)

---

## File Structure

**New files:**
- `backend/rag/reranker.py` — `Reranker` class + `get_reranker()` singleton.
- `backend/tests_local/test_rag_reranker.py` — unit tests on `Reranker`.
- `backend/tests_local/test_rag_retriever_uses_reranker.py` — integration tests on the wired pipeline.

**Modified files:**
- `backend/core/config.py` — 3 new settings (model, enabled, candidate_k).
- `backend/rag/config.py` — 3 module constants re-exporting settings.
- `backend/rag/retriever.py` — `RerankedRetriever` class + `get_retriever()` rewires pipeline.
- `CLAUDE.md` — note the ~1.11 GB first-run model download.

**New eval artefacts (committed at end):**
- `docs/rag_eval_results_rerank.json`
- `docs/rag_eval_diff_rerank.json`

---

## Operator note

This plan calls live external services in two places:

1. **Task 8** — first live retriever query triggers fastembed to download the reranker model (~1.11 GB) into `~/.cache/fastembed/`. Needs internet, several minutes on the first run only.
2. **Task 9** — runs the eval against the live RAG (Qdrant + OpenRouter). Requires both services up.

Tasks 1-7 are pure code + monkey-patched tests, no external dependencies.

---

## Task 1: Add reranker settings + module constants

**Files:**
- Modify: `backend/core/config.py`
- Modify: `backend/rag/config.py`

- [ ] **Step 1: Add 3 settings to `core/config.py`**

Open `backend/core/config.py`. After the existing `rag_bm25_model` line, add:

```python
    # RAG retrieval Stage 2 (reranker)
    rag_reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rag_reranker_enabled: bool = True
    rag_reranker_candidate_k: int = 20
```

- [ ] **Step 2: Add 3 module constants to `rag/config.py`**

Open `backend/rag/config.py`. After the existing `BM25_SPARSE_MODEL = ...` line, add:

```python
RERANKER_MODEL = settings.rag_reranker_model
RERANKER_ENABLED = settings.rag_reranker_enabled
RERANKER_CANDIDATE_K = settings.rag_reranker_candidate_k
```

- [ ] **Step 3: Verify the imports load**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -c "
from rag.config import RERANKER_MODEL, RERANKER_ENABLED, RERANKER_CANDIDATE_K
print(RERANKER_MODEL, RERANKER_ENABLED, RERANKER_CANDIDATE_K)
"
```

Expected: `jinaai/jina-reranker-v2-base-multilingual True 20`.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/core/config.py backend/rag/config.py
git commit -m "feat: rag_reranker_* settings + RERANKER_* module constants"
```

---

## Task 2: `Reranker` class — TDD

**Files:**
- Create: `backend/rag/reranker.py`
- Test: `backend/tests_local/test_rag_reranker.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_reranker.py`:

```python
"""Unit tests for rag.reranker.Reranker — sort + slice via mocked encoder."""
from types import SimpleNamespace

from rag.reranker import Reranker


def test_reranker_sorts_by_score_and_slices_to_top_k():
    docs = [
        SimpleNamespace(page_content="bad match"),
        SimpleNamespace(page_content="great match"),
        SimpleNamespace(page_content="ok match"),
    ]

    class FakeEncoder:
        def rerank(self, query, texts):
            # Scores aligned with texts order: bad=0.1, great=0.9, ok=0.5
            return [0.1, 0.9, 0.5]

    r = Reranker()
    r._encoder = FakeEncoder()  # bypass lazy load
    result = r.rerank("any query", docs, top_k=2)

    assert len(result) == 2
    assert result[0].page_content == "great match"
    assert result[1].page_content == "ok match"


def test_reranker_returns_empty_for_no_docs():
    r = Reranker()
    r._encoder = object()  # untouched
    assert r.rerank("q", [], top_k=5) == []


def test_reranker_lazy_loads_encoder():
    """Constructor must NOT trigger model download."""
    r = Reranker()
    assert r._encoder is None


def test_reranker_top_k_larger_than_docs_returns_all_sorted():
    docs = [
        SimpleNamespace(page_content="a"),
        SimpleNamespace(page_content="b"),
    ]

    class FakeEncoder:
        def rerank(self, query, texts):
            return [0.3, 0.7]

    r = Reranker()
    r._encoder = FakeEncoder()
    out = r.rerank("q", docs, top_k=10)
    assert len(out) == 2
    assert out[0].page_content == "b"  # higher score first


if __name__ == "__main__":
    test_reranker_sorts_by_score_and_slices_to_top_k()
    test_reranker_returns_empty_for_no_docs()
    test_reranker_lazy_loads_encoder()
    test_reranker_top_k_larger_than_docs_returns_all_sorted()
    print("rag reranker tests passed")
```

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_reranker.py
```

Expected: `ModuleNotFoundError: No module named 'rag.reranker'`.

- [ ] **Step 3: Create `backend/rag/reranker.py`**

```python
"""
reranker.py — Cross-encoder reranker for the RAG retrieval pipeline.

Wraps fastembed.rerank.cross_encoder.TextCrossEncoder with a singleton
cache and a lazy-load constructor. Reuses fastembed already pulled in
for Stage 1 (hybrid sparse vectors).
"""
from __future__ import annotations

import logging

from rag.config import RERANKER_ENABLED, RERANKER_MODEL

logger = logging.getLogger(__name__)

_singleton: "Reranker | None" = None


class Reranker:
    """Score (query, candidate_text) pairs; return docs sorted desc, top_k."""

    def __init__(self, model_name: str = RERANKER_MODEL):
        self._model_name = model_name
        self._encoder = None  # lazy

    def _ensure_loaded(self):
        if self._encoder is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self._encoder = TextCrossEncoder(model_name=self._model_name)
        return self._encoder

    def rerank(self, query: str, docs: list, top_k: int) -> list:
        """Return docs sorted desc by relevance score, sliced to top_k.

        Empty input returns empty list (no model load).
        Exceptions propagate to caller (RerankedRetriever catches).
        """
        if not docs:
            return docs
        encoder = self._ensure_loaded()
        texts = [getattr(d, "page_content", str(d)) for d in docs]
        scores = list(encoder.rerank(query, texts))
        scored = sorted(zip(scores, docs), key=lambda t: t[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]


def get_reranker() -> "Reranker | None":
    """Singleton accessor. Returns None if rerank is disabled by config."""
    global _singleton
    if not RERANKER_ENABLED:
        return None
    if _singleton is None:
        _singleton = Reranker()
    return _singleton
```

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_reranker.py
```

Expected: `rag reranker tests passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/reranker.py backend/tests_local/test_rag_reranker.py
git commit -m "feat: rag.reranker.Reranker with lazy-loaded TextCrossEncoder"
```

---

## Task 3: `RerankedRetriever` wrapper class — TDD

**Files:**
- Modify: `backend/rag/retriever.py` (add new class only; do not touch `get_retriever()` yet — Task 4 does that)
- Test: `backend/tests_local/test_rag_retriever_uses_reranker.py` (write only the wrapper-pass-through test in this task; pipeline tests come in Task 4)

- [ ] **Step 1: Write the failing test**

Create `backend/tests_local/test_rag_retriever_uses_reranker.py`:

```python
"""Integration tests for the RerankedRetriever wrapper + get_retriever pipeline."""
from types import SimpleNamespace

from rag.retriever import RerankedRetriever


def test_reranked_retriever_passthrough_when_reranker_is_none():
    """reranker=None => slice candidates to top_k, preserve order."""
    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(20)]

    rr = RerankedRetriever(FakeBase(), reranker=None, top_k=12)
    out = rr.invoke("q")
    assert len(out) == 12
    assert out[0].page_content == "0"
    assert out[-1].page_content == "11"


def test_reranked_retriever_uses_reranker_when_provided():
    """reranker.rerank called with the candidates and top_k."""
    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content="a"), SimpleNamespace(page_content="b")]

    captured = {}

    class FakeReranker:
        def rerank(self, query, docs, top_k):
            captured["query"] = query
            captured["doc_count"] = len(docs)
            captured["top_k"] = top_k
            return list(reversed(docs))  # reverse to prove rerank ran

    rr = RerankedRetriever(FakeBase(), reranker=FakeReranker(), top_k=2)
    out = rr.invoke("hello")

    assert captured == {"query": "hello", "doc_count": 2, "top_k": 2}
    assert out[0].page_content == "b"  # reversed


def test_reranked_retriever_falls_back_on_rerank_failure():
    """If reranker raises, return raw candidates sliced to top_k."""
    class FakeBase:
        def invoke(self, q):
            return [SimpleNamespace(page_content=str(i)) for i in range(5)]

    class FailingReranker:
        def rerank(self, query, docs, top_k):
            raise RuntimeError("model not loaded")

    rr = RerankedRetriever(FakeBase(), reranker=FailingReranker(), top_k=3)
    out = rr.invoke("q")
    assert len(out) == 3
    assert [d.page_content for d in out] == ["0", "1", "2"]


if __name__ == "__main__":
    test_reranked_retriever_passthrough_when_reranker_is_none()
    test_reranked_retriever_uses_reranker_when_provided()
    test_reranked_retriever_falls_back_on_rerank_failure()
    print("rag retriever uses reranker (wrapper) tests passed")
```

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
```

Expected: `ImportError: cannot import name 'RerankedRetriever'`.

- [ ] **Step 3: Add the wrapper class to `retriever.py`**

Open `backend/rag/retriever.py`. The current file imports + `ParentDocumentRetriever` class + `get_retriever()` function exist; ADD the new class right above `_retriever = None`. The new class:

```python
class RerankedRetriever:
    """Pulls candidates from base_retriever; if a reranker is provided,
    scores+sorts via reranker; otherwise pure slice to top_k.

    Any reranker exception is caught and we fall back to the raw
    candidate slice — never let a reranker failure break retrieval.
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

The file uses `logger` — verify it's already declared at the top. If not, add `import logging` + `logger = logging.getLogger(__name__)` near the existing imports.

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
```

Expected: `rag retriever uses reranker (wrapper) tests passed`.

- [ ] **Step 5: Verify the broader retriever tests still pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_hybrid_config.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/retriever.py backend/tests_local/test_rag_retriever_uses_reranker.py
git commit -m "feat: RerankedRetriever wrapper (fallback-graceful on rerank failure)"
```

---

## Task 4: Wire `get_retriever` to use rerank + extended pipeline — TDD

**Files:**
- Modify: `backend/rag/retriever.py` (`get_retriever()` only)
- Append: `backend/tests_local/test_rag_retriever_uses_reranker.py` (3 new tests)

- [ ] **Step 1: Append 3 failing tests**

Open `backend/tests_local/test_rag_retriever_uses_reranker.py`. Add ABOVE the `if __name__ == "__main__":` block:

```python
from langchain_core.runnables import Runnable

import rag.retriever as retriever_mod


class FakeSparseEmbed:
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


def _patch_retriever_module():
    """Patch all external constructors and reset the singleton.
    Returns the dict of originals so the caller can restore."""
    retriever_mod._retriever = None
    originals = {
        "qvs": retriever_mod.QdrantVectorStore,
        "qc": retriever_mod.QdrantClient,
        "fes": retriever_mod.FastEmbedSparse,
        "oe": retriever_mod.OpenAIEmbeddings,
    }
    retriever_mod.QdrantVectorStore = FakeVectorStore
    retriever_mod.QdrantClient = FakeClient
    retriever_mod.FastEmbedSparse = FakeSparseEmbed
    retriever_mod.OpenAIEmbeddings = lambda **kw: object()
    return originals


def _unpatch_retriever_module(originals):
    retriever_mod.QdrantVectorStore = originals["qvs"]
    retriever_mod.QdrantClient = originals["qc"]
    retriever_mod.FastEmbedSparse = originals["fes"]
    retriever_mod.OpenAIEmbeddings = originals["oe"]
    retriever_mod._retriever = None


def test_get_retriever_requests_candidate_k_from_hybrid():
    """Hybrid retriever should be asked for RERANKER_CANDIDATE_K candidates."""
    from core.config import settings
    originals = _patch_retriever_module()
    try:
        retriever_mod.get_retriever()
    finally:
        _unpatch_retriever_module(originals)

    assert FakeVectorStore.captured_k == settings.rag_reranker_candidate_k


def test_get_retriever_chain_is_parent_of_reranked_of_hybrid():
    """Pipeline must be ParentDocumentRetriever wrapping RerankedRetriever wrapping hybrid."""
    from rag.retriever import ParentDocumentRetriever, RerankedRetriever
    originals = _patch_retriever_module()
    try:
        r = retriever_mod.get_retriever()
    finally:
        _unpatch_retriever_module(originals)

    assert isinstance(r, ParentDocumentRetriever)
    assert isinstance(r.child_retriever, RerankedRetriever)


def test_get_retriever_respects_reranker_disabled():
    """When rag_reranker_enabled=False, RerankedRetriever has reranker=None."""
    from rag.retriever import RerankedRetriever
    from rag import config as rag_config
    from core.config import settings

    original_enabled = rag_config.RERANKER_ENABLED
    rag_config.RERANKER_ENABLED = False

    # Reset reranker singleton too so the next get_reranker() respects the new flag.
    import rag.reranker as reranker_mod
    original_singleton = reranker_mod._singleton
    reranker_mod._singleton = None

    originals = _patch_retriever_module()
    try:
        r = retriever_mod.get_retriever()
        rr = r.child_retriever
        assert isinstance(rr, RerankedRetriever)
        assert rr.reranker is None
    finally:
        _unpatch_retriever_module(originals)
        rag_config.RERANKER_ENABLED = original_enabled
        reranker_mod._singleton = original_singleton


if __name__ == "__main__":
    test_reranked_retriever_passthrough_when_reranker_is_none()
    test_reranked_retriever_uses_reranker_when_provided()
    test_reranked_retriever_falls_back_on_rerank_failure()
    test_get_retriever_requests_candidate_k_from_hybrid()
    test_get_retriever_chain_is_parent_of_reranked_of_hybrid()
    test_get_retriever_respects_reranker_disabled()
    print("rag retriever uses reranker tests passed")
```

(Replace the existing `if __name__ == "__main__":` block with the updated one above so the 3 new tests run.)

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
```

Expected: `AssertionError` — the existing `get_retriever()` still uses `TOP_K * 3 = 12` (not `RERANKER_CANDIDATE_K = 20`), and child_retriever is the raw vectorstore retriever, not a `RerankedRetriever`.

- [ ] **Step 3: Update `get_retriever()` in `backend/rag/retriever.py`**

The existing function currently does:

```python
child_retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K * 3})
_retriever = ParentDocumentRetriever(child_retriever, max_parent_docs=TOP_K)
```

Replace those two lines with:

```python
hybrid = vectorstore.as_retriever(search_kwargs={"k": RERANKER_CANDIDATE_K})
reranked = RerankedRetriever(hybrid, reranker=get_reranker(), top_k=TOP_K * 3)
_retriever = ParentDocumentRetriever(reranked, max_parent_docs=TOP_K)
```

Also add the import line at the top of `retriever.py`:

```python
from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
    RERANKER_CANDIDATE_K, TOP_K,
)
from rag.reranker import get_reranker
```

(Merge `RERANKER_CANDIDATE_K` into the existing `from rag.config import (...)` tuple; add the new `from rag.reranker import get_reranker` line.)

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
```

Expected: `rag retriever uses reranker tests passed` (all 6 tests).

- [ ] **Step 5: Verify the existing hybrid-config test still passes**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_hybrid_config.py
```

This test asserts the hybrid retriever is constructed with the right kwargs; the kwargs are unchanged (only `as_retriever`'s `k` changed). Expected: pass. If it asserts on `_retriever.child_retriever` being something specific, update its assertion to allow either the raw retriever or a `RerankedRetriever` (whichever it now finds).

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/retriever.py backend/tests_local/test_rag_retriever_uses_reranker.py
git commit -m "feat: get_retriever wires hybrid -> rerank -> parent pipeline"
```

---

## Task 5: Update `CLAUDE.md` with reranker note

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Find the existing Qdrant section**

```bash
grep -n "Qdrant (local, for RAG)" /home/taitu/GitHub/Loan_ETL/CLAUDE.md
```

Note the line number.

- [ ] **Step 2: Add a reranker note**

Right below the existing `--recreate` hybrid migration note (the `> **Note (V1+/hybrid):** ...` callout), insert this new paragraph:

```markdown
> **Note (Stage 2 / reranker):** The first live RAG query after enabling the reranker downloads `jinaai/jina-reranker-v2-base-multilingual` (~1.11 GB) into `~/.cache/fastembed/`. Subsequent queries are instant. To disable rerank entirely (e.g., for A/B comparison), set `rag_reranker_enabled=False` in `backend/.env` and restart the server — the retrieval pipeline falls back to plain hybrid sliced to top-K.
```

- [ ] **Step 3: Verify markdown looks right**

```bash
grep -B 1 -A 3 "Stage 2 / reranker" /home/taitu/GitHub/Loan_ETL/CLAUDE.md
```

Expected: the note appears once, surrounded by the existing Qdrant content.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add CLAUDE.md
git commit -m "docs: note ~1.11 GB reranker model download on first live query"
```

---

## Task 6: Test sweep before live calls

**Files:** none — verification only.

- [ ] **Step 1: Run every RAG / chat / memory standalone test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All RAG / chat / memory tests passed"
```

Expected: every test prints its pass line. If any test fails, STOP and investigate before continuing — Tasks 7+ are live and irreversible (model download, eval costs).

- [ ] **Step 2: No commit** (verification only).

---

## Task 7: Pre-flight services check

**Files:** none.

- [ ] **Step 1: Verify Qdrant is up**

```bash
docker ps | grep creditintel-qdrant
```

Expected: shows `Up`. If not, start it:

```bash
docker start creditintel-qdrant
```

- [ ] **Step 2: Verify Qdrant has hybrid collection (Stage 1 was ingested)**

```bash
curl -s http://localhost:6333/collections/creditintel-kb | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('points:', d['result']['points_count'])
print('vectors:', list(d['result']['config']['params']['vectors'].keys()))
print('sparse_vectors:', list(d['result']['config']['params'].get('sparse_vectors', {}).keys()))
"
```

Expected:
```
points: 28
vectors: ['dense']
sparse_vectors: ['sparse']
```

If sparse_vectors is empty, Stage 1 needs to be re-ingested first (`PYTHONPATH=. ../.venv/bin/python -m rag.ingest --recreate` from `backend/`).

- [ ] **Step 3: Verify OPENROUTER_API_KEY is set**

```bash
grep -c OPENROUTER_API_KEY /home/taitu/GitHub/Loan_ETL/backend/.env
```

Expected: `1` (key is present in env).

- [ ] **Step 4: No commit** (verification only).

---

## Task 8: Smoke test live rerank pipeline (triggers model download)

**Files:** none — operates on live services.

- [ ] **Step 1: First live query — model downloads (~1.11 GB)**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONUNBUFFERED=1 PYTHONPATH=. ../.venv/bin/python -u -c "
import time
from rag.retriever import get_retriever
t0 = time.time()
docs = get_retriever().invoke('DTI là gì')
print(f'Got {len(docs)} docs in {time.time()-t0:.1f}s')
for d in docs[:3]:
    print('-', d.metadata.get('source'), '::', d.metadata.get('section_title'))
"
```

Expected on FIRST run: prints download progress for `jinaai/jina-reranker-v2-base-multilingual`, takes 2-5 minutes depending on bandwidth, then prints `Got 4 docs in N.Ns` with N typically 5-15s on first call (cold model load). 

If you see a Python traceback with `SIGSEGV` / `exit code 139` / `core dumped` / `BrokenPipe`, abort and report — the Python 3.12 migration may have an unexpected interaction with the rerank model. Do NOT retry blindly.

- [ ] **Step 2: Second query — warm cache, should be fast**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -c "
import time
from rag.retriever import get_retriever
t0 = time.time()
docs = get_retriever().invoke('Tôi muốn vay 50 triệu')
print(f'Got {len(docs)} docs in {time.time()-t0:.1f}s')
"
```

Expected: returns in 1-3 seconds; `Got 4 docs in N.Ns` where N < 3.

- [ ] **Step 3: Verify model is cached**

```bash
ls -lah ~/.cache/fastembed/ 2>/dev/null | head
du -sh ~/.cache/fastembed/* 2>/dev/null
```

Expected: directories for the BM25 model AND `jina-reranker-v2-base-multilingual` (~1.1 GB).

- [ ] **Step 4: No commit** (verification only).

---

## Task 9: Live eval + diff vs Stage 1 baseline

**Files:**
- Create: `docs/rag_eval_results_rerank.json`
- Create: `docs/rag_eval_diff_rerank.json`

- [ ] **Step 1: Run eval against Stage 1 (hybrid) baseline**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONUNBUFFERED=1 PYTHONPATH=. ../.venv/bin/python -u -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results_rerank.json \
  --baseline ../docs/rag_eval_results_hybrid.json \
  --diff ../docs/rag_eval_diff_rerank.json
```

Expected: 31 cases scored, terminal prints `Eval complete: 31 cases, avg_overall=<float>`. Exit code 0 means no per-case regression; exit code 1 means the runner flagged something.

Per-case rerank latency adds time — total run can take 5-10 minutes (vs ~3-5 for Stage 1). Be patient; do not interrupt.

- [ ] **Step 2: Inspect the diff**

```bash
/home/taitu/GitHub/Loan_ETL/.venv/bin/python -c "
import json
with open('/home/taitu/GitHub/Loan_ETL/docs/rag_eval_diff_rerank.json') as f:
    d = json.load(f)
s = d['summary']
print('has_regression:', d['has_regression'])
print('avg_overall_delta:', round(s.get('avg_overall_delta', 0), 4))
print('avg_faithfulness_delta:', round(s.get('avg_faithfulness_delta', 0), 4))
print('avg_context_precision_delta:', round(s.get('avg_context_precision_delta', 0), 4))
print('run_regressed:', s.get('run_regressed'))
print('regressed_case_ids:', d.get('regressed_case_ids'))
print('improved_case_ids:', d.get('improved_case_ids'))
"
```

- [ ] **Step 3: Decide pass band per spec acceptance**

Per the spec acceptance bands:

| Band | `avg_overall_delta` | Action |
|---|---|---|
| **Strict pass** | `> +0.02` | Commit; rerank works; move to Stage 3. |
| **Soft pass** | `+0.005` to `+0.02` | Commit; file V1.1 follow-up to investigate further lift. |
| **Neutral** | `-0.005` to `+0.005` | Commit with caveat; brainstorm V1.1 model swap (`bge-reranker-v2-m3` via sentence-transformers). |
| **Regression** | `< -0.005` | STOP. Do NOT commit results-as-win. File V1.1 investigate-or-revert spec. |

Inspect the printed delta and pick the band. If regression: stop here, do not run Step 4.

- [ ] **Step 4: Commit the eval artefacts (only if pass / neutral)**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add docs/rag_eval_results_rerank.json docs/rag_eval_diff_rerank.json
git commit -m "eval: Stage 2 rerank results + diff vs Stage 1 hybrid baseline"
```

If neutral, edit the commit message to add `(neutral — see V1.1 follow-up)` so the band is recorded in git history.

---

## Task 10: Final verification

- [ ] **Step 1: Re-run the full standalone test sweep**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All tests passed"
```

Expected: every test prints its pass line.

- [ ] **Step 2: Confirm git log shows the expected commit chain**

```bash
cd /home/taitu/GitHub/Loan_ETL
git log --oneline ceea806..HEAD
```

Expected: 6 commits — Task 1 (settings), Task 2 (Reranker class), Task 3 (RerankedRetriever), Task 4 (pipeline wire-up), Task 5 (docs), Task 9 (eval artefacts).

- [ ] **Step 3: No commit** (verification only).

---

## Acceptance criteria

1. `backend/rag/reranker.py` exists with `Reranker` class + `get_reranker()` singleton.
2. `backend/rag/retriever.py` has `RerankedRetriever` wrapper class.
3. `get_retriever()` returns `ParentDocumentRetriever(RerankedRetriever(hybrid, reranker=get_reranker(), top_k=12), max_parent_docs=4)`.
4. Hybrid stage requests `RERANKER_CANDIDATE_K` (20) candidates from Qdrant.
5. `rag_reranker_enabled=False` → `RerankedRetriever.reranker is None` → pipeline behaves like Stage 1.
6. Reranker failures (init or per-query) fall back to raw candidate slice — never raise to caller.
7. New tests `test_rag_reranker.py` + `test_rag_retriever_uses_reranker.py` pass.
8. All existing RAG / chat / memory / eval tests still pass.
9. `docs/rag_eval_results_rerank.json` + `docs/rag_eval_diff_rerank.json` committed if band is pass or neutral; not committed if band is regression.
10. CLAUDE.md notes the ~1.11 GB first-run model download for the reranker.

If criterion 9 fails (regression band), this stage is **not done** — file a V1.1 follow-up spec to investigate (likely model swap to `bge-reranker-v2-m3`) before merging.
