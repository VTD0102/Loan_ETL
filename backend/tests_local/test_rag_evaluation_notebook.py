"""
Smoke checks for the RAG evaluation notebook.

Run from repository root:
    python backend/tests_local/test_rag_evaluation_notebook.py
"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = ROOT / "RAG_eval" / "rag_evaluation.ipynb"


def test_notebook_exists_and_is_valid_json():
    assert NOTEBOOK_PATH.exists(), f"Missing notebook: {NOTEBOOK_PATH}"

    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["language"] == "python"
    assert len(notebook["cells"]) == 9


def test_notebook_uses_existing_benchmark_artifacts():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )

    assert "RAG_eval/rag_benchmark_dataset.json" in source
    assert "RAG_eval/rag_benchmark_results.json" in source
    assert "RUN_BENCHMARK" in source
    assert "tests_local/test_rag_benchmark.py" in source
    assert "source_ok" in source
    assert "faithfulness" in source
    assert "guardrail_pass" in source
    assert "overall_score" in source


if __name__ == "__main__":
    test_notebook_exists_and_is_valid_json()
    test_notebook_uses_existing_benchmark_artifacts()
    print("RAG evaluation notebook smoke checks passed.")
