# RAG Retrieval Rerank V1.1 Follow-up Investigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run controlled reranker V1.1 experiments to recover `FAQ-03` and improve Stage 2's `+0.0152` soft-pass lift without committing unmeasured retrieval changes.

**Architecture:** Add one behavior-preserving setting, `rag_reranker_top_k`, so candidate-k and rerank child top-k can be varied through environment variables in separate eval processes. Then run deterministic live eval variants against `docs/rag_eval_results_hybrid_temp0.json`; only update production defaults if a variant beats Stage 2 and satisfies the no-new-severe-regression gate.

**Tech Stack:** Python 3.12.13 (`/home/taitu/GitHub/Loan_ETL/.venv/bin/python`), FastAPI backend RAG modules, `fastembed` reranker cache, Qdrant local container, OpenRouter eval runner. Tests are standalone scripts in `backend/tests_local/`.

**Spec:** [docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md](../specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md)

---

## File Structure

**Modified code files:**
- `backend/core/config.py` - add `rag_reranker_top_k: int = 12`.
- `backend/rag/config.py` - export `RERANKER_TOP_K`.
- `backend/rag/retriever.py` - use `RERANKER_TOP_K` when constructing `RerankedRetriever`.
- `backend/tests_local/test_rag_retriever_uses_reranker.py` - assert the pipeline uses the configured rerank child top-k.

**New eval artifacts, generated only by live experiments:**
- `docs/rag_eval_results_rerank_v11_k16_top12.json`
- `docs/rag_eval_diff_rerank_v11_k16_top12.json`
- `docs/rag_eval_results_rerank_v11_k20_top16.json`
- `docs/rag_eval_diff_rerank_v11_k20_top16.json`
- `docs/rag_eval_results_rerank_v11_k24_top12.json`
- `docs/rag_eval_diff_rerank_v11_k24_top12.json`

**Modified defaults if an experiment wins:**
- `backend/core/config.py`
- `backend/tests_local/test_rag_retriever_uses_reranker.py`
- `docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md`

---

## Baseline Facts

Stage 2 committed eval result:

```text
commit: 2434721 eval: Stage 2 rerank — soft pass (+0.0152) on deterministic eval
baseline file for V1.1 comparisons: docs/rag_eval_results_hybrid_temp0.json
stage2 current file: docs/rag_eval_results_rerank_temp0.json
stage2 diff file: docs/rag_eval_diff_rerank_temp0.json
stage2 avg_overall_delta: +0.0152
stage2 regressed_case_ids: ['FAQ-03']
stage2 improved_case_ids: ['PERSONAL-02', 'PERSONAL-04', 'POLICY-03']
```

V1.1 experiments must beat `+0.0152` to justify changing defaults. A strict win is `avg_overall_delta > +0.02`.

---

## Task 1: Add Configurable Rerank Child Top-K - TDD

**Files:**
- Modify: `backend/core/config.py`
- Modify: `backend/rag/config.py`
- Modify: `backend/rag/retriever.py`
- Modify: `backend/tests_local/test_rag_retriever_uses_reranker.py`

- [ ] **Step 1: Write the failing test**

Open `backend/tests_local/test_rag_retriever_uses_reranker.py`. Add this test above the `if __name__ == "__main__":` block:

```python
def test_get_retriever_uses_configured_reranker_top_k():
    """RerankedRetriever.top_k should come from RERANKER_TOP_K, not TOP_K * 3."""
    from core.config import settings
    from rag.retriever import RerankedRetriever

    originals = _patch_retriever_module()
    try:
        r = retriever_mod.get_retriever()
        rr = r.child_retriever
    finally:
        _unpatch_retriever_module(originals)

    assert isinstance(rr, RerankedRetriever)
    assert rr.top_k == settings.rag_reranker_top_k
```

Then update the `if __name__ == "__main__":` block to call it:

```python
if __name__ == "__main__":
    test_reranked_retriever_passthrough_when_reranker_is_none()
    test_reranked_retriever_uses_reranker_when_provided()
    test_reranked_retriever_falls_back_on_rerank_failure()
    test_get_retriever_requests_candidate_k_from_hybrid()
    test_get_retriever_chain_is_parent_of_reranked_of_hybrid()
    test_get_retriever_respects_reranker_disabled()
    test_get_retriever_uses_configured_reranker_top_k()
    print("rag retriever uses reranker tests passed")
```

- [ ] **Step 2: Run - expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
```

Expected: `AttributeError: 'Settings' object has no attribute 'rag_reranker_top_k'`.

- [ ] **Step 3: Add the new setting**

Open `backend/core/config.py`. In the "RAG retrieval Stage 2 (reranker)" block, add:

```python
    rag_reranker_top_k: int = 12
```

The block should become:

```python
    # RAG retrieval Stage 2 (reranker)
    rag_reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rag_reranker_enabled: bool = True
    rag_reranker_candidate_k: int = 20
    rag_reranker_top_k: int = 12
```

- [ ] **Step 4: Export the module constant**

Open `backend/rag/config.py`. After `RERANKER_CANDIDATE_K = ...`, add:

```python
RERANKER_TOP_K = settings.rag_reranker_top_k
```

- [ ] **Step 5: Use the configured top-k in `get_retriever()`**

Open `backend/rag/retriever.py`. Update the import tuple:

```python
from rag.config import (
    BM25_SPARSE_MODEL, EMBEDDING_MODEL, OPENROUTER_BASE_URL,
    QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL,
    RERANKER_CANDIDATE_K, RERANKER_TOP_K, TOP_K,
)
```

Then replace:

```python
reranked = RerankedRetriever(hybrid, reranker=get_reranker(), top_k=TOP_K * 3)
```

with:

```python
reranked = RerankedRetriever(hybrid, reranker=get_reranker(), top_k=RERANKER_TOP_K)
```

- [ ] **Step 6: Verify imports**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python -c "
from rag.config import RERANKER_CANDIDATE_K, RERANKER_TOP_K
print(RERANKER_CANDIDATE_K, RERANKER_TOP_K)
"
```

Expected:

```text
20 12
```

- [ ] **Step 7: Run targeted tests - expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_reranker.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_hybrid_config.py
```

Expected:

```text
rag retriever uses reranker tests passed
rag reranker tests passed
rag retriever hybrid config tests passed
```

The fallback tests may log expected tracebacks; exit code must be 0.

- [ ] **Step 8: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/core/config.py backend/rag/config.py backend/rag/retriever.py backend/tests_local/test_rag_retriever_uses_reranker.py
git commit -m "feat: make reranker child top-k configurable"
```

---

## Task 2: Pre-Live Non-Live Sweep

**Files:** none.

- [ ] **Step 1: Run the non-live sweep with legacy live excludes**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
SKIP=(
  tests_local/test_rag_benchmark.py
  tests_local/test_rag_evaluation_notebook.py
)
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    skip=false
    for s in "${SKIP[@]}"; do
        [[ "$f" == "$s" ]] && skip=true && break
    done
    [[ "$skip" == true ]] && { echo "=== $f === SKIPPED (live)"; continue; }
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All non-live tests passed"
```

Expected: exit code 0 and final line `All non-live tests passed`.

- [ ] **Step 2: No commit**

This is verification only.

---

## Task 3: Pre-Flight Live Services Check

**Files:** none.

- [ ] **Step 1: Verify Qdrant is up**

```bash
docker ps | grep creditintel-qdrant
```

Expected: a row containing `creditintel-qdrant` and `Up`.

If Docker access is denied by sandbox, rerun with approved escalation. If the container is not running, start it:

```bash
docker start creditintel-qdrant
```

- [ ] **Step 2: Verify the hybrid collection**

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

```text
points: 28
vectors: ['dense']
sparse_vectors: ['sparse']
```

- [ ] **Step 3: Verify OpenRouter key presence**

```bash
grep -c OPENROUTER_API_KEY /home/taitu/GitHub/Loan_ETL/backend/.env
```

Expected:

```text
1
```

- [ ] **Step 4: Verify model cache**

```bash
ls -lah /tmp/fastembed_cache
du -sh /tmp/fastembed_cache/* 2>/dev/null
```

Expected: both `models--Qdrant--bm25` and `models--jinaai--jina-reranker-v2-base-multilingual`; Jina reranker size is about `1.1G`.

- [ ] **Step 5: No commit**

This is verification only.

---

## Task 4: Run Candidate/Top-K Variant Evals

**Files:**
- Create: `docs/rag_eval_results_rerank_v11_k16_top12.json`
- Create: `docs/rag_eval_diff_rerank_v11_k16_top12.json`
- Create: `docs/rag_eval_results_rerank_v11_k20_top16.json`
- Create: `docs/rag_eval_diff_rerank_v11_k20_top16.json`
- Create: `docs/rag_eval_results_rerank_v11_k24_top12.json`
- Create: `docs/rag_eval_diff_rerank_v11_k24_top12.json`

**Important:** Each eval can take 10-20 minutes. Do not interrupt quiet runs. If a runtime error occurs, stop and report the full output.

- [ ] **Step 1: Run variant k16/top12**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
RAG_RERANKER_CANDIDATE_K=16 RAG_RERANKER_TOP_K=12 \
PYTHONUNBUFFERED=1 PYTHONPATH=. ../.venv/bin/python -u -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results_rerank_v11_k16_top12.json \
  --baseline ../docs/rag_eval_results_hybrid_temp0.json \
  --diff ../docs/rag_eval_diff_rerank_v11_k16_top12.json
```

Expected: exit code 0.

- [ ] **Step 2: Run variant k20/top16**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
RAG_RERANKER_CANDIDATE_K=20 RAG_RERANKER_TOP_K=16 \
PYTHONUNBUFFERED=1 PYTHONPATH=. ../.venv/bin/python -u -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results_rerank_v11_k20_top16.json \
  --baseline ../docs/rag_eval_results_hybrid_temp0.json \
  --diff ../docs/rag_eval_diff_rerank_v11_k20_top16.json
```

Expected: exit code 0.

- [ ] **Step 3: Run variant k24/top12**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
RAG_RERANKER_CANDIDATE_K=24 RAG_RERANKER_TOP_K=12 \
PYTHONUNBUFFERED=1 PYTHONPATH=. ../.venv/bin/python -u -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results_rerank_v11_k24_top12.json \
  --baseline ../docs/rag_eval_results_hybrid_temp0.json \
  --diff ../docs/rag_eval_diff_rerank_v11_k24_top12.json
```

Expected: exit code 0.

- [ ] **Step 4: Summarize all variants**

```bash
cd /home/taitu/GitHub/Loan_ETL
/home/taitu/GitHub/Loan_ETL/.venv/bin/python - <<'PY'
import json
from pathlib import Path

variants = [
    ("stage2", Path("docs/rag_eval_diff_rerank_temp0.json")),
    ("k16_top12", Path("docs/rag_eval_diff_rerank_v11_k16_top12.json")),
    ("k20_top16", Path("docs/rag_eval_diff_rerank_v11_k20_top16.json")),
    ("k24_top12", Path("docs/rag_eval_diff_rerank_v11_k24_top12.json")),
]

for name, path in variants:
    d = json.loads(path.read_text(encoding="utf-8"))
    s = d["summary"]
    cases = {case["id"]: case for case in d["cases"]}
    faq03 = cases.get("FAQ-03", {})
    print(f"=== {name} ===")
    print("file:", path)
    print("avg_overall_delta:", round(s.get("avg_overall_delta", 0), 4))
    print("run_regressed:", s.get("run_regressed"))
    print("has_regression:", d.get("has_regression"))
    print("regressed_case_ids:", d.get("regressed_case_ids"))
    print("improved_case_ids:", d.get("improved_case_ids"))
    print("FAQ-03 overall_delta:", faq03.get("overall_delta"))
    print()
PY
```

Expected: prints all four summaries.

- [ ] **Step 5: Decide experiment result**

Use this gate:

| Outcome | Condition | Action |
|---|---|---|
| Strict win | Any V1.1 variant has `avg_overall_delta > +0.02` and no new regressed case worse than `FAQ-03`'s Stage 2 `-0.2` drop | Continue to Task 5. |
| Soft improvement | Best V1.1 variant is `> +0.0152` but `<= +0.02` | Continue to Task 5, but commit with caveat. |
| No improvement | No variant beats Stage 2's `+0.0152` | Do not promote defaults; continue to Task 6 to document no candidate/top-k improvement. |
| Regression | Best variant is worse than Stage 2 or introduces severe new regressions | Stop, leave artifacts uncommitted, report summary. |

---

## Task 5: Promote Winning Retrieval Shape (Only If Task 4 Finds a Winner)

**Files:**
- Modify: `backend/core/config.py`
- Modify: `docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md`
- Commit relevant winning eval artifacts from Task 4.

Skip this task if Task 4 finds no winning variant.

- [ ] **Step 1: Update default settings**

If `k20_top16` wins, update `backend/core/config.py`:

```python
    rag_reranker_candidate_k: int = 20
    rag_reranker_top_k: int = 16
```

If `k16_top12` wins, update:

```python
    rag_reranker_candidate_k: int = 16
    rag_reranker_top_k: int = 12
```

If `k24_top12` wins, update:

```python
    rag_reranker_candidate_k: int = 24
    rag_reranker_top_k: int = 12
```

- [ ] **Step 2: Update the follow-up spec with the selected result**

Open `docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md`. Under "Investigation Plan", add a short "Experiment result" subsection using the exact values printed in Task 4 Step 4:

```markdown
### Experiment result

Selected variant: k20_top16.

Reason:
- `avg_overall_delta`: value printed for k20_top16
- `regressed_case_ids`: list printed for k20_top16
- `improved_case_ids`: list printed for k20_top16

This variant is promoted to defaults in `backend/core/config.py`.
```

If `k16_top12` or `k24_top12` wins instead, use that exact variant name and its printed values. Do not invent or round values differently from the Task 4 summary.

- [ ] **Step 3: Run targeted tests**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_uses_reranker.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_retriever_hybrid_config.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Expected: all pass.

- [ ] **Step 4: Commit code/defaults and winning artifacts**

For `k20_top16`, run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/core/config.py docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md \
  docs/rag_eval_results_rerank_v11_k20_top16.json docs/rag_eval_diff_rerank_v11_k20_top16.json
git commit -m "feat: tune reranker retrieval shape from V1.1 eval"
```

For `k16_top12`, replace the two artifact paths with:

```text
docs/rag_eval_results_rerank_v11_k16_top12.json docs/rag_eval_diff_rerank_v11_k16_top12.json
```

For `k24_top12`, replace them with:

```text
docs/rag_eval_results_rerank_v11_k24_top12.json docs/rag_eval_diff_rerank_v11_k24_top12.json
```

---

## Task 6: Document No-Improvement Result (Only If Task 4 Finds No Winner)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md`
- Commit: all six candidate/top-k eval artifacts as investigation evidence, not as a production win.

Skip this task if Task 5 ran.

- [ ] **Step 1: Update the follow-up spec**

Add this subsection under "Investigation Plan":

```markdown
### Candidate/top-k result

The candidate/top-k variants did not beat Stage 2's `+0.0152` soft-pass result.
Keep Stage 2 defaults for now:

- `rag_reranker_candidate_k=20`
- `rag_reranker_top_k=12`

Next investigation step: prototype FAQ source preservation before considering
the heavier `BAAI/bge-reranker-v2-m3` model swap.
```

- [ ] **Step 2: Commit the documentation update and investigation artifacts**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add docs/superpowers/specs/2026-05-19-rag-retrieval-rerank-v1.1-follow-up-design.md \
  docs/rag_eval_results_rerank_v11_k16_top12.json docs/rag_eval_diff_rerank_v11_k16_top12.json \
  docs/rag_eval_results_rerank_v11_k20_top16.json docs/rag_eval_diff_rerank_v11_k20_top16.json \
  docs/rag_eval_results_rerank_v11_k24_top12.json docs/rag_eval_diff_rerank_v11_k24_top12.json
git commit -m "eval: document rerank V1.1 candidate-k investigation"
```

---

## Task 7: Final Verification

**Files:** none.

- [ ] **Step 1: Run final non-live sweep**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
SKIP=(
  tests_local/test_rag_benchmark.py
  tests_local/test_rag_evaluation_notebook.py
)
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    skip=false
    for s in "${SKIP[@]}"; do
        [[ "$f" == "$s" ]] && skip=true && break
    done
    [[ "$skip" == true ]] && { echo "=== $f === SKIPPED (live)"; continue; }
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All non-live tests passed"
```

Expected: exit code 0 and final line `All non-live tests passed`.

- [ ] **Step 2: Inspect final status**

```bash
cd /home/taitu/GitHub/Loan_ETL
git status --short --branch
git log --oneline 2434721..HEAD
```

Expected:

- Clean working tree unless Task 4 ended in regression and artifacts were intentionally left uncommitted.
- Commit list includes Task 1 config commit and either Task 5 or Task 6 outcome commit.

---

## Stop Conditions

Stop and report full output if:

- Any non-live test fails after the Task 1 config change.
- Docker/Qdrant/OpenRouter pre-flight checks fail.
- Any live eval command exits nonzero.
- A live eval produces a worse-than-Stage-2 result and the next action is ambiguous.
- A proposed production default would reduce `avg_overall_delta` below `+0.0152`.

Do not push. Do not amend commits. Do not skip hooks.
