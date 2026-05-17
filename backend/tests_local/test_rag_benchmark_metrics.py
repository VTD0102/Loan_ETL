"""
Unit checks for RAG benchmark metric helpers.

Run from repository root:
    python backend/tests_local/test_rag_benchmark_metrics.py
"""
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from tests_local.rag_benchmark_metrics import compute_summary, score_source_match


def test_score_source_match_only_scores_knowledge_base_sources():
    assert score_source_match("faq.md", ["faq.md", "policy.md"]) == 1
    assert score_source_match("policy.md", ["faq.md"]) == 0
    assert score_source_match("user_context", ["faq.md", "policy.md"]) is None
    assert score_source_match("none", ["faq.md"]) is None
    assert score_source_match("", []) is None


def test_compute_summary_excludes_non_knowledge_sources_from_source_recall():
    results = [
        {"faithfulness": 1.0, "relevance": 1.0, "source_ok": 1, "group": "faq", "guardrail_pass": None},
        {"faithfulness": 1.0, "relevance": 1.0, "source_ok": 1, "group": "policy", "guardrail_pass": None},
        {"faithfulness": 1.0, "relevance": 1.0, "source_ok": None, "group": "personalized", "guardrail_pass": None},
        {"faithfulness": 1.0, "relevance": 1.0, "source_ok": None, "group": "guardrail", "guardrail_pass": 1},
    ]

    summary = compute_summary(results)

    assert summary["avg_faithfulness"] == 1.0
    assert summary["avg_relevance"] == 1.0
    assert summary["source_recall"] == 1.0
    assert summary["guardrail_rate"] == 1.0
    assert summary["overall_score"] == 1.0


if __name__ == "__main__":
    test_score_source_match_only_scores_knowledge_base_sources()
    test_compute_summary_excludes_non_knowledge_sources_from_source_recall()
    print("RAG benchmark metric helper checks passed.")
