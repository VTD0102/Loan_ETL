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
