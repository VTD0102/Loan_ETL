# RAG Eval + Memory V1.1 Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 6 fixes flagged by the eval framework + memory V1.1 audit: cleaner `--baseline` UX, missing test coverage for run-level regression / error-continue paths, an overly-broad must_include phrase, and the right name/location for the excluded-user-message test.

**Architecture:** Six surgical edits across `eval_runner.py`, `eval_metrics.py`'s tests, the eval dataset, and three memory/chat tests. Each fix is a single commit. Independent of the KB chunking plan — no shared files.

**Tech Stack:** Standalone Python test scripts under `backend/tests_local/`, `argparse`-driven eval CLI, JSON-on-disk fixtures.

**Spec:** [docs/superpowers/specs/2026-05-19-rag-eval-and-memory-polish-design.md](../specs/2026-05-19-rag-eval-and-memory-polish-design.md)

**Independent from:** `docs/superpowers/plans/2026-05-19-rag-kb-chunking-v1.1-fixes.md` — runs in parallel without overlap.

---

## File Structure

**Modified files:**
- `backend/rag/eval_runner.py` — wrap baseline read in try/except → `ValueError`.
- `backend/tests_local/test_rag_eval_runner.py` — 2 new tests (missing baseline, error-continue).
- `backend/tests_local/test_rag_eval_diff.py` — 2 new tests (run-level regression, `same` status).
- `docs/rag_eval_dataset.json` — FAQ-07 `must_include` entry.
- `backend/tests_local/test_memory_excludes_error_rows.py` — tighten assertion to a call-count.
- `backend/tests_local/test_chat_service_uses_memory.py` — extract the excluded-user-message test.
- `backend/tests_local/test_chat_service_excludes_current_user_message.py` — new file.

**No source-code changes outside `eval_runner.py`.**

---

## Task 1: FAQ-07 dataset fix (E4)

**Files:**
- Modify: `docs/rag_eval_dataset.json` (FAQ-07 entry)

- [ ] **Step 1: Locate the entry**

```bash
grep -n -A 6 '"FAQ-07"' /home/taitu/GitHub/Loan_ETL/docs/rag_eval_dataset.json
```

Confirm the `must_include` field contains `"1"`, `"3 ngày làm việc|1-3 ngày"`, `"PENDING_REVIEW"`.

- [ ] **Step 2: Edit the file**

Replace the single-character `"1"` entry with the alternative-form phrase:

```diff
"must_include": [
-  "1",
+  "1 ngày|1-3 ngày",
   "3 ngày làm việc|1-3 ngày",
   "PENDING_REVIEW"
],
```

- [ ] **Step 3: Verify dataset still parses + tests still pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_eval_dataset.py
```

Expected: `RAG eval dataset checks passed.`.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add docs/rag_eval_dataset.json
git commit -m "fix: FAQ-07 must_include uses alternative form (not the bare digit '1')"
```

---

## Task 2: `--baseline` missing-file UX (E1)

**Files:**
- Modify: `backend/rag/eval_runner.py` (around line 122 — the call site `_read_results(baseline)`)
- Test: `backend/tests_local/test_rag_eval_runner.py` (new test)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests_local/test_rag_eval_runner.py`:

```python
def test_run_eval_file_missing_baseline_raises_value_error(tmp_path=None):
    import tempfile
    import json
    from pathlib import Path
    from rag.eval_runner import run_eval_file

    tmp = Path(tempfile.mkdtemp())
    dataset = tmp / "ds.json"
    dataset.write_text(json.dumps([{
        "id": "T-01", "group": "faq", "question": "q", "ground_truth": "gt",
        "expected_behavior": "...", "must_include": [], "must_not_include": [],
        "expected_context_terms": [], "expected_sources": [],
    }]), encoding="utf-8")

    output = tmp / "out.json"
    diff = tmp / "diff.json"
    bogus_baseline = tmp / "does_not_exist.json"

    def stub_invoke(question, context):
        return {"answer": "", "source_documents": []}

    raised = None
    try:
        run_eval_file(
            str(dataset),
            str(output),
            baseline_path=str(bogus_baseline),
            diff_output_path=str(diff),
            invoke_func=stub_invoke,
            enforce_dataset_size=False,
        )
    except ValueError as exc:
        raised = exc
    assert raised is not None, "expected ValueError when baseline missing"
    assert "Baseline" in str(raised) or "baseline" in str(raised)
    assert str(bogus_baseline) in str(raised)
```

Add to the `if __name__ == "__main__":` block.

NOTE: `run_eval_file` may use a different parameter name than `baseline_path` / `diff_output_path` — read the function signature in `eval_runner.py` first and use the actual names. Likewise, `invoke_func` and `enforce_dataset_size` may have different names — check.

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_eval_runner.py
```

Expected: `FileNotFoundError` (raw, not wrapped) propagates → test gets the wrong exception type and fails on `raised is not None`.

- [ ] **Step 3: Wrap the read in `eval_runner.py`**

Open `/home/taitu/GitHub/Loan_ETL/backend/rag/eval_runner.py`. Locate the block:

```python
if baseline is not None:
    diff = diff_results(results, _read_results(baseline))
```

Replace with:

```python
if baseline is not None:
    try:
        baseline_results = _read_results(baseline)
    except FileNotFoundError as exc:
        raise ValueError(f"Baseline file not found: {baseline}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read baseline file {baseline}: {exc}") from exc
    diff = diff_results(results, baseline_results)
```

Make sure `json` is imported at the top of the file — it likely already is for `_read_results` / `_write_json`. If not, add `import json` near the top.

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_eval_runner.py
```

Expected: `RAG eval runner checks passed.`.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/eval_runner.py backend/tests_local/test_rag_eval_runner.py
git commit -m "fix: clean error when --baseline file is missing (ValueError → exit 2)"
```

---

## Task 3: Run-level regression test + `same` status test (E2)

**Files:**
- Test: `backend/tests_local/test_rag_eval_diff.py` (2 new test functions)

- [ ] **Step 1: Read existing thresholds**

```bash
grep -n "0.05\|0.15\|run_regressed" /home/taitu/GitHub/Loan_ETL/backend/rag/eval_metrics.py
```

Confirm the per-case threshold is `-0.15` (or similar) and the run-level threshold is `-0.05`. Adjust the test values below if the numbers in the code differ.

- [ ] **Step 2: Append the 2 new tests**

```python
def test_diff_results_run_level_regression_triggers_has_regression():
    """Avg overall drop > 0.05 flags regression even when no case regresses individually."""
    baseline = [
        {"id": "FAQ-01", "group": "faq", "faithfulness": 1.0, "context_precision": 1.0, "overall": 1.0},
        {"id": "FAQ-02", "group": "faq", "faithfulness": 1.0, "context_precision": 1.0, "overall": 1.0},
    ]
    current = [
        {"id": "FAQ-01", "group": "faq", "faithfulness": 0.93, "context_precision": 0.93, "overall": 0.93},
        {"id": "FAQ-02", "group": "faq", "faithfulness": 0.93, "context_precision": 0.93, "overall": 0.93},
    ]

    diff = diff_results(current, baseline)

    statuses = {c["id"]: c["status"] for c in diff["cases"]}
    assert statuses["FAQ-01"] == "same", "individual case below per-case regression threshold"
    assert statuses["FAQ-02"] == "same"
    assert diff["regressed_case_ids"] == []
    assert diff["summary"]["run_regressed"] is True, "run-level avg drop must flag regression"
    assert diff["has_regression"] is True


def test_diff_results_marks_unchanged_case_as_same():
    baseline = [{"id": "FAQ-01", "group": "faq", "faithfulness": 0.8, "context_precision": 0.8, "overall": 0.8}]
    current = [{"id": "FAQ-01", "group": "faq", "faithfulness": 0.8, "context_precision": 0.8, "overall": 0.8}]

    diff = diff_results(current, baseline)

    assert diff["cases"][0]["status"] == "same"
    assert diff["cases"][0]["overall_delta"] == 0.0
    assert diff["has_regression"] is False
    assert diff["improved_case_ids"] == []
    assert diff["regressed_case_ids"] == []
```

Wire both into `if __name__ == "__main__":`.

- [ ] **Step 3: Run**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_eval_diff.py
```

Expected: `RAG eval diff checks passed.` — including the two new assertions.

If the run-level regression test fails because the per-case threshold (`-0.07` here) exceeds the actual per-case threshold (maybe it's `-0.05` not `-0.15`?), tweak `0.93 → 0.97` so the per-case delta of `-0.03` is unambiguously above the per-case bar but the average drop of `-0.03` is still inside the run-level bar. Verify against the constants in `eval_metrics.py`.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_rag_eval_diff.py
git commit -m "test: cover run-level regression threshold and 'same' status in diff_results"
```

---

## Task 4: Error-continue test (E3)

**Files:**
- Test: `backend/tests_local/test_rag_eval_runner.py` (new test)

- [ ] **Step 1: Read `run_eval_cases` to confirm signature**

```bash
grep -n "def run_eval_cases" /home/taitu/GitHub/Loan_ETL/backend/rag/eval_runner.py
```

Note the parameter names — `invoke_func` vs `invoker`, `stop_on_error` etc. Use the real names below.

- [ ] **Step 2: Append the new test**

```python
def test_run_eval_cases_records_invoker_error_and_continues():
    """When the invoker raises for one case, the run continues and the error is recorded."""
    from rag.eval_runner import run_eval_cases

    base_case = {
        "group": "g",
        "expected_behavior": "...",
        "must_include": [],
        "must_not_include": [],
        "expected_context_terms": [],
        "expected_sources": [],
    }
    cases = [
        {**base_case, "id": "OK-1", "question": "q1", "ground_truth": "gt1"},
        {**base_case, "id": "BAD-2", "question": "q2", "ground_truth": "gt2"},
        {**base_case, "id": "OK-3", "question": "q3", "ground_truth": "gt3"},
    ]
    attempted = []

    def flaky_invoke(question, context):
        attempted.append(question)
        if question == "q2":
            raise RuntimeError("upstream blip")
        return {"answer": "stub", "source_documents": []}

    results = run_eval_cases(cases, invoke_func=flaky_invoke)

    assert attempted == ["q1", "q2", "q3"], "all 3 cases must be attempted, even after failure"
    by_id = {r["id"]: r for r in results}
    assert "error" in by_id["BAD-2"] and "upstream blip" in by_id["BAD-2"]["error"]
    assert "error" not in by_id["OK-3"]
    assert "error" not in by_id["OK-1"]
```

Adjust `invoke_func=` to whichever kwarg name `run_eval_cases` accepts.

Wire into `if __name__ == "__main__":`.

- [ ] **Step 3: Run**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_eval_runner.py
```

Expected: `RAG eval runner checks passed.`.

If `run_eval_cases` doesn't currently propagate the error onto `case["error"]` (i.e. the production code is also broken), STOP and report — the spec assumes the code already implements this and just needs a test.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_rag_eval_runner.py
git commit -m "test: run_eval_cases records per-case invoker errors and continues"
```

---

## Task 5: Tighten error-row exclusion assertion (M2)

**Files:**
- Modify: `backend/tests_local/test_memory_excludes_error_rows.py`

- [ ] **Step 1: Read the current test**

```bash
cat /home/taitu/GitHub/Loan_ETL/backend/tests_local/test_memory_excludes_error_rows.py
```

Confirm the current assertion is `assert "to_summarize" in captured` (or similar) without a call-count check.

- [ ] **Step 2: Update the assertion**

Locate the `captured = {}` dict and the `fake_summarize` function. Replace with a `summarize_calls` list-based pattern:

```python
summarize_calls = []

def fake_summarize(db_arg, session_arg, messages_to_summarize, previous_summary):
    summarize_calls.append(list(messages_to_summarize))
    return "TÓM TẮT"
```

And replace the existing post-`load_memory` assertion with:

```python
assert len(summarize_calls) == 1, (
    f"expected exactly 1 summarize call, got {len(summarize_calls)}"
)
assert all(m.content != "ERR PLACEHOLDER" for m in summarize_calls[0]), (
    "error=True row leaked into summarize input"
)
```

Drop the silent `if "to_summarize" in captured:` block entirely (the new asserts replace it).

Keep the existing `recent_messages` assertion (error row not in window) — that one is fine.

- [ ] **Step 3: Run**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_memory_excludes_error_rows.py
```

Expected: `memory excludes-error-rows test passed`.

- [ ] **Step 4: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_memory_excludes_error_rows.py
git commit -m "test: assert summarize called exactly once + no error row in input"
```

---

## Task 6: Split the excluded-user-message test into its own file (M1)

**Files:**
- Modify: `backend/tests_local/test_chat_service_uses_memory.py` (remove the test function + cleanup the `__main__` block).
- Create: `backend/tests_local/test_chat_service_excludes_current_user_message.py`.

- [ ] **Step 1: Read the current `test_chat_service_uses_memory.py`**

```bash
cat /home/taitu/GitHub/Loan_ETL/backend/tests_local/test_chat_service_uses_memory.py
```

Locate the function `test_chat_service_excludes_current_user_message_from_memory_window` and all helper classes it depends on (`FakeQuery`, `FakeDB`, etc.).

- [ ] **Step 2: Create the new file**

Create `backend/tests_local/test_chat_service_excludes_current_user_message.py` and paste:
1. All necessary imports (mirror what `test_chat_service_uses_memory.py` imports).
2. Helper classes (`FakeQuery`, `FakeDB`, helper `_msg` factory) — copy, do not import (avoids tight coupling between the two test files).
3. The `test_chat_service_excludes_current_user_message_from_memory_window` function body.
4. A standalone `if __name__ == "__main__":` block:
   ```python
   if __name__ == "__main__":
       test_chat_service_excludes_current_user_message_from_memory_window()
       print("chat_service excludes-current-user-message test passed")
   ```

- [ ] **Step 3: Remove the function from `test_chat_service_uses_memory.py`**

In `backend/tests_local/test_chat_service_uses_memory.py`:
1. Delete the `test_chat_service_excludes_current_user_message_from_memory_window` function body.
2. Remove it from the `if __name__ == "__main__":` block.
3. Leave the original `test_chat_service_passes_summary_and_window_to_rag` function and its `if __name__ == "__main__":` call intact.

- [ ] **Step 4: Run both files**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_uses_memory.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_excludes_current_user_message.py
```

Expected: both print their pass messages.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/tests_local/test_chat_service_uses_memory.py backend/tests_local/test_chat_service_excludes_current_user_message.py
git commit -m "test: move excluded-current-user-message test into its own file"
```

---

## Task 7: Final sweep

- [ ] **Step 1: Run every eval / memory / chat test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_rag_eval_*.py tests_local/test_memory_*.py tests_local/test_chat_service_*.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All eval + memory + chat tests passed"
```

- [ ] **Step 2: No commit (verification only).**

---

## Acceptance criteria

- [x] `--baseline /tmp/missing.json` exits with code 2 + clean message (no traceback).
- [x] `test_rag_eval_diff.py` covers both the run-level regression threshold and the `same` status.
- [x] `test_rag_eval_runner.py` covers per-case invoker error + continue.
- [x] FAQ-07 `must_include` uses `"1 ngày|1-3 ngày"` instead of `"1"`.
- [x] `test_memory_excludes_error_rows.py` asserts exactly one summarize call and no error row in its input.
- [x] `test_chat_service_excludes_current_user_message.py` exists, runs independently, and passes.
- [x] All existing eval / memory / chat tests still pass.
