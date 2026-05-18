# RAG Eval + Memory V1.1 Polish — Fixes design

**Date**: 2026-05-19
**Status**: Approved (post-audit of Eval V1 + Memory V1.1)
**Scope**:
- `backend/rag/eval_runner.py`
- `backend/tests_local/test_rag_eval_diff.py`
- `backend/tests_local/test_rag_eval_runner.py`
- `docs/rag_eval_dataset.json`
- `backend/rag/memory.py`
- `backend/tests_local/test_chat_service_uses_memory.py`
- `backend/tests_local/test_chat_service_excludes_current_user_message.py` (new)
- `backend/tests_local/test_memory_excludes_error_rows.py`

This spec is **independent of the KB chunking v1.1 fixes** (different files, no shared symbols) — Codex can run it in parallel.

## Why

Audits of Memory V1.1 (commit `dacd983`) and Eval Framework V1 (commits `4faa410`..`4e378f7`) surfaced 6 issues. All tests pass today, but each issue is a real gap that will surface as soon as the framework is used for real diffs or the redundant filter is removed.

---

## Fix E1 — `--baseline` missing-file UX (Eval, Important)

`backend/rag/eval_runner.py` line 122 calls `_read_results(baseline)` which raises a plain `FileNotFoundError` and propagates as an unhandled exception. `main()` (line 154) only catches `ValueError`, so the user sees a Python traceback + exit code 1. Since `docs/rag_eval_baseline.json` is intentionally not yet committed, this is the very first thing anyone running `--baseline` will hit.

### Approach

Wrap the read in a try/except that turns the IO failure into a `ValueError` with a clean Vietnamese-friendly message. `main()` already converts `ValueError` to exit code 2 + stderr message.

```python
try:
    baseline_results = _read_results(baseline)
except FileNotFoundError as exc:
    raise ValueError(f"Baseline file not found: {baseline}") from exc
except (OSError, json.JSONDecodeError) as exc:
    raise ValueError(f"Cannot read baseline file {baseline}: {exc}") from exc
diff = diff_results(results, baseline_results)
```

### Acceptance

- Running with `--baseline /tmp/does_not_exist.json` exits with code 2 and prints a clean message — no traceback.
- A test in `test_rag_eval_runner.py` invokes the public function with a bogus baseline path and asserts `ValueError` is raised with a recognisable message.

---

## Fix E2 — Run-level regression threshold untested (Eval, Important)

`eval_metrics.diff_results` sets `summary["run_regressed"] = True` and `has_regression = True` when `avg_overall_delta <= -0.05`, even if no individual case crosses its per-case threshold. **No test exercises this path.** A future change to that constant or to the aggregation logic would slip through silently.

### Approach

Add a test in `backend/tests_local/test_rag_eval_diff.py`:

```python
def test_diff_results_run_level_regression_triggers_has_regression():
    """Average drop > 0.05 flags regression even when no case regresses individually."""
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
    assert statuses["FAQ-01"] == "same"
    assert statuses["FAQ-02"] == "same"
    assert diff["regressed_case_ids"] == []
    assert diff["summary"]["run_regressed"] is True
    assert diff["has_regression"] is True
```

Also add a sanity counterpart that verifies the `same` status path:

```python
def test_diff_results_marks_unchanged_case_as_same():
    baseline = [{"id": "FAQ-01", "group": "faq", "faithfulness": 0.8, "context_precision": 0.8, "overall": 0.8}]
    current = [{"id": "FAQ-01", "group": "faq", "faithfulness": 0.8, "context_precision": 0.8, "overall": 0.8}]
    diff = diff_results(current, baseline)
    assert diff["cases"][0]["status"] == "same"
    assert diff["cases"][0]["overall_delta"] == 0.0
    assert diff["has_regression"] is False
```

Wire both into the `if __name__ == "__main__":` block. Threshold values (`-0.05`, `-0.15`) come from the actual constants in `eval_metrics.py` — verify them before writing the test if they were changed.

### Acceptance

- Both new tests pass.
- Removing the run-level threshold from `diff_results` makes the first new test fail.

---

## Fix E3 — Error-continue path untested (Eval, Important)

`eval_runner.run_eval_cases` catches per-case exceptions and writes `case["error"]` while continuing the loop (unless `stop_on_error=True`). No test verifies this. A regression that re-raises (or stops the loop) would not be caught.

### Approach

Add a test in `backend/tests_local/test_rag_eval_runner.py`:

```python
def test_run_eval_cases_records_invoker_error_and_continues():
    cases = [
        {"id": "OK-1", "group": "g", "question": "q1", "ground_truth": "gt1",
         "expected_behavior": "...", "must_include": [], "must_not_include": [],
         "expected_context_terms": [], "expected_sources": []},
        {"id": "BAD-2", "group": "g", "question": "q2", "ground_truth": "gt2",
         "expected_behavior": "...", "must_include": [], "must_not_include": [],
         "expected_context_terms": [], "expected_sources": []},
        {"id": "OK-3", "group": "g", "question": "q3", "ground_truth": "gt3",
         "expected_behavior": "...", "must_include": [], "must_not_include": [],
         "expected_context_terms": [], "expected_sources": []},
    ]
    seen = []

    def flaky_invoke(question, context):
        seen.append(question)
        if question == "q2":
            raise RuntimeError("upstream blip")
        return {"answer": "stub", "source_documents": []}

    results = run_eval_cases(cases, invoke_func=flaky_invoke)

    assert seen == ["q1", "q2", "q3"], "all 3 cases must be attempted, even after failure"
    bad = next(r for r in results if r["id"] == "BAD-2")
    assert "error" in bad and "upstream blip" in bad["error"]
    ok = next(r for r in results if r["id"] == "OK-3")
    assert "error" not in ok
```

If `stop_on_error=True` is also supported as a flag, add a companion test that verifies the loop stops at the first failure.

### Acceptance

- New test passes.
- Setting `stop_on_error=True` in the runner makes a follow-up test stop after the first failing case.

---

## Fix E4 — FAQ-07 `must_include` "1" matches anything (Eval, Minor)

`docs/rag_eval_dataset.json` FAQ-07 has `"must_include": ["1", "3 ngày làm việc|1-3 ngày", "PENDING_REVIEW"]`. After text normalisation `"1"` matches any answer that contains the digit 1 — including unrelated tokens like `"10 triệu"` or `"1 lần"`.

### Approach

Replace the first entry with `"1 ngày|1-3 ngày"`. The pipe (`|`) form is the alternative-matching syntax the metric already supports (`_alternatives()` in `eval_metrics.py`).

```diff
"must_include": [
-  "1",
+  "1 ngày|1-3 ngày",
   "3 ngày làm việc|1-3 ngày",
   "PENDING_REVIEW"
],
```

### Acceptance

- `test_rag_eval_dataset.py` still passes (it doesn't inspect this field).
- Manual: changing the FAQ-07 answer to omit "1 ngày" wording → faithfulness score drops by the expected amount.

---

## Fix M1 — Move excluded-user-message test into the file the spec named (Memory V1.1, Important)

The Memory V1.1 spec mandated a standalone file `backend/tests_local/test_chat_service_excludes_current_user_message.py`. The implementation instead extended `test_chat_service_uses_memory.py` with a function `test_chat_service_excludes_current_user_message_from_memory_window`. The test itself is fine; the file name is wrong.

### Approach

1. Create `backend/tests_local/test_chat_service_excludes_current_user_message.py`.
2. Move (cut/paste) the `test_chat_service_excludes_current_user_message_from_memory_window` function (and any helper classes / fixtures it needs — `FakeQuery`, `FakeDB`, etc.) from `test_chat_service_uses_memory.py` into the new file.
3. Remove the call to that test function from the old file's `if __name__ == "__main__":` block.
4. Add a standalone `if __name__ == "__main__":` block to the new file that runs the test.
5. Confirm both files run independently and pass.

### Acceptance

- `backend/tests_local/test_chat_service_excludes_current_user_message.py` exists and runs the test on its own.
- `test_chat_service_uses_memory.py` still runs and still has its `test_chat_service_passes_summary_and_window_to_rag` test.
- Both print their respective pass messages.

---

## Fix M2 — Tighten error-row exclusion assertion (Memory V1.1, Minor)

`backend/tests_local/test_memory_excludes_error_rows.py` asserts `"to_summarize" in captured` but does not check the call count. A bug that summarises twice would still pass.

### Approach

Replace
```python
assert "to_summarize" in captured
```
with a call-count tracker plus the existing membership assertion:
```python
summarize_calls = []

def fake_summarize(db_arg, session_arg, messages_to_summarize, previous_summary):
    summarize_calls.append(list(messages_to_summarize))
    # existing body...

# after load_memory(...)
assert len(summarize_calls) == 1, f"expected exactly 1 summarize call, got {len(summarize_calls)}"
assert all(m.content != "ERR PLACEHOLDER" for m in summarize_calls[0])
```

### Acceptance

- Test still passes.
- Adding a second `_summarize` invocation inside `load_memory` (artificial bug) makes the test fail with the message above.

---

## Order of work

The 6 fixes are independent (different files for the most part). Suggested order to keep diffs small:

1. **E4** (one-line dataset edit, fastest).
2. **E1** (small wrapper in `eval_runner.py`).
3. **E2** (additive tests in `test_rag_eval_diff.py`).
4. **E3** (additive test in `test_rag_eval_runner.py`).
5. **M2** (assertion tightening in `test_memory_excludes_error_rows.py`).
6. **M1** (file split — touches two test files).

Each fix is its own commit. After all six, run:
```bash
cd backend
for f in tests_local/test_rag_eval_*.py tests_local/test_memory_*.py tests_local/test_chat_service_*.py; do
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
```
Expected: all pass.

## Acceptance criteria (whole spec)

- All 6 fixes implemented per their sections.
- All new and existing eval/memory/chat tests pass.
- `--baseline /tmp/does_not_exist.json` exits cleanly (code 2, no traceback).
- New test `test_chat_service_excludes_current_user_message.py` exists and runs.

## Out of scope

- Removing the redundant in-memory `id != exclude_message_id` filter from `memory.py` — the audit flagged this as defensive but harmless; keeping it removes a class of test-FakeQuery brittleness. If we later add a real Postgres integration test, revisit.
- Reducing `scored["contexts"]` bloat in `rag_eval_results.json` — the audit flagged this as outside the spec; keeping it because it is useful for debugging.
- Re-architecting the eval framework or chunking module.
- Anything in `backend/rag/chunking.py` — that's in the KB chunking v1.1 fix spec, which runs in parallel.
