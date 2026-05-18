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
