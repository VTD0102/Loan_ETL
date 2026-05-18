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


def test_run_eval_cases_records_invoker_error_and_continues():
    """When the invoker raises for one case, the run continues and the error is recorded."""
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

    def flaky_invoke(question, user_context):
        attempted.append(question)
        if question == "q2":
            raise RuntimeError("upstream blip")
        return {"answer": "stub", "source_documents": []}

    results = run_eval_cases(cases, invoke_func=flaky_invoke)

    assert attempted == ["q1", "q2", "q3"], "all 3 cases must be attempted, even after failure"
    by_id = {result["id"]: result for result in results}
    assert "error" in by_id["BAD-2"] and "upstream blip" in by_id["BAD-2"]["error"]
    assert by_id["OK-3"].get("error") is None
    assert by_id["OK-1"].get("error") is None


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


def test_run_eval_file_missing_baseline_raises_value_error(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "results.json"
    diff_path = tmp_path / "diff.json"
    baseline_path = tmp_path / "does_not_exist.json"

    dataset_path.write_text(json.dumps([_case()], ensure_ascii=False), encoding="utf-8")

    raised = None
    try:
        run_eval_file(
            dataset_path=dataset_path,
            output_path=output_path,
            baseline_path=baseline_path,
            diff_path=diff_path,
            invoke_func=_fake_invoke,
            enforce_dataset_size=False,
        )
    except ValueError as exc:
        raised = exc

    assert raised is not None, "expected ValueError when baseline missing"
    assert "Baseline" in str(raised) or "baseline" in str(raised)
    assert str(baseline_path) in str(raised)


if __name__ == "__main__":
    import tempfile

    test_serialize_document_extracts_metadata()
    test_run_eval_cases_scores_fake_invoker()
    test_run_eval_cases_records_invoker_error_and_continues()
    with tempfile.TemporaryDirectory() as directory:
        test_run_eval_file_writes_results_and_diff(Path(directory))
    with tempfile.TemporaryDirectory() as directory:
        test_run_eval_file_missing_baseline_raises_value_error(Path(directory))
    print("RAG eval runner checks passed.")
