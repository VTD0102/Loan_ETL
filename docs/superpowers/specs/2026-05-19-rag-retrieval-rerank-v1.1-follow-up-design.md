# RAG Retrieval Rerank V1.1 - Follow-up Investigation

**Date**: 2026-05-19
**Status**: Proposed follow-up after Stage 2 soft pass
**Scope**: Retrieval evaluation only at first; implementation is deferred until
the investigation identifies a measured change.

## Why

Stage 2 rerank landed with a deterministic eval soft pass:

- Eval artifacts: `docs/rag_eval_results_hybrid_temp0.json`,
  `docs/rag_eval_results_rerank_temp0.json`,
  `docs/rag_eval_diff_rerank_temp0.json`
- `avg_overall_delta`: `+0.0152`
- Current overall: `0.8397`
- Baseline overall: `0.8245`
- Improved cases: `PERSONAL-02`, `PERSONAL-04`, `POLICY-03`
- Regressed case: `FAQ-03`

This is enough to keep Stage 2, but not enough to stop tuning. The main
negative signal is narrow: `FAQ-03` kept answer faithfulness at `1.0`, but
context precision fell from `1.0` to `0.5` because rerank replaced two FAQ
contexts with policy contexts for the question "Lam the nao de giam DTI cua
toi?". That suggests the cross-encoder can over-promote generally relevant
policy sections over more directly actionable FAQ sections.

## Goals

1. Preserve Stage 2's soft-pass lift while recovering `FAQ-03`.
2. Keep the fallback contract: reranker failures never break retrieval.
3. Avoid adding heavy dependencies until a measured comparison justifies them.
4. Keep the V1 eval framework as the gate for every variant.

## Non-goals

- No query rewriting; that remains Stage 3.
- No prompt changes unless the retrieval-only variants fail to explain the
  remaining gap.
- No unmeasured model swap.
- No committing eval artifacts from a regression run as a win.

## Investigation Plan

### Experiment 1 - Candidate/top-k sensitivity

Run the same 31-case eval for small retrieval shape variants:

- `rag_reranker_candidate_k=16`, rerank top `12`
- `rag_reranker_candidate_k=20`, rerank top `16`
- `rag_reranker_candidate_k=24`, rerank top `12`

Acceptance: choose a variant only if `avg_overall_delta >= +0.02` and no case
regresses by more than the current `FAQ-03` drop.

### Candidate/top-k result

The candidate/top-k variants did not beat Stage 2's `+0.0152` soft-pass result.
Keep Stage 2 defaults for now:

- `rag_reranker_candidate_k=20`
- `rag_reranker_top_k=12`

Next investigation step: prototype FAQ source preservation before considering
the heavier `BAAI/bge-reranker-v2-m3` model swap.

### Experiment 2 - FAQ source preservation

Prototype a retrieval-only rule that preserves at least one high-ranked FAQ
parent when the query is FAQ-like and FAQ candidates are present before rerank.
Do this as an A/B branch, not as a blind production change.

Evidence to collect:

- Does `FAQ-03` return to context precision `1.0`?
- Does the rule harm policy cases such as `POLICY-03`?
- Does it change guardrail or personalized groups?

Acceptance: keep only if run-level delta improves over `+0.0152` and no new
case regression appears.

### Experiment 3 - Alternative reranker model

If retrieval-shape tuning and FAQ preservation do not improve the run, evaluate
`BAAI/bge-reranker-v2-m3` via `sentence-transformers` in an isolated branch.

This is deliberately last because it adds a heavier dependency stack and likely
larger local model footprint. The model swap should be accepted only if it gives
a strict pass (`avg_overall_delta > +0.02`) or removes `FAQ-03` without losing
the personalized gains.

## Required Eval Commands

Each experiment must run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONUNBUFFERED=1 PYTHONPATH=. ../.venv/bin/python -u -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results_<variant>.json \
  --baseline ../docs/rag_eval_results_hybrid_temp0.json \
  --diff ../docs/rag_eval_diff_<variant>.json
```

Then inspect:

```bash
/home/taitu/GitHub/Loan_ETL/.venv/bin/python -c "
import json
with open('/home/taitu/GitHub/Loan_ETL/docs/rag_eval_diff_<variant>.json') as f:
    d = json.load(f)
s = d['summary']
print('has_regression:', d['has_regression'])
print('avg_overall_delta:', round(s.get('avg_overall_delta', 0), 4))
print('run_regressed:', s.get('run_regressed'))
print('regressed_case_ids:', d.get('regressed_case_ids'))
print('improved_case_ids:', d.get('improved_case_ids'))
"
```

## Completion Criteria

- A V1.1 implementation plan exists only after one experiment shows a measured
  improvement over Stage 2's `+0.0152` result.
- If no variant beats Stage 2, keep the current reranker and document the
  remaining `FAQ-03` tradeoff as accepted.
- Final non-live sweeps must continue to skip legacy live checks:
  `test_rag_benchmark.py` and `test_rag_evaluation_notebook.py`.
