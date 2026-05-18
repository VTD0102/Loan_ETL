# RAG Knowledge Base & Chunking V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed-size KB chunking with Markdown/FAQ-aware semantic chunks, parent-document retrieval, and richer metadata.

**Architecture:** Add `rag.chunking` as the focused unit for metadata enrichment, parent sectioning, child chunking, and child-to-parent expansion. `rag.ingest` will produce child chunks for Qdrant; `rag.retriever` will search children but return de-duplicated parent documents to `rag.chain`. Existing Qdrant/OpenRouter stack stays unchanged.

**Tech Stack:** Python 3.14 local venv, LangChain `Document`, `langchain-openai`, `langchain-qdrant`, Qdrant client, standalone scripts in `backend/tests_local/`.

**Spec:** [docs/superpowers/specs/2026-05-18-rag-kb-chunking-v1-design.md](../specs/2026-05-18-rag-kb-chunking-v1-design.md)

---

## File Structure

**New files:**
- `backend/rag/chunking.py` - semantic Markdown/FAQ chunking, metadata enrichment, parent expansion.
- `backend/tests_local/test_rag_chunking_semantic.py` - unit checks for metadata and semantic chunks.
- `backend/tests_local/test_rag_parent_retriever.py` - unit checks for child-to-parent expansion and retriever wrapper behavior.
- `backend/tests_local/test_rag_ingest_semantic_chunks.py` - ingest integration with semantic splitter.
- `backend/tests_local/test_rag_chain_format_documents.py` - source + section-title formatting.

**Modified files:**
- `backend/rag/ingest.py` - replace `RecursiveCharacterTextSplitter` with `split_documents_semantically`; improve dry-run output.
- `backend/rag/retriever.py` - wrap Qdrant child retriever with parent expansion.
- `backend/rag/chain.py` - format enriched metadata in retrieved document headers.
- `backend/tests_local/test_rag_ingest_cli.py` - keep CLI behavior tests compatible with enriched metadata.
- `backend/tests_local/test_rag_timeout_config.py` - assert retriever wrapper still propagates timeout kwargs.

No database migration. No frontend changes.

---

## Task 1: Add semantic chunking module

**Files:**
- Create: `backend/rag/chunking.py`
- Create: `backend/tests_local/test_rag_chunking_semantic.py`

- [ ] **Step 1: Write the failing semantic chunking test**

Create `backend/tests_local/test_rag_chunking_semantic.py`:

```python
"""Semantic chunking checks for Markdown/FAQ knowledge base docs."""
from langchain_core.documents import Document

from rag.chunking import (
    enrich_document_metadata,
    expand_child_documents_to_parents,
    split_documents_semantically,
)


def test_enrich_document_metadata_infers_source_fields():
    doc = Document(
        page_content="# Chính sách\nNội dung",
        metadata={"source": "/repo/backend/rag/knowledge/policy.md"},
    )

    enriched = enrich_document_metadata(doc)

    assert enriched.metadata["source"] == "policy.md"
    assert enriched.metadata["source_path"].endswith("backend/rag/knowledge/policy.md")
    assert enriched.metadata["source_type"] == "policy"
    assert enriched.metadata["document_title"] == "Chính sách"


def test_heading_sections_become_parent_child_chunks():
    doc = Document(
        page_content=(
            "# Chính sách\n\n"
            "Intro chung.\n\n"
            "## DTI\n\n"
            "DTI dưới 35% là an toàn.\n\n"
            "DTI trên 43% là rủi ro cao.\n\n"
            "## Credit Score\n\n"
            "Điểm tín dụng càng cao thì rủi ro càng thấp."
        ),
        metadata={"source": "/repo/backend/rag/knowledge/policy.md"},
    )

    chunks = split_documents_semantically([doc])

    section_titles = {chunk.metadata["section_title"] for chunk in chunks}
    assert "DTI" in section_titles
    assert "Credit Score" in section_titles
    assert all(chunk.metadata["retrieval_unit"] == "child" for chunk in chunks)
    assert all(chunk.metadata.get("parent_content") for chunk in chunks)
    assert all(chunk.metadata.get("parent_id") for chunk in chunks)
    assert all(chunk.metadata.get("source_type") == "policy" for chunk in chunks)


def test_faq_question_answer_block_stays_together():
    doc = Document(
        page_content=(
            "# FAQ\n\n"
            "**Q: DTI là gì?**\n"
            "A: DTI là tỷ lệ nợ trên thu nhập.\n\n"
            "---\n\n"
            "**Q: Tôi có thể nộp lại không?**\n"
            "A: Có, sau khi cải thiện hồ sơ."
        ),
        metadata={"source": "/repo/backend/rag/knowledge/faq.md"},
    )

    chunks = split_documents_semantically([doc])

    assert any("DTI là gì" in chunk.metadata["section_title"] for chunk in chunks)
    assert any("nộp lại" in chunk.metadata["section_title"] for chunk in chunks)
    dti_chunks = [chunk for chunk in chunks if "DTI là gì" in chunk.metadata["section_title"]]
    assert dti_chunks
    assert "DTI là tỷ lệ nợ trên thu nhập" in dti_chunks[0].metadata["parent_content"]


def test_expand_child_documents_to_parents_deduplicates_by_parent_id():
    child_a = Document(
        page_content="child A",
        metadata={
            "parent_id": "p1",
            "parent_content": "full parent one",
            "source": "policy.md",
            "section_title": "DTI",
        },
    )
    child_b = Document(
        page_content="child B",
        metadata={
            "parent_id": "p1",
            "parent_content": "full parent one duplicate",
            "source": "policy.md",
            "section_title": "DTI",
        },
    )
    child_c = Document(
        page_content="child C",
        metadata={
            "parent_id": "p2",
            "parent_content": "full parent two",
            "source": "faq.md",
            "section_title": "FAQ",
        },
    )

    parents = expand_child_documents_to_parents([child_a, child_b, child_c])

    assert [doc.metadata["parent_id"] for doc in parents] == ["p1", "p2"]
    assert parents[0].page_content == "full parent one"
    assert parents[0].metadata["retrieval_unit"] == "parent"


if __name__ == "__main__":
    test_enrich_document_metadata_infers_source_fields()
    test_heading_sections_become_parent_child_chunks()
    test_faq_question_answer_block_stays_together()
    test_expand_child_documents_to_parents_deduplicates_by_parent_id()
    print("semantic chunking tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: `ModuleNotFoundError: No module named 'rag.chunking'`.

- [ ] **Step 3: Implement `backend/rag/chunking.py`**

Create `backend/rag/chunking.py`:

```python
"""Semantic chunking helpers for the RAG knowledge base.

V1 is Markdown/FAQ structure-aware and deterministic. It does not call an LLM
or embeddings during chunking.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document

PARENT_MAX_CHARS = 3500
CHILD_MAX_CHARS = 700
CHILD_OVERLAP_CHARS = 80

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_FAQ_RE = re.compile(r"^\*\*Q:\s*(.+?)\*\*\s*$", re.MULTILINE)


def enrich_document_metadata(doc: Document) -> Document:
    """Normalize source metadata and infer document-level fields."""
    metadata = dict(doc.metadata or {})
    original_source = str(metadata.get("source") or metadata.get("file_path") or "unknown")
    source_name = Path(original_source).name or original_source

    metadata["source"] = source_name
    metadata["source_path"] = original_source
    metadata["source_type"] = _infer_source_type(source_name, original_source)
    metadata["document_title"] = _extract_document_title(doc.page_content, source_name)
    return Document(page_content=doc.page_content, metadata=metadata)


def split_documents_semantically(docs: list[Document]) -> list[Document]:
    """Return child chunks for vector search, carrying parent content in metadata."""
    chunks: list[Document] = []
    for doc in docs:
        enriched = enrich_document_metadata(doc)
        parent_sections = _split_markdown_into_parent_sections(enriched.page_content, enriched.metadata)
        for parent_index, parent in enumerate(parent_sections):
            parent_content = parent["content"].strip()
            if not parent_content:
                continue
            for section_part_index, parent_part in enumerate(_split_long_parent(parent_content)):
                parent_id = _stable_parent_id(
                    enriched.metadata["source"],
                    parent["section_title"],
                    parent_index,
                    section_part_index,
                    parent_part,
                )
                parent_metadata = {
                    **enriched.metadata,
                    "retrieval_unit": "parent",
                    "parent_id": parent_id,
                    "parent_index": parent_index,
                    "section_part_index": section_part_index,
                    "section_title": parent["section_title"],
                }
                child_texts = _split_parent_into_child_texts(parent_part)
                for chunk_index, child_text in enumerate(child_texts):
                    child_metadata = {
                        **parent_metadata,
                        "retrieval_unit": "child",
                        "chunk_index": chunk_index,
                        "parent_content": parent_part,
                    }
                    chunks.append(Document(page_content=child_text, metadata=child_metadata))
    return chunks


def expand_child_documents_to_parents(
    child_docs: list[Document],
    max_parent_docs: int | None = None,
) -> list[Document]:
    """Deduplicate child hits by parent_id and return parent Documents."""
    parents: list[Document] = []
    seen: set[str] = set()
    for child in child_docs:
        metadata = dict(child.metadata or {})
        parent_id = str(metadata.get("parent_id") or f"child:{len(parents)}")
        if parent_id in seen:
            continue
        seen.add(parent_id)
        parent_content = metadata.get("parent_content") or child.page_content
        metadata.pop("parent_content", None)
        metadata["retrieval_unit"] = "parent"
        parents.append(Document(page_content=parent_content, metadata=metadata))
        if max_parent_docs is not None and len(parents) >= max_parent_docs:
            break
    return parents


def _infer_source_type(source_name: str, source_path: str) -> str:
    lowered = f"{source_path}/{source_name}".lower()
    if source_name.lower() == "faq.md":
        return "faq"
    if source_name.lower() == "policy.md":
        return "policy"
    if "data_dictionary" in lowered:
        return "data_dictionary"
    return "knowledge_base"


def _extract_document_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _split_markdown_into_parent_sections(markdown: str, base_metadata: dict) -> list[dict[str, str]]:
    if base_metadata.get("source_type") == "faq":
        faq_sections = _split_faq_sections(markdown, base_metadata)
        if faq_sections:
            return faq_sections

    matches = list(_HEADING_RE.finditer(markdown))
    if not matches:
        return [{
            "section_title": base_metadata.get("document_title") or base_metadata.get("source") or "Document",
            "content": markdown,
        }]

    sections: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        title = match.group(2).strip()
        content = markdown[start:end].strip()
        if content:
            sections.append({"section_title": title, "content": content})
    return sections


def _split_faq_sections(markdown: str, base_metadata: dict) -> list[dict[str, str]]:
    matches = list(_FAQ_RE.finditer(markdown))
    if not matches:
        return []

    sections: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        question = match.group(1).strip()
        content = markdown[start:end].strip().strip("-").strip()
        if content:
            sections.append({"section_title": question, "content": content})
    return sections


def _split_long_parent(parent_content: str) -> list[str]:
    if len(parent_content) <= PARENT_MAX_CHARS:
        return [parent_content]
    return _pack_blocks(_iter_markdown_blocks(parent_content), PARENT_MAX_CHARS, overlap_chars=0)


def _split_parent_into_child_texts(parent_content: str) -> list[str]:
    return _pack_blocks(_iter_markdown_blocks(parent_content), CHILD_MAX_CHARS, CHILD_OVERLAP_CHARS)


def _iter_markdown_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if blocks:
        return blocks
    return [text.strip()] if text.strip() else []


def _pack_blocks(blocks: Iterable[str], max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for block in blocks:
        if len(block) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            chunks.extend(_split_oversized_block(block, max_chars, overlap_chars))
            continue

        proposed_len = current_len + len(block) + (2 if current else 0)
        if current and proposed_len > max_chars:
            chunks.append("\n\n".join(current))
            current = _overlap_tail(chunks[-1], overlap_chars)
            current_len = sum(len(item) for item in current) + (2 * max(0, len(current) - 1))

        current.append(block)
        current_len += len(block) + (2 if len(current) > 1 else 0)

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _split_oversized_block(block: str, max_chars: int, overlap_chars: int) -> list[str]:
    chunks = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(block):
        chunks.append(block[start:start + max_chars].strip())
        start += step
    return [chunk for chunk in chunks if chunk]


def _overlap_tail(text: str, overlap_chars: int) -> list[str]:
    if overlap_chars <= 0:
        return []
    tail = text[-overlap_chars:].strip()
    return [tail] if tail else []


def _stable_parent_id(
    source: str,
    section_title: str,
    parent_index: int,
    section_part_index: int,
    parent_content: str,
) -> str:
    raw = f"{source}|{section_title}|{parent_index}|{section_part_index}|{parent_content[:200]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: `semantic chunking tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/rag/chunking.py backend/tests_local/test_rag_chunking_semantic.py
git commit -m "feat: add semantic markdown chunking for rag knowledge base"
```

---

## Task 2: Wire semantic chunking into ingest

**Files:**
- Modify: `backend/rag/ingest.py`
- Create: `backend/tests_local/test_rag_ingest_semantic_chunks.py`
- Modify: `backend/tests_local/test_rag_ingest_cli.py`

- [ ] **Step 1: Write the failing ingest integration test**

Create `backend/tests_local/test_rag_ingest_semantic_chunks.py`:

```python
"""Verify rag.ingest uses semantic chunking metadata."""
from langchain_core.documents import Document

import rag.ingest as ingest


def test_split_documents_returns_semantic_child_chunks():
    docs = [
        Document(
            page_content="# Policy\n\n## DTI\n\nDTI dưới 35% là an toàn.",
            metadata={"source": "/repo/backend/rag/knowledge/policy.md"},
        )
    ]

    chunks = ingest.split_documents(docs)

    assert chunks
    assert chunks[0].metadata["retrieval_unit"] == "child"
    assert chunks[0].metadata["source"] == "policy.md"
    assert chunks[0].metadata["source_type"] == "policy"
    assert chunks[0].metadata["section_title"] == "Policy" or chunks[0].metadata["section_title"] == "DTI"
    assert chunks[0].metadata["parent_content"]


if __name__ == "__main__":
    test_split_documents_returns_semantic_child_chunks()
    print("rag ingest semantic chunk tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_semantic_chunks.py
```

Expected: `KeyError: 'retrieval_unit'` or similar because current `split_documents()` uses fixed-size splitter.

- [ ] **Step 3: Update `backend/rag/ingest.py` imports and split function**

Change imports:

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

to:

```python
from rag.chunking import split_documents_semantically
```

Replace `split_documents`:

```python
def split_documents(docs):
    return split_documents_semantically(docs)
```

- [ ] **Step 4: Preserve source path in `load_documents()`**

In `load_documents()`, replace:

```python
for doc in loaded:
    doc.metadata["source"] = Path(doc.metadata["source"]).name
docs.extend(loaded)
```

with:

```python
docs.extend(loaded)
```

`enrich_document_metadata()` now normalizes `source` and keeps `source_path`.

- [ ] **Step 5: Improve dry-run metadata output**

In `main()`, replace the dry-run chunk print block:

```python
for i, chunk in enumerate(chunks[:2]):
    source = chunk.metadata.get("source", "?")
    print(f"--- Chunk {i + 1} ({source}) ---")
    print(chunk.page_content[:200])
```

with:

```python
for i, chunk in enumerate(chunks[:2]):
    source = chunk.metadata.get("source", "?")
    section = chunk.metadata.get("section_title", "?")
    source_type = chunk.metadata.get("source_type", "?")
    parent_id = chunk.metadata.get("parent_id", "?")
    print(f"--- Chunk {i + 1} ({source} | {source_type} | {section} | parent={parent_id}) ---")
    print(chunk.page_content[:200])
```

- [ ] **Step 6: Update ingest CLI test fake chunks**

In `backend/tests_local/test_rag_ingest_cli.py`, change `_fake_load_documents()` to return a LangChain `Document` with semantic metadata-compatible source:

```python
from langchain_core.documents import Document


def _fake_load_documents():
    return [Document(page_content="# Fake\n\nhello", metadata={"source": "/tmp/fake.md"})]
```

Keep `_fake_split_documents(docs)` returning `docs`; CLI tests only verify dry-run/upsert/recreate control flow.

- [ ] **Step 7: Run ingest tests**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_semantic_chunks.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_cli.py
```

Expected:

```text
rag ingest semantic chunk tests passed
rag ingest CLI tests passed
```

- [ ] **Step 8: Commit**

```bash
git add backend/rag/ingest.py backend/tests_local/test_rag_ingest_semantic_chunks.py backend/tests_local/test_rag_ingest_cli.py
git commit -m "feat: use semantic chunks in rag ingest"
```

---

## Task 3: Add parent-document retrieval wrapper

**Files:**
- Modify: `backend/rag/retriever.py`
- Create: `backend/tests_local/test_rag_parent_retriever.py`
- Modify: `backend/tests_local/test_rag_timeout_config.py`

- [ ] **Step 1: Write the failing parent retriever test**

Create `backend/tests_local/test_rag_parent_retriever.py`:

```python
"""Parent-document retrieval wrapper checks."""
from langchain_core.documents import Document

from rag.retriever import ParentDocumentRetriever


class FakeChildRetriever:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return self.docs


def test_parent_retriever_expands_and_deduplicates_child_hits():
    child_docs = [
        Document(page_content="child 1", metadata={"parent_id": "p1", "parent_content": "parent 1", "source": "policy.md"}),
        Document(page_content="child 2", metadata={"parent_id": "p1", "parent_content": "parent 1 dup", "source": "policy.md"}),
        Document(page_content="child 3", metadata={"parent_id": "p2", "parent_content": "parent 2", "source": "faq.md"}),
    ]
    fake = FakeChildRetriever(child_docs)
    retriever = ParentDocumentRetriever(fake, max_parent_docs=2)

    parents = retriever.invoke("DTI")

    assert fake.queries == ["DTI"]
    assert [doc.metadata["parent_id"] for doc in parents] == ["p1", "p2"]
    assert [doc.page_content for doc in parents] == ["parent 1", "parent 2"]


def test_parent_retriever_supports_legacy_get_relevant_documents():
    fake = FakeChildRetriever([
        Document(page_content="child only", metadata={"source": "faq.md"}),
    ])
    retriever = ParentDocumentRetriever(fake, max_parent_docs=1)

    parents = retriever.get_relevant_documents("hello")

    assert len(parents) == 1
    assert parents[0].page_content == "child only"


if __name__ == "__main__":
    test_parent_retriever_expands_and_deduplicates_child_hits()
    test_parent_retriever_supports_legacy_get_relevant_documents()
    print("rag parent retriever tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_parent_retriever.py
```

Expected: `ImportError: cannot import name 'ParentDocumentRetriever'`.

- [ ] **Step 3: Implement wrapper in `backend/rag/retriever.py`**

Add import:

```python
from rag.chunking import expand_child_documents_to_parents
```

Add class above `_retriever = None`:

```python
class ParentDocumentRetriever:
    """Search child chunks, return de-duplicated parent documents."""

    def __init__(self, child_retriever, max_parent_docs: int):
        self.child_retriever = child_retriever
        self.max_parent_docs = max_parent_docs

    def invoke(self, query):
        if hasattr(self.child_retriever, "invoke"):
            child_docs = self.child_retriever.invoke(query)
        else:
            child_docs = self.child_retriever.get_relevant_documents(query)
        return expand_child_documents_to_parents(
            child_docs,
            max_parent_docs=self.max_parent_docs,
        )

    def get_relevant_documents(self, query):
        return self.invoke(query)
```

- [ ] **Step 4: Wrap the Qdrant retriever**

In `get_retriever()`, replace:

```python
_retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
```

with:

```python
child_retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K * 3})
_retriever = ParentDocumentRetriever(child_retriever, max_parent_docs=TOP_K)
```

- [ ] **Step 5: Update timeout config test fake vector store**

In `backend/tests_local/test_rag_timeout_config.py`, keep `FakeVectorStore.as_retriever()` returning `self`. Add an assertion after `retriever_mod.get_retriever()`:

```python
    assert retriever_mod._retriever.max_parent_docs == settings.rag_top_k
```

Also ensure cleanup still sets:

```python
retriever_mod._retriever = None
```

- [ ] **Step 6: Run retriever tests**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_parent_retriever.py
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_timeout_config.py
```

Expected:

```text
rag parent retriever tests passed
rag timeout config tests passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/rag/retriever.py backend/tests_local/test_rag_parent_retriever.py backend/tests_local/test_rag_timeout_config.py
git commit -m "feat: return parent documents from rag retriever"
```

---

## Task 4: Format enriched metadata in RAG context

**Files:**
- Modify: `backend/rag/chain.py`
- Create: `backend/tests_local/test_rag_chain_format_documents.py`

- [ ] **Step 1: Write failing formatting test**

Create `backend/tests_local/test_rag_chain_format_documents.py`:

```python
"""Verify retrieved document formatting includes enriched metadata."""
from langchain_core.documents import Document

from rag.chain import _format_documents


def test_format_documents_includes_source_and_section_title():
    docs = [
        Document(
            page_content="DTI dưới 35% là an toàn.",
            metadata={
                "source": "policy.md",
                "section_title": "4.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)",
                "source_type": "policy",
            },
        )
    ]

    formatted = _format_documents(docs)

    assert "[1] policy.md — 4.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)" in formatted
    assert "DTI dưới 35%" in formatted


def test_format_documents_keeps_existing_fallback_for_no_metadata():
    docs = [Document(page_content="plain text", metadata={})]

    formatted = _format_documents(docs)

    assert "[1]" in formatted
    assert "plain text" in formatted


if __name__ == "__main__":
    test_format_documents_includes_source_and_section_title()
    test_format_documents_keeps_existing_fallback_for_no_metadata()
    print("rag chain document formatting tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_format_documents.py
```

Expected: assertion fails because current header is only `[1] policy.md`.

- [ ] **Step 3: Update `_format_documents()` header logic**

In `backend/rag/chain.py`, replace:

```python
source = metadata.get("source") or metadata.get("file_path") or metadata.get("title")
header = f"[{index}] {source}" if source else f"[{index}]"
```

with:

```python
source = metadata.get("source") or metadata.get("file_path") or metadata.get("title")
section = metadata.get("section_title")
if source and section:
    header = f"[{index}] {source} — {section}"
elif source:
    header = f"[{index}] {source}"
else:
    header = f"[{index}]"
```

- [ ] **Step 4: Run formatting test**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_format_documents.py
```

Expected: `rag chain document formatting tests passed`.

- [ ] **Step 5: Run fallback chain test**

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_retriever_fallback.py
```

Expected: `RAG retriever fallback test passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/rag/chain.py backend/tests_local/test_rag_chain_format_documents.py
git commit -m "feat: include section metadata in rag document context"
```

---

## Task 5: Final verification and rollout note

**Files:**
- No production files.
- Optional docs update if the project maintains RAG ops notes: `docs/11_benchmark_rag.md`

- [ ] **Step 1: Run deterministic RAG tests**

```bash
cd backend
for f in tests_local/test_rag_chunking_semantic.py \
         tests_local/test_rag_parent_retriever.py \
         tests_local/test_rag_ingest_semantic_chunks.py \
         tests_local/test_rag_ingest_cli.py \
         tests_local/test_rag_timeout_config.py \
         tests_local/test_rag_chain_format_documents.py \
         tests_local/test_rag_chain_retriever_fallback.py \
         tests_local/test_rag_qdrant_config.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f"
done
```

Expected: every script prints its pass message.

- [ ] **Step 2: Run import/compile checks**

```bash
cd /home/taitu/GitHub/Loan_ETL
.venv/bin/python -m compileall -q backend/rag backend/tests_local
git diff --check
```

Expected: no output and exit 0 for both commands.

- [ ] **Step 3: Run ingest dry-run**

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --dry-run
```

Expected:

```text
Loaded <N> documents -> <M> chunks
--- Chunk 1 (<source> | <source_type> | <section_title> | parent=<id>) ---
...
Dry run: would upsert <M> chunks to '<collection>'
```

This command must not initialize embeddings or call Qdrant.

- [ ] **Step 4: Manual rollout command (do not run unless Qdrant should be rebuilt)**

Only after local dry-run output looks sane:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m rag.ingest --recreate
```

Expected: Qdrant collection is recreated with new child chunks and parent metadata. This is intentionally destructive for the collection.

- [ ] **Step 5: Commit optional docs note if changed**

If `docs/11_benchmark_rag.md` is updated with the new `--recreate` requirement, commit:

```bash
git add docs/11_benchmark_rag.md
git commit -m "docs: note rag semantic chunking ingest rollout"
```

If no docs changed, skip this commit.

---

## Acceptance criteria checklist

- [ ] `backend/rag/ingest.py` does not import or use `RecursiveCharacterTextSplitter`.
- [ ] Child chunks include `parent_id`, `chunk_index`, `section_title`, `source_type`, `parent_content`.
- [ ] Parent retriever returns parent documents de-duped by `parent_id`.
- [ ] Retrieval still supports both `.invoke()` and `.get_relevant_documents()`.
- [ ] `_format_documents()` includes source + section title when metadata exists.
- [ ] `python -m rag.ingest --dry-run` does not call embeddings or Qdrant.
- [ ] Deterministic RAG tests pass.

---

## Notes for executor

- Do not run `tests_local/test_rag_benchmark.py` as part of normal verification. It logs into the app, calls the LLM evaluator, sleeps between dataset rows, and writes `docs/rag_benchmark_results.json`.
- After implementation, Qdrant must be rebuilt with `--recreate`; old fixed chunks and new parent-child chunks should not coexist in one collection.
- If `backend/rag/__init__.py` stale exports (`load_chat_history`, `get_or_create_session`) fail during import checks, fix them in a separate small cleanup commit rather than mixing with chunking behavior.

---

## Plan self-review

- Spec coverage: semantic chunking, parent-document retrieval, metadata enrichment, dry-run and rollout are all mapped to tasks.
- Placeholder scan: no placeholder markers.
- Type consistency: `split_documents_semantically`, `expand_child_documents_to_parents`, and `ParentDocumentRetriever` names are consistent across tasks.
- Scope: one implementation stream; no frontend/database/live benchmark work.
