"""Lightweight deterministic metrics for RAG evaluation."""
from __future__ import annotations

from collections import defaultdict
from typing import Any
import re


PASS_THRESHOLD = 0.75
CASE_REGRESSION_DELTA = -0.15
RUN_REGRESSION_DELTA = -0.05

_PUNCT_TRANSLATION = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "−": "-",
        "“": '"',
        "”": '"',
        "’": "'",
    }
)


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
            "avg_context_precision": _mean(
                [float(item.get("context_precision", 0.0)) for item in group_results]
            ),
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
