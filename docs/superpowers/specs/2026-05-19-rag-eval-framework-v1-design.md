# RAG Eval Framework V1 — Design

**Date**: 2026-05-19
**Status**: Draft (pending user review)
**Scope**: `backend/rag/eval_*.py`, `backend/tests_local/`, `docs/rag_eval_dataset.json`, `docs/rag_eval_results.json`, `docs/rag_eval_baseline.json`, `docs/rag_eval_diff.json`

## Mục tiêu

Tạo một eval framework nhẹ để đo RAG trước khi tune retrieval:

1. **Dataset ground truth 30-50 câu hỏi**: dùng V1 dataset 31 câu, kế thừa coverage hiện có từ `docs/rag_benchmark_dataset.json`, nhưng thêm field chấm điểm deterministic.
2. **Metric đơn giản**:
   - `faithfulness`: câu trả lời có bao phủ fact bắt buộc và có grounding trong retrieved context/user context không.
   - `context_precision`: retrieved context trả về có đúng nguồn/đúng nội dung kỳ vọng không.
3. **Pipeline baseline diff**:
   - dataset -> run RAG -> score -> so sánh với baseline.
   - output JSON ổn định để review regression trước khi đổi chunking/retrieval/reranking.

V1 ưu tiên deterministic, chạy được bằng script local, dễ test bằng fake RAG runner. Không thay thế benchmark LLM-as-judge hiện có, chỉ thêm một lớp eval nhanh để dùng trong vòng lặp tune retrieval.

## Phạm vi không bao gồm

- Không dùng RAGAS, DeepEval, LangSmith, hoặc LLM-as-judge trong V1.
- Không tự động tune retrieval, chunk size, reranker, prompt, model.
- Không gọi FastAPI login/DB seed trong runner mặc định.
- Không xóa `docs/rag_benchmark_dataset.json` hoặc `backend/tests_local/test_rag_benchmark.py`.
- Không yêu cầu notebook mới trong V1; notebook hiện tại có thể được cập nhật sau nếu cần.

---

## Context hiện tại

Hiện repo có:

- `docs/rag_benchmark_dataset.json`: 31 case gồm `faq`, `policy`, `personalized`, `guardrail`, `edge_case`.
- `backend/tests_local/test_rag_benchmark.py`: benchmark live qua FastAPI `/chat`, seed DB, gọi LLM evaluator, sleep 2 giây mỗi case, ghi `docs/rag_benchmark_results.json`.
- `backend/tests_local/rag_benchmark_metrics.py`: metric rất nhỏ cho source match và summary.

Vấn đề nếu dùng benchmark hiện tại để tune retrieval:

- Chậm và phụ thuộc môi trường: cần DB, user `rag_test@creditintel.vn`, OpenRouter, Qdrant, LLM judge.
- Metric `faithfulness` hiện do LLM judge chấm, khó repeat chính xác giữa các lần chạy.
- Không có baseline diff theo từng case, nên khó thấy retrieval change làm case nào regress.
- Dataset thiếu field `must_include`, `must_not_include`, `expected_context_terms`, nên khó chấm bằng pure functions.

---

## Chọn hướng thiết kế

### Option A — Mở rộng benchmark live hiện có

Thêm baseline diff trực tiếp vào `test_rag_benchmark.py`.

Ưu điểm: ít file mới, tận dụng script sẵn có. Nhược điểm: vẫn chậm, vẫn cần DB + LLM judge, không phù hợp vòng lặp tune retrieval. Một lỗi retrieval nhỏ sẽ bị nhiễu bởi LLM judge.

### Option B — Lightweight eval module riêng (khuyến nghị)

Thêm module eval độc lập:

- `rag.eval_metrics`: pure Python metrics, không gọi network.
- `rag.eval_runner`: CLI chạy chain-level RAG và ghi results/diff.
- `docs/rag_eval_dataset.json`: 31 câu hỏi đã enrich field để score.

Ưu điểm: deterministic, dễ test, không đụng benchmark cũ, đủ nhanh để chạy trước/sau mỗi retrieval change. Nhược điểm: metric đơn giản, chỉ đo được fact/phrase coverage và retrieval precision gần đúng.

### Option C — RAGAS/DeepEval

Dùng framework eval ngoài.

Ưu điểm: metric phong phú hơn. Nhược điểm: thêm dependency, cần LLM/embeddings judge, cấu hình phức tạp hơn mức cần thiết trước khi tune retrieval.

**Quyết định V1**: Option B.

---

## Dataset V1

File mới: `docs/rag_eval_dataset.json`.

V1 chứa 31 cases, nằm trong yêu cầu 30-50 câu. Nguồn ban đầu là `docs/rag_benchmark_dataset.json`, nhưng mỗi case thêm field để chấm điểm deterministic.

Schema mỗi case:

```json
{
  "id": "FAQ-02",
  "group": "faq",
  "question": "DTI ở mức nào được xem là an toàn?",
  "ground_truth": "DTI dưới 35% được xem là an toàn...",
  "expected_sources": ["faq.md"],
  "expected_context_terms": ["DTI", "35%", "43%"],
  "must_include": ["DTI", "35%", "43%"],
  "must_not_include": ["được đảm bảo phê duyệt"],
  "expected_behavior": "answer"
}
```

Field semantics:

- `expected_sources`: source names expected in retrieved `Document.metadata["source"]`. Empty for guardrail/off-topic cases that should not retrieve KB.
- `expected_context_terms`: terms expected inside retrieved context. Used when source metadata is missing or when parent retrieval returns broader source.
- `must_include`: facts/phrases expected in the final answer. These are not full exact-match sentences; they are stable key facts.
- `must_not_include`: hallucination/safety phrases that should fail or penalize a case if present.
- `expected_behavior`: carries existing categories such as `answer`, `cite_personal_data`, `refuse_internal`, `answer_in_vietnamese`.

`must_include`, `must_not_include`, and `expected_context_terms` support explicit alternatives with `|`.
Example: `"30.28%|30,28%|0.3028"` passes if any one alternative appears.

Dataset validation rules:

- `id`, `group`, `question`, `ground_truth`, `expected_behavior` are required non-empty strings.
- `expected_sources`, `expected_context_terms`, `must_include`, `must_not_include` are required arrays.
- Case IDs must be unique.
- Dataset size must be between 30 and 50.
- Knowledge cases (`faq`, `policy`, `edge_case` with KB answer) should have at least one `expected_sources` item.
- Personalized and guardrail cases may have `expected_sources` empty; personalized cases rely on `user_context` grounding.

---

## Metrics

### Normalization

All phrase matching uses a shared normalizer:

- lowercase;
- trim whitespace;
- collapse repeated whitespace;
- normalize common Unicode punctuation (`–`, `—`) to `-`;
- keep Vietnamese diacritics because dataset and answers are Vietnamese.

No stemming, embeddings, or fuzzy NLP in V1.

### `faithfulness`

V1 uses keypoint grounding, not open-ended claim extraction.

For each case:

1. Count `must_include` phrases present in the answer.
2. Count included phrases that are also supported by the combined grounding text:
   - retrieved document contents;
   - source names/section titles;
   - fixed eval user context for personalized cases;
   - ground truth only for guardrail/refusal cases where no retrieval is expected.
3. Apply hallucination penalty for any `must_not_include` phrase present in the answer.

Formula:

```text
coverage = included_must_include / total_must_include
grounded = supported_included / max(included_must_include, 1)
penalty = 0.25 * count(must_not_include phrases found in answer)
faithfulness = clamp(0.7 * coverage + 0.3 * grounded - penalty, 0, 1)
```

If `must_include` is empty, `coverage` and `grounded` default to 1.0 before penalties. This supports simple refusal cases where `must_not_include` is more important than exact wording.

### `context_precision`

For each returned context document:

- relevant if its source matches any `expected_sources`;
- relevant if its content/header contains any `expected_context_terms`;
- not relevant otherwise.

Formula:

```text
context_precision = relevant_context_count / returned_context_count
```

Special cases:

- If `expected_sources` and `expected_context_terms` are both empty and no docs are returned, precision is 1.0.
- If no context is expected but docs are returned, precision is 0.0.
- If context is expected but no docs are returned, precision is 0.0.

This is intentionally precision, not recall. It answers: "Trong context LLM được đưa đọc, bao nhiêu phần là đúng/hữu ích?"

### Summary score

Per-case result:

```json
{
  "id": "FAQ-02",
  "group": "faq",
  "answer": "...",
  "sources_returned": ["faq.md"],
  "faithfulness": 1.0,
  "context_precision": 1.0,
  "overall": 1.0,
  "missing_must_include": [],
  "forbidden_found": [],
  "matched_context_terms": ["DTI", "35%", "43%"]
}
```

Case overall:

```text
overall = 0.6 * faithfulness + 0.4 * context_precision
```

Run summary:

- `avg_faithfulness`
- `avg_context_precision`
- `avg_overall`
- group averages by `group`
- failing case IDs where `overall < 0.75`

---

## Pipeline

CLI module: `backend/rag/eval_runner.py`.

Default command:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results.json
```

Diff command:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results.json \
  --baseline ../docs/rag_eval_baseline.json \
  --diff ../docs/rag_eval_diff.json \
  --fail-on-regression
```

Runner flow:

```text
load dataset
  -> validate schema and size
  -> for each case:
       build fixed eval user context
       call rag.chain.invoke(question, user_context, chat_history=[])
       serialize answer and source documents
       score case with rag.eval_metrics
  -> write results JSON
  -> if baseline provided:
       compute per-case diff and aggregate diff
       write diff JSON
       optionally exit 1 on regression
```

The runner is chain-level, not API-level. It avoids auth/DB setup and focuses on RAG behavior.

### Fixed eval user context

Personalized cases need stable user context without hitting DB. V1 runner includes a deterministic text fixture matching current benchmark seed:

```text
Hồ sơ eval:
- loan_amount: 10000
- recommended_amount: 8000
- recommended_term: 60
- default_probability: 0.3028
- risk_level: Medium
- dti: 0.415
- credit_score: 620
- positive_factors: có sở hữu nhà, thu nhập có thể xác minh, không có lịch sử nợ xấu
- primary_risk_factors: DTI ở mức cần chú ý, điểm tín dụng trung bình, số tiền vay cao hơn hạn mức đề xuất
```

This makes personalized scoring independent from SQLAlchemy state.

---

## Baseline diff

Baseline file: `docs/rag_eval_baseline.json`.

Diff file: `docs/rag_eval_diff.json`.

Diff compares current results to baseline by case ID:

- `faithfulness_delta`
- `context_precision_delta`
- `overall_delta`
- `status`: `same`, `improved`, `regressed`, `new`, `missing`

Regression rules:

- Per-case `overall_delta <= -0.15` => `regressed`.
- Any case going from `overall >= 0.75` to `< 0.75` => `regressed`.
- Run-level `avg_overall_delta <= -0.05` => run regression.

`--fail-on-regression` exits with code 1 if any regression rule fires. Without this flag, the diff is informational and exits 0.

---

## Error handling

- Invalid dataset schema: print validation errors and exit 2.
- Duplicate case ID: print duplicate IDs and exit 2.
- RAG invocation exception for one case: record `error`, use empty answer/context, score 0 for that case, continue unless `--stop-on-error`.
- Baseline missing case: status `new`.
- Current result missing baseline case: status `missing`.
- Output path parent directory missing: create it.

---

## Testing strategy

Standalone scripts under `backend/tests_local/`:

1. `test_rag_eval_metrics.py`
   - phrase normalization;
   - faithfulness coverage/grounding;
   - forbidden phrase penalty;
   - context precision expected/no-context cases;
   - summary averages.
2. `test_rag_eval_dataset.py`
   - `docs/rag_eval_dataset.json` exists;
   - size is 30-50;
   - required fields are present;
   - IDs are unique;
   - every case can be scored against empty fake output without exceptions.
3. `test_rag_eval_diff.py`
   - per-case improved/regressed/same/new/missing;
   - run-level regression threshold;
   - `has_regression` flag.
4. `test_rag_eval_runner.py`
   - runner can execute a tiny temp dataset with a fake invoke function;
   - writes results JSON;
   - writes diff JSON against temp baseline;
   - does not import FastAPI or call `/chat`.

Manual/live command after implementation:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.eval_runner \
  --dataset ../docs/rag_eval_dataset.json \
  --output ../docs/rag_eval_results.json
```

This command still needs configured Qdrant/OpenRouter because it calls the real RAG chain. Unit tests avoid those dependencies with fake invokers.

---

## Acceptance criteria

- `docs/rag_eval_dataset.json` has 31 valid ground-truth cases.
- Pure metric tests pass without network, DB, Qdrant, or OpenRouter.
- Runner tests pass with fake invoke function and temp files.
- Live runner can produce `docs/rag_eval_results.json` when RAG dependencies are available.
- Diff mode writes `docs/rag_eval_diff.json` and can fail CI/local command on regressions.
- Existing `test_rag_benchmark.py` remains unchanged and still available for slower LLM-as-judge benchmark.
