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
