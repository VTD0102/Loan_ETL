# RAG Knowledge Base & Chunking V1 — Design

**Date**: 2026-05-18
**Status**: Draft (pending user review)
**Scope**: `backend/rag/chunking.py`, `backend/rag/ingest.py`, `backend/rag/retriever.py`, `backend/rag/chain.py`, `backend/tests_local/`

## Mục tiêu

Nâng chất lượng retrieval của knowledge base theo "trục 2":

1. **Semantic chunking thay fixed-size chunking**: không cắt tài liệu theo 800 ký tự mù nữa; ưu tiên ranh giới Markdown heading, FAQ question/answer, paragraph và list/table block.
2. **Parent-document retrieval**: Qdrant search trên child chunks nhỏ, nhưng LLM đọc parent section lớn hơn để có ngữ cảnh đầy đủ.
3. **Metadata enrichment**: mỗi child/parent có `source`, `source_path`, `source_type`, `document_title`, `section_title`, `parent_id`, `chunk_index`.

V1 tập trung vào KB Markdown hiện có (`backend/rag/knowledge/*.md` và nếu tồn tại thì `docs/data_dictionary/**/*.md`). Không đổi model, vector store, prompt policy hay benchmark dataset.

## Phạm vi không bao gồm

- Không thêm semantic splitter embedding-based từ `langchain-experimental` trong V1. Dependency này chưa có trong `backend/requirements.txt` và sẽ làm ingest/test kém deterministic.
- Không thêm hybrid retrieval / reranker / BM25.
- Không tạo collection/table riêng cho parent docs.
- Không ingest PDF/DOCX.
- Không chạy live benchmark tự động trong implementation plan; benchmark có thể chạy thủ công sau khi Qdrant + OpenRouter sẵn sàng.

---

## Context hiện tại

`backend/rag/ingest.py` hiện dùng:

```python
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
return splitter.split_documents(docs)
```

Vấn đề:

- Heading và Q/A có thể bị cắt đôi.
- Chunk được đưa thẳng cho LLM nên có thể thiếu phần tiêu đề/định nghĩa cha.
- Metadata chỉ còn `source` basename; không có section title/source type để debug và format citation.
- `retriever.py` trả thẳng child chunks từ `QdrantVectorStore.as_retriever(...)`.

---

## Chọn hướng thiết kế

### Option A — Structure-aware semantic chunking (khuyến nghị)

Tạo module nội bộ `backend/rag/chunking.py`:

- Parse Markdown theo heading (`#`, `##`, `###`) và FAQ question markers (`**Q:`).
- Parent document = một section logic (ví dụ `## 4. Vai Trò...` hoặc một Q/A block).
- Child chunks = đoạn nhỏ trong parent, cắt theo paragraph/list/table boundary, chỉ fallback character split khi một block quá dài.
- Child metadata lưu `parent_content`; retriever expand child hit thành parent `Document`.

Ưu điểm: deterministic, không thêm dependency, dễ test bằng standalone scripts, phù hợp KB Markdown nhỏ hiện tại. Nhược điểm: không phải embedding-based semantic breakpoint.

### Option B — LangChain `SemanticChunker`

Thêm `langchain-experimental`, dùng embedding distances để đặt breakpoints.

Ưu điểm: semantic đúng nghĩa theo embedding. Nhược điểm: thêm dependency, có thể gọi embeddings trong chunking nếu không mock kỹ, tests dễ flaky, ingest chậm hơn và cần tune threshold.

### Option C — LLM-assisted chunking

Dùng LLM phân đoạn tài liệu.

Ưu điểm: chunk semantic tốt nhất nếu prompt tốt. Nhược điểm: tốn chi phí, nondeterministic, không phù hợp local ingest script.

**Quyết định V1**: Option A. Khi KB lớn hơn và có nhu cầu đo benchmark, V2 có thể thay implementation sau cùng interface.

---

## Architecture

### `backend/rag/chunking.py`

Module mới, dependency-free ngoài `langchain_core.documents.Document`.

Public API:

```python
def enrich_document_metadata(doc: Document) -> Document:
    """Normalize source metadata and infer source_type/document_title."""


def split_documents_semantically(docs: list[Document]) -> list[Document]:
    """Return child chunks for vector search, each carrying parent metadata/content."""


def expand_child_documents_to_parents(
    child_docs: list[Document],
    max_parent_docs: int | None = None,
) -> list[Document]:
    """Deduplicate child hits by parent_id and return parent Documents for the LLM."""
```

Private helpers:

- `_infer_source_type(source_name, source_path)`:
  - `faq.md` -> `faq`
  - `policy.md` -> `policy`
  - path containing `data_dictionary` -> `data_dictionary`
  - else `knowledge_base`
- `_extract_document_title(markdown, fallback)` -> first `# ...` heading or fallback source filename.
- `_split_markdown_into_parent_sections(markdown, base_metadata)` -> semantic parent sections.
- `_split_parent_into_child_texts(parent_content)` -> paragraph/list/table-aware child chunks.
- `_stable_parent_id(source, section_title, parent_index, parent_content)` -> sha1 hex prefix.

### Parent-child storage strategy

V1 stores only child chunks in Qdrant.

Each child chunk metadata includes:

```python
{
    "retrieval_unit": "child",
    "parent_id": "...",
    "parent_index": 3,
    "chunk_index": 0,
    "source": "policy.md",
    "source_path": "/abs/path/backend/rag/knowledge/policy.md",
    "source_type": "policy",
    "document_title": "Chính Sách Xét Duyệt Cho Vay — CreditIntel",
    "section_title": "4.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)",
    "parent_content": "...full section text...",
}
```

Retriever expands hits:

1. Qdrant searches child chunks (`page_content` small).
2. Wrapper deduplicates by `parent_id` preserving rank order.
3. Wrapper returns parent `Document(page_content=parent_content, metadata=...)`.
4. `chain._format_documents()` renders parent content and enriched source heading for the LLM.

Trade-off: `parent_content` is duplicated in Qdrant payload. Acceptable for V1 because KB is small and avoids a second collection/store. If KB grows, V2 can store parents in a local docstore keyed by `parent_id`.

### `backend/rag/ingest.py`

Changes:

- Import `split_documents_semantically`.
- `load_documents()` keeps source path long enough for metadata enrichment.
- `split_documents(docs)` becomes a thin wrapper:

```python
def split_documents(docs):
    return split_documents_semantically(docs)
```

CLI behavior remains:

- `--dry-run` does not call embeddings/Qdrant.
- `--recreate` remains destructive.
- Dry run prints chunk source + section title + source type for visibility.

### `backend/rag/retriever.py`

Changes:

- Child search uses larger k: `TOP_K * 3` to compensate for parent dedupe.
- Wrap Qdrant retriever:

```python
_retriever = ParentDocumentRetriever(
    child_retriever=vectorstore.as_retriever(search_kwargs={"k": TOP_K * 3}),
    max_parent_docs=TOP_K,
)
```

`ParentDocumentRetriever` supports both `.invoke(query)` and `.get_relevant_documents(query)` so existing `chain._retrieve_documents()` keeps working.

### `backend/rag/chain.py`

Small formatting upgrade only:

- `_format_documents()` includes `section_title` when present:

```text
[1] policy.md — 4.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)
...
```

This improves citations/debugging without changing prompt variables.

---

## Data flow

Ingest:

```text
Markdown files
  -> load_documents()
  -> enrich_document_metadata()
  -> parent sections
  -> child chunks with parent_content metadata
  -> Qdrant child embeddings
```

Chat:

```text
user question
  -> Qdrant child search
  -> child docs ranked by similarity
  -> expand_child_documents_to_parents()
  -> de-duped parent docs
  -> chain._format_documents()
  -> LLM prompt
```

---

## Error handling

- Malformed/empty markdown file: return zero chunks for that file, no exception.
- Document with no heading: use source filename as `document_title` and `section_title`.
- Parent section longer than max parent size: split into multiple parent sections with suffix metadata (`section_part_index`).
- Child metadata missing `parent_content`: parent expansion falls back to child `page_content`, preserving current behavior.
- Duplicate child hits for one parent: return only the first parent, preserving the best rank.

---

## Testing strategy

Standalone scripts under `backend/tests_local/`:

1. `test_rag_chunking_semantic.py`
   - heading sections do not get mixed;
   - FAQ Q/A block stays together;
   - child chunks contain enriched metadata;
   - long parent sections split into multiple children but keep the same parent id.
2. `test_rag_parent_retriever.py`
   - duplicate child hits collapse into one parent;
   - rank order is preserved;
   - missing parent metadata gracefully returns child content.
3. `test_rag_ingest_semantic_chunks.py`
   - `ingest.split_documents()` calls semantic splitter and returns child chunks with parent metadata.
4. Update `test_rag_ingest_cli.py`
   - existing dry-run/upsert/recreate behavior remains.
5. Update `test_rag_timeout_config.py`
   - retriever still propagates embedding/Qdrant timeouts after wrapper.
6. Add/extend `_format_documents` test if needed so section title formatting is locked down.

---

## Acceptance criteria

- `backend/rag/ingest.py` no longer uses fixed-size `RecursiveCharacterTextSplitter`.
- Child chunks are small search units and include `parent_id`, `chunk_index`, `section_title`, `source_type`, and `parent_content`.
- `backend/rag/retriever.py` returns parent documents to the chain, not raw child snippets.
- Duplicate child hits for the same parent produce one parent document.
- `chain._format_documents()` displays `source` plus `section_title` when available.
- Dry-run ingest still avoids embedding/Qdrant calls.
- Existing deterministic RAG tests still pass.

---

## Migration / rollout

Implementation changes the payload schema in the existing Qdrant collection. Run:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --dry-run
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --recreate
```

`--recreate` is required after deployment so old fixed-size chunks do not mix with new parent-child payloads.

---

## Spec self-review

- Placeholder scan: no placeholder markers.
- Scope: one subsystem, focused on KB ingestion/retrieval/formatting.
- Ambiguity: "semantic chunking" is explicitly defined as Markdown/FAQ structure-aware for V1, not embedding-distance chunking.
- Risk: parent content duplication in Qdrant payload is accepted for small KB; V2 can move parents to a docstore.
