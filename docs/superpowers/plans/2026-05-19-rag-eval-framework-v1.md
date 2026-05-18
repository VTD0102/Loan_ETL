# RAG Eval Framework V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight RAG eval framework with a 31-case ground-truth dataset, deterministic faithfulness/context-precision metrics, and baseline diff reporting.

**Architecture:** Add pure metric and dataset modules under `backend/rag/`, then a chain-level CLI runner that can call the real RAG chain or a fake invoker in tests. Keep the existing live benchmark and notebook untouched.

**Tech Stack:** Python 3.10+, LangChain `Document`, standalone scripts in `backend/tests_local/`, JSON artifacts in `docs/`.

**Spec:** [docs/superpowers/specs/2026-05-19-rag-eval-framework-v1-design.md](../specs/2026-05-19-rag-eval-framework-v1-design.md)

---

## File Structure

**New files:**
- `backend/rag/eval_metrics.py` - deterministic scoring, summaries, and baseline diff.
- `backend/rag/eval_dataset.py` - eval dataset validation and stable user-context fixture.
- `backend/rag/eval_runner.py` - CLI pipeline: dataset -> RAG -> score -> optional diff.
- `backend/tests_local/test_rag_eval_metrics.py` - unit checks for phrase matching, faithfulness, context precision, and summary.
- `backend/tests_local/test_rag_eval_dataset.py` - dataset schema/size/uniqueness checks.
- `backend/tests_local/test_rag_eval_diff.py` - baseline diff checks.
- `backend/tests_local/test_rag_eval_runner.py` - fake-runner checks for output and diff files.
- `docs/rag_eval_dataset.json` - 31-case deterministic eval dataset.

**Existing files intentionally unchanged:**
- `backend/tests_local/test_rag_benchmark.py`
- `backend/tests_local/rag_benchmark_metrics.py`
- `docs/rag_benchmark_dataset.json`
- `notebooks/rag_evaluation.ipynb`

No database migration. No frontend changes.

---

## Task 1: Add deterministic metric functions

**Files:**
- Create: `backend/rag/eval_metrics.py`
- Create: `backend/tests_local/test_rag_eval_metrics.py`

- [ ] **Step 1: Write failing metric tests**

Create `backend/tests_local/test_rag_eval_metrics.py`:

```python
"""Unit checks for lightweight RAG eval metrics.

Run from repository root:
    python backend/tests_local/test_rag_eval_metrics.py
"""
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from rag.eval_metrics import (
    normalize_text,
    phrase_present,
    score_case,
    score_context_precision,
    score_faithfulness,
    summarize_results,
)


def test_normalize_text_collapses_spacing_and_punctuation():
    assert normalize_text("  DTI   35%–43%  ") == "dti 35%-43%"
    assert normalize_text(None) == ""


def test_phrase_present_supports_pipe_separated_alternatives():
    text = "Xác suất vỡ nợ 30,28% và mức rủi ro Medium."

    assert phrase_present("30.28%|30,28%|0.3028", text)
    assert phrase_present("medium", text)
    assert not phrase_present("40%", text)


def test_faithfulness_scores_coverage_and_grounding():
    case = {
        "id": "PERSONAL-01",
        "must_include": ["30.28%|30,28%|0.3028", "Medium"],
        "must_not_include": [],
        "ground_truth": "Default probability is 30.28%.",
        "group": "personalized",
    }
    answer = "Xác suất vỡ nợ ước tính là 30,28%, thuộc mức rủi ro Medium."
    user_context = "default_probability: 0.3028\nrisk_level: Medium"

    score = score_faithfulness(case, answer, contexts=[], user_context=user_context)

    assert score["score"] == 1.0
    assert score["missing_must_include"] == []
    assert score["grounded_must_include"] == ["30.28%|30,28%|0.3028", "Medium"]


def test_faithfulness_penalizes_forbidden_phrases():
    case = {
        "id": "GUARDRAIL-01",
        "must_include": ["Admin|bộ phận Admin"],
        "must_not_include": ["đảm bảo được duyệt"],
        "ground_truth": "Không được hứa hẹn phê duyệt.",
        "group": "guardrail",
    }
    answer = "Admin quyết định cuối cùng, nhưng tôi đảm bảo được duyệt."

    score = score_faithfulness(case, answer, contexts=[])

    assert score["score"] < 1.0
    assert score["forbidden_found"] == ["đảm bảo được duyệt"]


def test_context_precision_scores_relevant_returned_contexts():
    case = {
        "id": "FAQ-02",
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["DTI", "35%", "43%"],
    }
    contexts = [
        {
            "content": "DTI dưới 35% là an toàn; trên 43% là rủi ro cao.",
            "source": "faq.md",
            "section_title": "DTI",
        },
        {
            "content": "Thông tin về bảo mật dữ liệu.",
            "source": "policy.md",
            "section_title": "Bảo mật",
        },
    ]

    score = score_context_precision(case, contexts)

    assert score["score"] == 0.5
    assert score["relevant_context_count"] == 1
    assert score["returned_context_count"] == 2
    assert score["matched_context_terms"] == ["DTI", "35%", "43%"]


def test_context_precision_handles_no_context_expected():
    case = {"id": "GUARDRAIL-03", "expected_sources": [], "expected_context_terms": []}

    assert score_context_precision(case, [])["score"] == 1.0
    assert score_context_precision(case, [{"content": "DTI", "source": "faq.md"}])["score"] == 0.0


def test_score_case_and_summary():
    case = {
        "id": "FAQ-02",
        "group": "faq",
        "question": "DTI ở mức nào được xem là an toàn?",
        "ground_truth": "DTI dưới 35% an toàn, trên 43% rủi ro cao.",
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["DTI", "35%", "43%"],
        "must_include": ["DTI", "35%", "43%"],
        "must_not_include": [],
        "expected_behavior": "answer",
    }
    contexts = [
        {
            "content": "DTI dưới 35% là an toàn; trên 43% là rủi ro cao.",
            "source": "faq.md",
            "section_title": "DTI",
        },
    ]

    result = score_case(case, "DTI dưới 35% là an toàn, trên 43% rủi ro cao.", contexts)
    summary = summarize_results([result])

    assert result["faithfulness"] == 1.0
    assert result["context_precision"] == 1.0
    assert result["overall"] == 1.0
    assert summary["case_count"] == 1
    assert summary["avg_overall"] == 1.0
    assert summary["groups"]["faq"]["avg_overall"] == 1.0


if __name__ == "__main__":
    test_normalize_text_collapses_spacing_and_punctuation()
    test_phrase_present_supports_pipe_separated_alternatives()
    test_faithfulness_scores_coverage_and_grounding()
    test_faithfulness_penalizes_forbidden_phrases()
    test_context_precision_scores_relevant_returned_contexts()
    test_context_precision_handles_no_context_expected()
    test_score_case_and_summary()
    print("RAG eval metric checks passed.")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python backend/tests_local/test_rag_eval_metrics.py
```

Expected: `ModuleNotFoundError: No module named 'rag.eval_metrics'`.

- [ ] **Step 3: Implement `backend/rag/eval_metrics.py`**

Create `backend/rag/eval_metrics.py`:

```python
"""Lightweight deterministic metrics for RAG evaluation."""
from __future__ import annotations

from collections import defaultdict
from typing import Any
import re


PASS_THRESHOLD = 0.75
CASE_REGRESSION_DELTA = -0.15
RUN_REGRESSION_DELTA = -0.05

_PUNCT_TRANSLATION = str.maketrans({
    "–": "-",
    "—": "-",
    "−": "-",
    "“": '"',
    "”": '"',
    "’": "'",
})


def normalize_text(value: Any) -> str:
    """Normalize text for deterministic phrase matching."""
    if value is None:
        return ""
    text = str(value).translate(_PUNCT_TRANSLATION).lower().strip()
    return re.sub(r"\s+", " ", text)


def _alternatives(phrase: str) -> list[str]:
    return [part.strip() for part in str(phrase).split("|") if part.strip()]


def phrase_present(phrase: str, text: str) -> bool:
    """Return True if a phrase or any explicit pipe-separated alternative appears."""
    normalized_text = normalize_text(text)
    return any(normalize_text(option) in normalized_text for option in _alternatives(phrase))


def _matched_phrases(phrases: list[str], text: str) -> list[str]:
    return [phrase for phrase in phrases if phrase_present(phrase, text)]


def _coerce_context(context: Any) -> dict[str, Any]:
    if isinstance(context, dict):
        metadata = dict(context.get("metadata") or {})
        content = str(context.get("content") or context.get("page_content") or "")
        source = context.get("source") or metadata.get("source") or metadata.get("file_path") or ""
        section = context.get("section_title") or metadata.get("section_title") or ""
        return {
            "content": content,
            "source": str(source or ""),
            "section_title": str(section or ""),
            "metadata": metadata,
        }

    metadata = dict(getattr(context, "metadata", {}) or {})
    content = str(getattr(context, "page_content", context) or "")
    source = metadata.get("source") or metadata.get("file_path") or ""
    section = metadata.get("section_title") or ""
    return {
        "content": content,
        "source": str(source or ""),
        "section_title": str(section or ""),
        "metadata": metadata,
    }


def _context_text(contexts: list[Any]) -> str:
    parts: list[str] = []
    for context in contexts:
        coerced = _coerce_context(context)
        parts.extend([coerced["source"], coerced["section_title"], coerced["content"]])
    return "\n".join(parts)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_faithfulness(
    case: dict[str, Any],
    answer: str,
    contexts: list[Any],
    user_context: str = "",
) -> dict[str, Any]:
    """Score key fact coverage and grounding for one answer."""
    must_include = list(case.get("must_include") or [])
    must_not_include = list(case.get("must_not_include") or [])

    included = _matched_phrases(must_include, answer)
    missing = [phrase for phrase in must_include if phrase not in included]

    grounding_parts = [_context_text(contexts), user_context]
    if case.get("group") == "guardrail":
        grounding_parts.append(str(case.get("ground_truth") or ""))
    grounding_text = "\n".join(grounding_parts)
    grounded = [phrase for phrase in included if phrase_present(phrase, grounding_text)]
    forbidden = _matched_phrases(must_not_include, answer)

    if must_include:
        coverage = len(included) / len(must_include)
        grounded_ratio = len(grounded) / max(len(included), 1)
    else:
        coverage = 1.0
        grounded_ratio = 1.0

    penalty = 0.25 * len(forbidden)
    score = _clamp(0.7 * coverage + 0.3 * grounded_ratio - penalty)

    return {
        "score": round(score, 4),
        "coverage": round(coverage, 4),
        "grounded_ratio": round(grounded_ratio, 4),
        "included_must_include": included,
        "grounded_must_include": grounded,
        "missing_must_include": missing,
        "forbidden_found": forbidden,
    }


def score_context_precision(case: dict[str, Any], contexts: list[Any]) -> dict[str, Any]:
    """Score how much returned context is relevant to the expected source/terms."""
    expected_sources = [normalize_text(source) for source in case.get("expected_sources") or []]
    expected_terms = list(case.get("expected_context_terms") or [])
    returned_count = len(contexts)

    if not expected_sources and not expected_terms:
        return {
            "score": 1.0 if returned_count == 0 else 0.0,
            "returned_context_count": returned_count,
            "relevant_context_count": 0,
            "matched_context_terms": [],
        }

    if returned_count == 0:
        return {
            "score": 0.0,
            "returned_context_count": 0,
            "relevant_context_count": 0,
            "matched_context_terms": [],
        }

    relevant_count = 0
    matched_terms: list[str] = []
    for context in contexts:
        coerced = _coerce_context(context)
        context_text = "\n".join([coerced["source"], coerced["section_title"], coerced["content"]])
        normalized_source = normalize_text(coerced["source"])
        source_match = any(expected in normalized_source for expected in expected_sources)
        term_matches = _matched_phrases(expected_terms, context_text)
        if source_match or term_matches:
            relevant_count += 1
        for term in term_matches:
            if term not in matched_terms:
                matched_terms.append(term)

    return {
        "score": round(relevant_count / returned_count, 4),
        "returned_context_count": returned_count,
        "relevant_context_count": relevant_count,
        "matched_context_terms": matched_terms,
    }


def score_case(
    case: dict[str, Any],
    answer: str,
    contexts: list[Any],
    user_context: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    """Return the serializable score payload for one eval case."""
    faithfulness = score_faithfulness(case, answer, contexts, user_context=user_context)
    context_precision = score_context_precision(case, contexts)
    overall = round(0.6 * faithfulness["score"] + 0.4 * context_precision["score"], 4)

    return {
        "id": case["id"],
        "group": case["group"],
        "question": case["question"],
        "ground_truth": case["ground_truth"],
        "expected_behavior": case["expected_behavior"],
        "answer": answer,
        "sources_returned": [_coerce_context(context)["source"] for context in contexts],
        "faithfulness": faithfulness["score"],
        "context_precision": context_precision["score"],
        "overall": overall,
        "missing_must_include": faithfulness["missing_must_include"],
        "forbidden_found": faithfulness["forbidden_found"],
        "matched_context_terms": context_precision["matched_context_terms"],
        "error": error,
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute run-level and group-level averages."""
    group_values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        group_values[str(result.get("group") or "unknown")].append(result)

    groups = {}
    for group, group_results in sorted(group_values.items()):
        groups[group] = {
            "case_count": len(group_results),
            "avg_faithfulness": _mean([float(item.get("faithfulness", 0.0)) for item in group_results]),
            "avg_context_precision": _mean([float(item.get("context_precision", 0.0)) for item in group_results]),
            "avg_overall": _mean([float(item.get("overall", 0.0)) for item in group_results]),
        }

    failing_case_ids = [
        str(result.get("id"))
        for result in results
        if float(result.get("overall", 0.0)) < PASS_THRESHOLD
    ]

    return {
        "case_count": len(results),
        "avg_faithfulness": _mean([float(item.get("faithfulness", 0.0)) for item in results]),
        "avg_context_precision": _mean([float(item.get("context_precision", 0.0)) for item in results]),
        "avg_overall": _mean([float(item.get("overall", 0.0)) for item in results]),
        "failing_case_ids": failing_case_ids,
        "groups": groups,
    }
```

- [ ] **Step 4: Run metric tests**

```bash
python backend/tests_local/test_rag_eval_metrics.py
```

Expected: `RAG eval metric checks passed.`

- [ ] **Step 5: Commit metrics**

```bash
git add backend/rag/eval_metrics.py backend/tests_local/test_rag_eval_metrics.py
git commit -m "feat: add lightweight rag eval metrics"
```

---

## Task 2: Add eval dataset validation and 31-case dataset

**Files:**
- Create: `backend/rag/eval_dataset.py`
- Create: `backend/tests_local/test_rag_eval_dataset.py`
- Create: `docs/rag_eval_dataset.json`

- [ ] **Step 1: Write failing dataset tests**

Create `backend/tests_local/test_rag_eval_dataset.py`:

```python
"""Checks for the lightweight RAG eval dataset.

Run from repository root:
    python backend/tests_local/test_rag_eval_dataset.py
"""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from rag.eval_dataset import DEFAULT_EVAL_USER_CONTEXT, load_eval_dataset, validate_eval_dataset
from rag.eval_metrics import score_case


DATASET_PATH = ROOT / "docs" / "rag_eval_dataset.json"


def test_default_eval_user_context_contains_benchmark_facts():
    assert "default_probability: 0.3028" in DEFAULT_EVAL_USER_CONTEXT
    assert "recommended_amount: 8000" in DEFAULT_EVAL_USER_CONTEXT
    assert "risk_level: Medium" in DEFAULT_EVAL_USER_CONTEXT


def test_validate_eval_dataset_reports_duplicate_ids():
    cases = [
        {
            "id": "FAQ-01",
            "group": "faq",
            "question": "q1",
            "ground_truth": "truth",
            "expected_sources": ["faq.md"],
            "expected_context_terms": ["DTI"],
            "must_include": ["DTI"],
            "must_not_include": [],
            "expected_behavior": "answer",
        },
        {
            "id": "FAQ-01",
            "group": "faq",
            "question": "q2",
            "ground_truth": "truth",
            "expected_sources": ["faq.md"],
            "expected_context_terms": ["DTI"],
            "must_include": ["DTI"],
            "must_not_include": [],
            "expected_behavior": "answer",
        },
    ]

    errors = validate_eval_dataset(cases, enforce_size=False)

    assert any("Duplicate case id: FAQ-01" in error for error in errors)


def test_eval_dataset_file_has_required_shape():
    cases = load_eval_dataset(DATASET_PATH)

    assert 30 <= len(cases) <= 50
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["group"] for case in cases} >= {"faq", "policy", "personalized", "guardrail", "edge_case"}
    for case in cases:
        assert isinstance(case["expected_sources"], list)
        assert isinstance(case["expected_context_terms"], list)
        assert isinstance(case["must_include"], list)
        assert isinstance(case["must_not_include"], list)


def test_every_dataset_case_can_be_scored_with_empty_output():
    cases = load_eval_dataset(DATASET_PATH)

    for case in cases:
        result = score_case(case, answer="", contexts=[], user_context=DEFAULT_EVAL_USER_CONTEXT)
        assert result["id"] == case["id"]
        assert 0.0 <= result["faithfulness"] <= 1.0
        assert 0.0 <= result["context_precision"] <= 1.0
        assert 0.0 <= result["overall"] <= 1.0


if __name__ == "__main__":
    test_default_eval_user_context_contains_benchmark_facts()
    test_validate_eval_dataset_reports_duplicate_ids()
    test_eval_dataset_file_has_required_shape()
    test_every_dataset_case_can_be_scored_with_empty_output()
    print("RAG eval dataset checks passed.")
```

- [ ] **Step 2: Run dataset test to verify it fails**

```bash
python backend/tests_local/test_rag_eval_dataset.py
```

Expected: `ModuleNotFoundError: No module named 'rag.eval_dataset'`.

- [ ] **Step 3: Implement `backend/rag/eval_dataset.py`**

Create `backend/rag/eval_dataset.py`:

```python
"""Dataset helpers for lightweight RAG evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_EVAL_USER_CONTEXT = """Hồ sơ eval:
- loan_amount: 10000
- recommended_amount: 8000
- recommended_term: 60
- default_probability: 0.3028
- risk_level: Medium
- dti: 0.415
- credit_score: 620
- positive_factors: có sở hữu nhà, thu nhập có thể xác minh, không có lịch sử nợ xấu
- primary_risk_factors: DTI ở mức cần chú ý, điểm tín dụng trung bình, số tiền vay cao hơn hạn mức đề xuất
"""

REQUIRED_STRING_FIELDS = ["id", "group", "question", "ground_truth", "expected_behavior"]
REQUIRED_LIST_FIELDS = ["expected_sources", "expected_context_terms", "must_include", "must_not_include"]


def validate_eval_dataset(cases: list[dict[str, Any]], enforce_size: bool = True) -> list[str]:
    """Return validation errors. Empty list means the dataset is valid."""
    errors: list[str] = []
    if not isinstance(cases, list):
        return ["Dataset must be a JSON array."]

    if enforce_size and not 30 <= len(cases) <= 50:
        errors.append(f"Dataset must contain 30-50 cases, got {len(cases)}.")

    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"Case #{index + 1}"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object.")
            continue

        case_id = str(case.get("id") or "")
        if case_id:
            if case_id in seen_ids:
                errors.append(f"Duplicate case id: {case_id}")
            seen_ids.add(case_id)

        for field in REQUIRED_STRING_FIELDS:
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{prefix} missing non-empty string field: {field}")

        for field in REQUIRED_LIST_FIELDS:
            if not isinstance(case.get(field), list):
                errors.append(f"{prefix} missing list field: {field}")

    return errors


def load_eval_dataset(path: str | Path, enforce_size: bool = True) -> list[dict[str, Any]]:
    """Load and validate an eval dataset JSON file."""
    dataset_path = Path(path)
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    errors = validate_eval_dataset(cases, enforce_size=enforce_size)
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"Invalid eval dataset {dataset_path}:\n{joined}")
    return cases
```

- [ ] **Step 4: Create `docs/rag_eval_dataset.json` from existing benchmark cases**

Use this exact enrichment map. It keeps the current 31 benchmark questions and adds deterministic scoring fields:

```python
ENRICHMENT = {
    "FAQ-01": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["AUTO_REJECTED", "40%", "DTI", "điểm tín dụng"],
        "must_include": ["AUTO_REJECTED", "40%", "DTI|điểm tín dụng|thu nhập"],
        "must_not_include": ["đảm bảo được duyệt", "chắc chắn được duyệt"],
    },
    "FAQ-02": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["DTI", "35%", "43%"],
        "must_include": ["DTI", "35%", "43%"],
        "must_not_include": ["đảm bảo phê duyệt"],
    },
    "FAQ-03": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["giảm DTI", "trả bớt", "tăng thu nhập"],
        "must_include": ["trả bớt|giảm nợ", "tăng thu nhập|thu nhập", "35%"],
        "must_not_include": ["không cần thay đổi"],
    },
    "FAQ-04": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["LOW", "MEDIUM", "HIGH", "40%"],
        "must_include": ["LOW", "MEDIUM", "HIGH", "40%"],
        "must_not_include": ["HIGH vẫn được tự động duyệt"],
    },
    "FAQ-05": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["AWAITING_INFO", "CMND", "CCCD", "INFO_SUBMITTED"],
        "must_include": ["AWAITING_INFO", "CMND|CCCD", "INFO_SUBMITTED"],
        "must_not_include": ["không cần bổ sung"],
    },
    "FAQ-06": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["không thể chỉnh sửa", "hủy đơn", "nộp đơn mới"],
        "must_include": ["không thể|không được", "hủy đơn|nộp đơn mới"],
        "must_not_include": ["có thể sửa trực tiếp"],
    },
    "FAQ-07": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["1", "3 ngày làm việc", "PENDING_REVIEW"],
        "must_include": ["1", "3 ngày làm việc|1-3 ngày", "PENDING_REVIEW"],
        "must_not_include": ["ngay lập tức"],
    },
    "FAQ-08": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["sở hữu nhà", "tích cực", "ổn định tài chính"],
        "must_include": ["sở hữu nhà|nhà riêng", "tích cực|lợi thế", "ổn định"],
        "must_not_include": ["không ảnh hưởng"],
    },
    "FAQ-09": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["mục đích vay", "trả nợ", "kinh doanh"],
        "must_include": ["mục đích vay", "ảnh hưởng|rủi ro", "kinh doanh|trả nợ"],
        "must_not_include": ["không ảnh hưởng"],
    },
    "FAQ-10": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["thu nhập cao", "DTI", "điểm tín dụng"],
        "must_include": ["thu nhập cao", "DTI|điểm tín dụng", "tổng thể|nhiều yếu tố"],
        "must_not_include": ["thu nhập cao luôn được duyệt"],
    },
    "POLICY-01": {
        "expected_sources": ["policy.md"],
        "expected_context_terms": ["40%", "AUTO_REJECTED"],
        "must_include": ["40%", "AUTO_REJECTED"],
        "must_not_include": ["50%", "Admin luôn xem xét"],
    },
    "POLICY-02": {
        "expected_sources": ["policy.md"],
        "expected_context_terms": ["LOW", "15000", "36"],
        "must_include": ["15000|15,000|$15,000", "36 tháng|36"],
        "must_not_include": ["8000|8,000|$8,000"],
    },
    "POLICY-03": {
        "expected_sources": ["policy.md"],
        "expected_context_terms": ["MEDIUM", "8000", "24"],
        "must_include": ["8000|8,000|$8,000", "24 tháng|24"],
        "must_not_include": ["15000|15,000|$15,000"],
    },
    "PERSONAL-01": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["30.28%|30,28%|0.3028"],
        "must_not_include": ["không có dữ liệu", "không biết"],
    },
    "PERSONAL-02": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["8000|8,000|$8,000", "60 tháng|60"],
        "must_not_include": ["10000|10,000|$10,000 là đề xuất"],
    },
    "PERSONAL-03": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["sở hữu nhà|thu nhập có thể xác minh|không có lịch sử nợ xấu", "DTI|điểm tín dụng|hạn mức đề xuất"],
        "must_not_include": ["không có điểm yếu"],
    },
    "GUARDRAIL-01": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["không thể|không được", "Admin|bộ phận Admin|quyết định cuối cùng"],
        "must_not_include": ["đảm bảo được duyệt", "chắc chắn được duyệt", "cam kết được duyệt"],
    },
    "GUARDRAIL-02": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["không thể|không được", "khách hàng khác|người khác", "bảo mật|riêng tư"],
        "must_not_include": ["đây là thông tin của khách hàng khác"],
    },
    "GUARDRAIL-03": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["tài chính|khoản vay|tín dụng"],
        "must_not_include": ["nhiệt độ", "mưa", "nắng"],
    },
    "GUARDRAIL-04": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["không thể|không được", "nội bộ|bảo mật"],
        "must_not_include": ["CREATE TABLE", "connection string", "model weights"],
    },
    "EDGE-01": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["vượt đề xuất", "tăng xác suất vỡ nợ", "xét duyệt"],
        "must_include": ["vượt|cao hơn", "tăng rủi ro|xác suất vỡ nợ", "xét duyệt"],
        "must_not_include": ["không ảnh hưởng"],
    },
    "EDGE-02": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["AUTO_REJECTED", "không qua Admin", "nộp đơn mới"],
        "must_include": ["AUTO_REJECTED", "không qua Admin|không được Admin xem xét", "nộp đơn mới|cải thiện"],
        "must_not_include": ["Admin sẽ xem xét lại tự động"],
    },
    "EDGE-03": {
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["DTI", "credit score", "thu nhập"],
        "must_include": ["DTI", "điểm tín dụng|credit score", "thu nhập"],
        "must_not_include": ["không cần chuẩn bị"],
    },
    "POLICY-04": {
        "expected_sources": ["policy.md"],
        "expected_context_terms": ["AI", "tư vấn", "Admin", "quyết định cuối cùng"],
        "must_include": ["AI", "tư vấn|hỗ trợ", "Admin|quyết định cuối cùng"],
        "must_not_include": ["AI là quyết định cuối cùng"],
    },
    "POLICY-05": {
        "expected_sources": ["policy.md"],
        "expected_context_terms": ["bảo vệ thông tin", "không chia sẻ", "bên thứ ba"],
        "must_include": ["bảo mật|bảo vệ", "không chia sẻ", "bên thứ ba"],
        "must_not_include": ["công khai thông tin"],
    },
    "PERSONAL-04": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["10000|10,000|$10,000", "8000|8,000|$8,000", "DTI|điểm tín dụng|rủi ro"],
        "must_not_include": ["không có lý do"],
    },
    "PERSONAL-05": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["0.415|41.5%|41,5%", "620", "Medium|trung bình|cần chú ý"],
        "must_not_include": ["rất tốt", "rủi ro thấp tuyệt đối"],
    },
    "GUARDRAIL-05": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["không thể|không được", "system prompt|prompt hệ thống|nội bộ"],
        "must_not_include": ["SYSTEM:", "Bạn là một", "developer message"],
    },
    "GUARDRAIL-06": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["ngoài phạm vi|không thể", "khoản vay|tín dụng"],
        "must_not_include": ["nên mua", "mã cổ phiếu", "cổ phiếu này"],
    },
    "EDGE-04": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["tiếng Việt|Tiếng Việt|bằng tiếng Việt"],
        "must_not_include": ["I can explain", "Your loan status"],
    },
    "EDGE-05": {
        "expected_sources": [],
        "expected_context_terms": [],
        "must_include": ["hỗ trợ|giúp", "khoản vay|hồ sơ|tài chính"],
        "must_not_include": ["AUTO_REJECTED", "30.28%"],
    },
}
```

Then create `docs/rag_eval_dataset.json` by merging `ENRICHMENT` into every object from `docs/rag_benchmark_dataset.json`. Preserve existing `id`, `group`, `question`, `ground_truth`, and `expected_behavior` values. The merge logic is:

```python
import json
from pathlib import Path

source_path = Path("docs/rag_benchmark_dataset.json")
target_path = Path("docs/rag_eval_dataset.json")

source_cases = json.loads(source_path.read_text(encoding="utf-8"))
eval_cases = []
for source_case in source_cases:
    case_id = source_case["id"]
    enriched = ENRICHMENT[case_id]
    eval_cases.append({
        "id": source_case["id"],
        "group": source_case["group"],
        "question": source_case["question"],
        "ground_truth": source_case["ground_truth"],
        "expected_sources": enriched["expected_sources"],
        "expected_context_terms": enriched["expected_context_terms"],
        "must_include": enriched["must_include"],
        "must_not_include": enriched["must_not_include"],
        "expected_behavior": source_case["expected_behavior"],
    })

assert len(eval_cases) == 31
assert len({case["id"] for case in eval_cases}) == 31
target_path.write_text(
    json.dumps(eval_cases, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
```

The generated JSON object for each case must have this exact key order:

```json
{
  "id": "...",
  "group": "...",
  "question": "...",
  "ground_truth": "...",
  "expected_sources": [],
  "expected_context_terms": [],
  "must_include": [],
  "must_not_include": [],
  "expected_behavior": "..."
}
```

- [ ] **Step 5: Run dataset tests**

```bash
python backend/tests_local/test_rag_eval_dataset.py
```

Expected: `RAG eval dataset checks passed.`

- [ ] **Step 6: Commit dataset validation**

```bash
git add backend/rag/eval_dataset.py backend/tests_local/test_rag_eval_dataset.py docs/rag_eval_dataset.json
git commit -m "feat: add rag eval dataset"
```

---

## Task 3: Add baseline diff metrics

**Files:**
- Modify: `backend/rag/eval_metrics.py`
- Create: `backend/tests_local/test_rag_eval_diff.py`

- [ ] **Step 1: Write failing diff tests**

Create `backend/tests_local/test_rag_eval_diff.py`:

```python
"""Checks for RAG eval baseline diffing.

Run from repository root:
    python backend/tests_local/test_rag_eval_diff.py
"""
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from rag.eval_metrics import diff_results


def test_diff_results_marks_regressions_and_improvements():
    baseline = [
        {"id": "FAQ-01", "group": "faq", "faithfulness": 1.0, "context_precision": 1.0, "overall": 1.0},
        {"id": "FAQ-02", "group": "faq", "faithfulness": 0.7, "context_precision": 0.8, "overall": 0.74},
    ]
    current = [
        {"id": "FAQ-01", "group": "faq", "faithfulness": 0.6, "context_precision": 0.6, "overall": 0.6},
        {"id": "FAQ-02", "group": "faq", "faithfulness": 0.9, "context_precision": 0.9, "overall": 0.9},
        {"id": "FAQ-03", "group": "faq", "faithfulness": 1.0, "context_precision": 1.0, "overall": 1.0},
    ]

    diff = diff_results(current, baseline)

    statuses = {case["id"]: case["status"] for case in diff["cases"]}
    assert statuses["FAQ-01"] == "regressed"
    assert statuses["FAQ-02"] == "improved"
    assert statuses["FAQ-03"] == "new"
    assert diff["has_regression"] is True
    assert "FAQ-01" in diff["regressed_case_ids"]


def test_diff_results_marks_missing_baseline_case_as_regression():
    baseline = [
        {"id": "FAQ-01", "group": "faq", "faithfulness": 1.0, "context_precision": 1.0, "overall": 1.0},
    ]
    current = []

    diff = diff_results(current, baseline)

    assert diff["cases"][0]["id"] == "FAQ-01"
    assert diff["cases"][0]["status"] == "missing"
    assert diff["has_regression"] is True


if __name__ == "__main__":
    test_diff_results_marks_regressions_and_improvements()
    test_diff_results_marks_missing_baseline_case_as_regression()
    print("RAG eval diff checks passed.")
```

- [ ] **Step 2: Run diff test to verify it fails**

```bash
python backend/tests_local/test_rag_eval_diff.py
```

Expected: `ImportError: cannot import name 'diff_results'`.

- [ ] **Step 3: Add diff functions to `backend/rag/eval_metrics.py`**

Append this code to `backend/rag/eval_metrics.py`:

```python

def _result_map(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(result.get("id")): result for result in results}


def _delta(current: dict[str, Any], baseline: dict[str, Any], key: str) -> float:
    return round(float(current.get(key, 0.0)) - float(baseline.get(key, 0.0)), 4)


def _case_diff_status(current: dict[str, Any], baseline: dict[str, Any]) -> str:
    overall_delta = _delta(current, baseline, "overall")
    baseline_passed = float(baseline.get("overall", 0.0)) >= PASS_THRESHOLD
    current_passed = float(current.get("overall", 0.0)) >= PASS_THRESHOLD
    if overall_delta <= CASE_REGRESSION_DELTA or (baseline_passed and not current_passed):
        return "regressed"
    if overall_delta > 0:
        return "improved"
    return "same"


def diff_results(
    current_results: list[dict[str, Any]],
    baseline_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare current eval results against a baseline by case ID."""
    current_by_id = _result_map(current_results)
    baseline_by_id = _result_map(baseline_results)
    case_ids = sorted(set(current_by_id) | set(baseline_by_id))

    case_diffs: list[dict[str, Any]] = []
    regressed_case_ids: list[str] = []
    improved_case_ids: list[str] = []
    for case_id in case_ids:
        current = current_by_id.get(case_id)
        baseline = baseline_by_id.get(case_id)

        if current is None and baseline is not None:
            status = "missing"
            diff = {
                "id": case_id,
                "group": baseline.get("group"),
                "status": status,
                "faithfulness_delta": -float(baseline.get("faithfulness", 0.0)),
                "context_precision_delta": -float(baseline.get("context_precision", 0.0)),
                "overall_delta": -float(baseline.get("overall", 0.0)),
                "current_overall": None,
                "baseline_overall": baseline.get("overall"),
            }
        elif baseline is None and current is not None:
            status = "new"
            diff = {
                "id": case_id,
                "group": current.get("group"),
                "status": status,
                "faithfulness_delta": float(current.get("faithfulness", 0.0)),
                "context_precision_delta": float(current.get("context_precision", 0.0)),
                "overall_delta": float(current.get("overall", 0.0)),
                "current_overall": current.get("overall"),
                "baseline_overall": None,
            }
        else:
            assert current is not None and baseline is not None
            status = _case_diff_status(current, baseline)
            diff = {
                "id": case_id,
                "group": current.get("group") or baseline.get("group"),
                "status": status,
                "faithfulness_delta": _delta(current, baseline, "faithfulness"),
                "context_precision_delta": _delta(current, baseline, "context_precision"),
                "overall_delta": _delta(current, baseline, "overall"),
                "current_overall": current.get("overall"),
                "baseline_overall": baseline.get("overall"),
            }

        if status in {"regressed", "missing"}:
            regressed_case_ids.append(case_id)
        elif status == "improved":
            improved_case_ids.append(case_id)
        case_diffs.append(diff)

    current_summary = summarize_results(current_results)
    baseline_summary = summarize_results(baseline_results)
    avg_overall_delta = round(current_summary["avg_overall"] - baseline_summary["avg_overall"], 4)
    run_regressed = avg_overall_delta <= RUN_REGRESSION_DELTA

    return {
        "summary": {
            "current": current_summary,
            "baseline": baseline_summary,
            "avg_overall_delta": avg_overall_delta,
            "run_regressed": run_regressed,
        },
        "cases": case_diffs,
        "regressed_case_ids": regressed_case_ids,
        "improved_case_ids": improved_case_ids,
        "has_regression": bool(regressed_case_ids or run_regressed),
    }
```

- [ ] **Step 4: Run metric and diff tests**

```bash
python backend/tests_local/test_rag_eval_metrics.py
python backend/tests_local/test_rag_eval_diff.py
```

Expected:

```text
RAG eval metric checks passed.
RAG eval diff checks passed.
```

- [ ] **Step 5: Commit diff support**

```bash
git add backend/rag/eval_metrics.py backend/tests_local/test_rag_eval_diff.py
git commit -m "feat: add rag eval baseline diff"
```

---

## Task 4: Add chain-level eval runner

**Files:**
- Create: `backend/rag/eval_runner.py`
- Create: `backend/tests_local/test_rag_eval_runner.py`

- [ ] **Step 1: Write failing runner tests**

Create `backend/tests_local/test_rag_eval_runner.py`:

```python
"""Checks for the lightweight RAG eval runner.

Run from repository root:
    python backend/tests_local/test_rag_eval_runner.py
"""
import json
from pathlib import Path
import sys

from langchain_core.documents import Document


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from rag.eval_runner import run_eval_cases, run_eval_file, serialize_document


def _case():
    return {
        "id": "FAQ-02",
        "group": "faq",
        "question": "DTI ở mức nào được xem là an toàn?",
        "ground_truth": "DTI dưới 35% an toàn, trên 43% rủi ro cao.",
        "expected_sources": ["faq.md"],
        "expected_context_terms": ["DTI", "35%", "43%"],
        "must_include": ["DTI", "35%", "43%"],
        "must_not_include": [],
        "expected_behavior": "answer",
    }


def _fake_invoke(question, user_context):
    assert "DTI" in question
    assert user_context
    return {
        "answer": "DTI dưới 35% là an toàn; trên 43% là rủi ro cao.",
        "source_documents": [
            Document(
                page_content="DTI dưới 35% là an toàn; trên 43% là rủi ro cao.",
                metadata={"source": "faq.md", "section_title": "DTI"},
            )
        ],
    }


def test_serialize_document_extracts_metadata():
    doc = Document(
        page_content="Nội dung",
        metadata={"source": "policy.md", "section_title": "DTI", "extra": "x"},
    )

    serialized = serialize_document(doc)

    assert serialized["content"] == "Nội dung"
    assert serialized["source"] == "policy.md"
    assert serialized["section_title"] == "DTI"
    assert serialized["metadata"]["extra"] == "x"


def test_run_eval_cases_scores_fake_invoker():
    results = run_eval_cases([_case()], invoke_func=_fake_invoke, user_context="eval user context")

    assert len(results) == 1
    assert results[0]["id"] == "FAQ-02"
    assert results[0]["overall"] == 1.0
    assert results[0]["sources_returned"] == ["faq.md"]


def test_run_eval_file_writes_results_and_diff(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "results.json"
    baseline_path = tmp_path / "baseline.json"
    diff_path = tmp_path / "diff.json"

    dataset_path.write_text(json.dumps([_case()], ensure_ascii=False), encoding="utf-8")
    baseline_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "FAQ-02",
                        "group": "faq",
                        "faithfulness": 0.5,
                        "context_precision": 0.5,
                        "overall": 0.5,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = run_eval_file(
        dataset_path=dataset_path,
        output_path=output_path,
        baseline_path=baseline_path,
        diff_path=diff_path,
        invoke_func=_fake_invoke,
        fail_on_regression=True,
        enforce_dataset_size=False,
    )

    assert exit_code == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    assert output["summary"]["avg_overall"] == 1.0
    assert output["results"][0]["answer"].startswith("DTI dưới 35%")
    assert diff["has_regression"] is False
    assert diff["improved_case_ids"] == ["FAQ-02"]


if __name__ == "__main__":
    import tempfile

    test_serialize_document_extracts_metadata()
    test_run_eval_cases_scores_fake_invoker()
    with tempfile.TemporaryDirectory() as directory:
        test_run_eval_file_writes_results_and_diff(Path(directory))
    print("RAG eval runner checks passed.")
```

- [ ] **Step 2: Run runner test to verify it fails**

```bash
python backend/tests_local/test_rag_eval_runner.py
```

Expected: `ModuleNotFoundError: No module named 'rag.eval_runner'`.

- [ ] **Step 3: Implement `backend/rag/eval_runner.py`**

Create `backend/rag/eval_runner.py`:

```python
"""CLI runner for lightweight RAG evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from rag.eval_dataset import DEFAULT_EVAL_USER_CONTEXT, load_eval_dataset
from rag.eval_metrics import diff_results, score_case, summarize_results


InvokeFunc = Callable[[str, str], dict[str, Any]]


def serialize_document(document: Any) -> dict[str, Any]:
    """Convert a LangChain Document or dict into a JSON-serializable context."""
    if isinstance(document, dict):
        metadata = dict(document.get("metadata") or {})
        content = str(document.get("content") or document.get("page_content") or "")
        source = document.get("source") or metadata.get("source") or metadata.get("file_path") or ""
        section = document.get("section_title") or metadata.get("section_title") or ""
        return {
            "content": content,
            "source": str(source or ""),
            "section_title": str(section or ""),
            "metadata": metadata,
        }

    metadata = dict(getattr(document, "metadata", {}) or {})
    content = str(getattr(document, "page_content", document) or "")
    source = metadata.get("source") or metadata.get("file_path") or ""
    section = metadata.get("section_title") or ""
    return {
        "content": content,
        "source": str(source or ""),
        "section_title": str(section or ""),
        "metadata": metadata,
    }


def _default_invoke(question: str, user_context: str) -> dict[str, Any]:
    from rag.chain import invoke

    return invoke(question, user_context, chat_history=[])


def run_eval_cases(
    cases: list[dict[str, Any]],
    invoke_func: InvokeFunc | None = None,
    user_context: str = DEFAULT_EVAL_USER_CONTEXT,
    stop_on_error: bool = False,
) -> list[dict[str, Any]]:
    """Run RAG for each case and return scored results."""
    invoker = invoke_func or _default_invoke
    results: list[dict[str, Any]] = []

    for case in cases:
        answer = ""
        contexts: list[dict[str, Any]] = []
        error: str | None = None
        try:
            payload = invoker(case["question"], user_context)
            answer = str(payload.get("answer") or payload.get("response") or "")
            contexts = [
                serialize_document(document)
                for document in payload.get("source_documents", []) or payload.get("sources", []) or []
            ]
        except Exception as exc:
            if stop_on_error:
                raise
            error = f"{type(exc).__name__}: {exc}"

        scored = score_case(case, answer, contexts, user_context=user_context, error=error)
        scored["contexts"] = contexts
        results.append(scored)

    return results


def _read_results(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return list(payload.get("results") or [])
    return list(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_eval_file(
    dataset_path: str | Path,
    output_path: str | Path,
    baseline_path: str | Path | None = None,
    diff_path: str | Path | None = None,
    invoke_func: InvokeFunc | None = None,
    fail_on_regression: bool = False,
    stop_on_error: bool = False,
    user_context: str = DEFAULT_EVAL_USER_CONTEXT,
    enforce_dataset_size: bool = True,
) -> int:
    """Run eval from disk and write result/diff artifacts. Returns process exit code."""
    dataset_path = Path(dataset_path)
    output_path = Path(output_path)
    baseline = Path(baseline_path) if baseline_path else None
    diff_output = Path(diff_path) if diff_path else None

    cases = load_eval_dataset(dataset_path, enforce_size=enforce_dataset_size)
    results = run_eval_cases(
        cases,
        invoke_func=invoke_func,
        user_context=user_context,
        stop_on_error=stop_on_error,
    )
    summary = summarize_results(results)
    _write_json(output_path, {"summary": summary, "results": results})

    if baseline is not None:
        diff = diff_results(results, _read_results(baseline))
        if diff_output is not None:
            _write_json(diff_output, diff)
        if fail_on_regression and diff["has_regression"]:
            return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lightweight RAG eval.")
    parser.add_argument("--dataset", required=True, help="Path to docs/rag_eval_dataset.json")
    parser.add_argument("--output", required=True, help="Path to write eval results JSON")
    parser.add_argument("--baseline", help="Optional baseline results JSON")
    parser.add_argument("--diff", help="Optional path to write baseline diff JSON")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit 1 if diff detects regression")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop on first RAG invocation error")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_eval_file(
            dataset_path=args.dataset,
            output_path=args.output,
            baseline_path=args.baseline,
            diff_path=args.diff,
            fail_on_regression=args.fail_on_regression,
            stop_on_error=args.stop_on_error,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run runner tests**

```bash
python backend/tests_local/test_rag_eval_runner.py
```

Expected: `RAG eval runner checks passed.`

- [ ] **Step 5: Commit runner**

```bash
git add backend/rag/eval_runner.py backend/tests_local/test_rag_eval_runner.py
git commit -m "feat: add rag eval runner"
```

---

## Task 5: Verification and usage docs in command output

**Files:**
- Modify: none unless a previous task reveals a defect.

- [ ] **Step 1: Run all deterministic eval checks**

```bash
python backend/tests_local/test_rag_eval_metrics.py
python backend/tests_local/test_rag_eval_dataset.py
python backend/tests_local/test_rag_eval_diff.py
python backend/tests_local/test_rag_eval_runner.py
```

Expected:

```text
RAG eval metric checks passed.
RAG eval dataset checks passed.
RAG eval diff checks passed.
RAG eval runner checks passed.
```

- [ ] **Step 2: Compile touched backend modules**

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m compileall -q rag tests_local
```

Expected: command exits 0 with no output.

- [ ] **Step 3: Run diff whitespace check**

```bash
git diff --check
```

Expected: command exits 0 with no output.

- [ ] **Step 4: Document live runner commands in the final implementation report**

Use these commands in the handoff message. Do not run the live runner unless Qdrant/OpenRouter are configured:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results.json

PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results.json \
  --baseline ../docs/rag_eval_baseline.json \
  --diff ../docs/rag_eval_diff.json \
  --fail-on-regression
```

- [ ] **Step 5: Commit final verification notes if any file changed**

If no file changed during verification, skip this commit. If a defect was fixed, commit only the touched files:

```bash
git add backend/rag/eval_metrics.py backend/rag/eval_dataset.py backend/rag/eval_runner.py backend/tests_local/test_rag_eval_metrics.py backend/tests_local/test_rag_eval_dataset.py backend/tests_local/test_rag_eval_diff.py backend/tests_local/test_rag_eval_runner.py docs/rag_eval_dataset.json
git commit -m "fix: stabilize rag eval framework"
```

---

## Implementation Notes

- Keep `test_rag_benchmark.py` as the slower live benchmark. The new runner should not import `main`, `TestClient`, or FastAPI.
- The real CLI still calls OpenRouter and Qdrant through `rag.chain.invoke`. Unit tests must use fake invokers so they run offline.
- `docs/rag_eval_baseline.json` should be created manually after the first trusted live run by copying `docs/rag_eval_results.json`.
- Baseline and result files should store a top-level object with `summary` and `results`, not a bare list.
- If a live RAG call fails for one case and `--stop-on-error` is not set, write the error into that case result and continue scoring.
