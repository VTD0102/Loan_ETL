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
