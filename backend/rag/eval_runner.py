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
        try:
            baseline_results = _read_results(baseline)
        except FileNotFoundError as exc:
            raise ValueError(f"Baseline file not found: {baseline}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read baseline file {baseline}: {exc}") from exc
        diff = diff_results(results, baseline_results)
        if diff_output is not None:
            _write_json(diff_output, diff)
        if fail_on_regression and diff["has_regression"]:
            return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lightweight RAG eval.")
    parser.add_argument("--dataset", required=True, help="Path to RAG_eval/rag_eval_dataset.json")
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
