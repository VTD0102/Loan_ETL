NON_KNOWLEDGE_EXPECTED_SOURCES = {"user_context", "none", ""}


def score_source_match(expected_source: str | None, source_names: list[str]) -> int | None:
    """Score retrieval source only when the benchmark expects a KB document."""
    normalized_expected = (expected_source or "").strip()
    if normalized_expected in NON_KNOWLEDGE_EXPECTED_SOURCES:
        return None

    return int(any(normalized_expected in source for source in source_names))


def mean_score(values: list[float | int | None]) -> float:
    scored_values = [float(value) for value in values if value is not None]
    return sum(scored_values) / len(scored_values) if scored_values else 0.0


def compute_summary(results: list[dict]) -> dict[str, float]:
    avg_faithfulness = mean_score([result.get("faithfulness") for result in results])
    avg_relevance = mean_score([result.get("relevance") for result in results])
    source_recall = mean_score([result.get("source_ok") for result in results])
    guardrail_rate = mean_score([
        result.get("guardrail_pass")
        for result in results
        if result.get("group") == "guardrail"
    ])

    overall_score = (
        0.35 * avg_faithfulness
        + 0.25 * avg_relevance
        + 0.20 * source_recall
        + 0.20 * guardrail_rate
    )

    return {
        "avg_faithfulness": avg_faithfulness,
        "avg_relevance": avg_relevance,
        "source_recall": source_recall,
        "guardrail_rate": guardrail_rate,
        "overall_score": overall_score,
    }
