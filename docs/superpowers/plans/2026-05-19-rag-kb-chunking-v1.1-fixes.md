# RAG KB Chunking V1.1 — Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 defects from the KB chunking V1 audit: heading flattening (Critical), FAQ preamble drop, and missing migration note.

**Architecture:** Replace the flat heading scan with a hierarchical algorithm: `#` becomes `document_title` metadata, `##` becomes the section boundary, `###`+ stays inside the parent. Preamble (content between `#` and first `##`) and FAQ preamble (content before first `**Q:`) become standalone parent sections. `_format_documents` renders `document_title → section_title` when both exist. CLAUDE.md documents the `--recreate` requirement.

**Tech Stack:** Python 3.11+, standalone test scripts in `backend/tests_local/`, regex-based Markdown parsing (`re`), LangChain `Document` objects. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-05-19-rag-kb-chunking-v1.1-fixes-design.md](../specs/2026-05-19-rag-kb-chunking-v1.1-fixes-design.md)

**Independent from:** `docs/superpowers/plans/2026-05-19-rag-eval-and-memory-polish.md` — touches different files, Codex can run both in parallel.

---

## File Structure

**Modified files:**
- `backend/rag/chunking.py` — heading hierarchy + FAQ preamble + document_title metadata.
- `backend/rag/chain.py` — `_format_documents` renders `document_title → section_title` when both are set.
- `backend/tests_local/test_rag_chunking_semantic.py` — new + updated tests for the new algorithm shape.
- `backend/tests_local/test_rag_chain_format_documents.py` — assert new header rendering when both fields present.
- `CLAUDE.md` — add a Note before/after the Qdrant `--recreate` example.

**No new files.**

---

## Task 1: Document-title helper

**Files:**
- Modify: `backend/rag/chunking.py` (new helper `_extract_h1_title`)
- Test: `backend/tests_local/test_rag_chunking_semantic.py` (new test function)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests_local/test_rag_chunking_semantic.py` (above the `if __name__ == "__main__":` block):

```python
def test_extract_h1_title_returns_first_h1_text():
    from rag.chunking import _extract_h1_title
    md = "# Chính sách cho vay\n\nPhần intro.\n\n## DTI\nNội dung."
    assert _extract_h1_title(md) == "Chính sách cho vay"


def test_extract_h1_title_returns_none_when_absent():
    from rag.chunking import _extract_h1_title
    assert _extract_h1_title("## Only h2\n\nNội dung.") is None
    assert _extract_h1_title("Không có heading.") is None
```

Wire both into the `if __name__ == "__main__":` block.

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: `ImportError: cannot import name '_extract_h1_title'`.

- [ ] **Step 3: Implement the helper**

Add to `backend/rag/chunking.py` near `_extract_document_title` (around line 107):

```python
_H1_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _extract_h1_title(markdown: str) -> str | None:
    """Return the first ``# Heading`` text, or None if no level-1 heading exists."""
    match = _H1_PATTERN.search(markdown)
    if match is None:
        return None
    return match.group(1).strip()
```

If `_H1_PATTERN` already exists with the same name, reuse it.

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: all checks pass including the two new ones.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chunking.py backend/tests_local/test_rag_chunking_semantic.py
git commit -m "feat: _extract_h1_title helper for chunking"
```

---

## Task 2: Hierarchical Markdown splitter — `##`-based parents + preamble + `document_title`

**Files:**
- Modify: `backend/rag/chunking.py` (`_split_markdown_into_parent_sections` rewrite + metadata wiring)
- Test: `backend/tests_local/test_rag_chunking_semantic.py` (4 new cases)

- [ ] **Step 1: Write 4 failing tests**

Append to `backend/tests_local/test_rag_chunking_semantic.py`:

```python
def test_h1_preamble_becomes_parent_when_h2_follows():
    from rag.chunking import chunk_documents
    from langchain_core.documents import Document

    md = (
        "# Chính sách cho vay\n\n"
        "Phần giới thiệu chung.\n\n"
        "## DTI\n\n"
        "Nội dung DTI.\n\n"
        "## Credit Score\n\n"
        "Nội dung credit score."
    )
    chunks = chunk_documents([Document(page_content=md, metadata={"source": "policy.md"})])

    parents = [c for c in chunks if c.metadata.get("retrieval_unit") == "parent"]
    titles = sorted(p.metadata["section_title"] for p in parents)
    assert titles == ["Chính sách cho vay", "Credit Score", "DTI"]

    preamble = next(p for p in parents if p.metadata["section_title"] == "Chính sách cho vay")
    assert "giới thiệu chung" in preamble.page_content
    assert preamble.metadata["document_title"] == "Chính sách cho vay"

    dti = next(p for p in parents if p.metadata["section_title"] == "DTI")
    assert dti.metadata["document_title"] == "Chính sách cho vay"


def test_document_without_h2_uses_h1_as_section_boundary():
    from rag.chunking import chunk_documents
    from langchain_core.documents import Document

    md = "# Section A\n\nNội dung A.\n\n# Section B\n\nNội dung B."
    chunks = chunk_documents([Document(page_content=md, metadata={"source": "two-h1.md"})])

    parents = [c for c in chunks if c.metadata.get("retrieval_unit") == "parent"]
    titles = sorted(p.metadata["section_title"] for p in parents)
    assert titles == ["Section A", "Section B"]


def test_document_without_headings_becomes_single_parent():
    from rag.chunking import chunk_documents
    from langchain_core.documents import Document

    md = "Chỉ có nội dung.\n\nKhông có heading nào."
    chunks = chunk_documents([Document(page_content=md, metadata={"source": "plain.md"})])

    parents = [c for c in chunks if c.metadata.get("retrieval_unit") == "parent"]
    assert len(parents) == 1
    assert "Không có heading" in parents[0].page_content


def test_children_inherit_document_title():
    from rag.chunking import chunk_documents
    from langchain_core.documents import Document

    md = (
        "# Doc Title\n\nIntro.\n\n## Section X\n\n"
        + ("Nội dung dài. " * 200)  # force chunking
    )
    chunks = chunk_documents([Document(page_content=md, metadata={"source": "doc.md"})])

    children = [c for c in chunks if c.metadata.get("retrieval_unit") == "child"]
    assert children, "expected at least one child chunk"
    for child in children:
        assert child.metadata["document_title"] == "Doc Title"
```

Wire all 4 into `if __name__ == "__main__":`.

- [ ] **Step 2: Run — expect failures**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: `AssertionError` from at least one of the new tests — the flat algorithm produces 3 parents for the first case but with wrong shape (the `# Chính sách` parent would currently be `Chính sách cho vay` containing only intro, but it would be ranked alongside `DTI` and `Credit Score` at the SAME level. Verify by reading the failure messages — they tell you exactly which assertion is off.)

- [ ] **Step 3: Rewrite `_split_markdown_into_parent_sections`**

In `backend/rag/chunking.py`, locate the existing `_split_markdown_into_parent_sections` function (around lines 115-152 per the audit). Replace with:

```python
_H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _split_markdown_into_parent_sections(
    markdown: str,
    *,
    source_path: str,
    source_name: str,
    document_title: str,
) -> list[dict]:
    """Split a Markdown document into hierarchical parent sections.

    Algorithm:
      1. If there is a level-1 ``# Heading``, extract it as ``document_title``
         (already passed in); content before the first ``##`` is the
         "preamble" and becomes its own parent named after document_title.
      2. Split the remaining body on ``##`` markers. Each ``##`` block
         becomes one parent (sub-headings ``###``+ stay inside the parent's
         content).
      3. If no ``##`` exists, fall back: split on ``#`` markers (legacy
         behaviour for `#`-only docs).
      4. If no headings at all, the whole body is one parent named after
         document_title.
    """
    sections: list[dict] = []
    h2_matches = list(_H2_PATTERN.finditer(markdown))

    if h2_matches:
        # Preamble = everything before the first ##.
        preamble_text = markdown[: h2_matches[0].start()].strip()
        # Strip the leading "# Title" line if present so it isn't duplicated
        # inside the preamble content.
        preamble_text = _H1_PATTERN.sub("", preamble_text, count=1).strip()
        if preamble_text:
            sections.append({
                "section_title": document_title,
                "content": preamble_text,
            })

        for idx, match in enumerate(h2_matches):
            start = match.start()
            end = h2_matches[idx + 1].start() if idx + 1 < len(h2_matches) else len(markdown)
            block = markdown[start:end].strip()
            # Strip the "## Heading" line from the content.
            heading_line, _, rest = block.partition("\n")
            section_title = heading_line.lstrip("#").strip()
            sections.append({
                "section_title": section_title,
                "content": rest.strip(),
            })
        return sections

    # No ##: fall back to # splitting (legacy behaviour).
    h1_matches = list(_H1_PATTERN.finditer(markdown))
    if h1_matches:
        for idx, match in enumerate(h1_matches):
            start = match.start()
            end = h1_matches[idx + 1].start() if idx + 1 < len(h1_matches) else len(markdown)
            block = markdown[start:end].strip()
            heading_line, _, rest = block.partition("\n")
            section_title = heading_line.lstrip("#").strip()
            sections.append({
                "section_title": section_title,
                "content": rest.strip(),
            })
        return sections

    # No headings at all.
    body = markdown.strip()
    if body:
        sections.append({
            "section_title": document_title,
            "content": body,
        })
    return sections
```

Then in the caller of `_split_markdown_into_parent_sections` (e.g. `chunk_documents` or `enrich_document_metadata`), ensure `document_title` is computed via `_extract_h1_title(markdown) or _extract_document_title(source_name)` and passed in.

Also propagate `document_title` to the chunk metadata for both parent and child chunks:
- Parent chunks already had `section_title`, `parent_id`, `parent_content`, etc. — add `document_title`.
- Children inherit `document_title` from the parent (they already inherit `section_title` via `parent_content`; mirror that).

- [ ] **Step 4: Run — expect new tests to pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: all checks pass.

- [ ] **Step 5: Run the broader chunking/retrieval test suite for regression**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_parent_retriever.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_ingest_semantic_chunks.py
```

Expected: all pass. If `test_rag_ingest_semantic_chunks.py` breaks because of the `or` guard (`section_title == "Policy" or "DTI"`), update it to assert the exact expected value (`"Policy"` if the input is `# Policy\n## DTI`).

- [ ] **Step 6: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chunking.py backend/tests_local/test_rag_chunking_semantic.py backend/tests_local/test_rag_ingest_semantic_chunks.py
git commit -m "fix: hierarchical markdown chunking — h1 → document_title, h2 → section boundary"
```

---

## Task 3: FAQ preamble preserved as a parent

**Files:**
- Modify: `backend/rag/chunking.py` (`_split_faq_sections`)
- Test: `backend/tests_local/test_rag_chunking_semantic.py` (new test)

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_faq_preamble_is_preserved_as_parent():
    from rag.chunking import chunk_documents
    from langchain_core.documents import Document

    md = (
        "# FAQ về CreditIntel\n\n"
        "Tài liệu này trả lời các câu hỏi thường gặp.\n\n"
        "---\n\n"
        "**Q: Bao lâu thì được duyệt?**\n\n"
        "**A:** 1-3 ngày làm việc."
    )
    chunks = chunk_documents([Document(page_content=md, metadata={"source": "faq.md"})])

    parents = [c for c in chunks if c.metadata.get("retrieval_unit") == "parent"]
    titles = [p.metadata["section_title"] for p in parents]
    assert "FAQ về CreditIntel" in titles, "preamble parent must exist"
    preamble = next(p for p in parents if p.metadata["section_title"] == "FAQ về CreditIntel")
    assert "câu hỏi thường gặp" in preamble.page_content
```

Add to `if __name__ == "__main__":`.

- [ ] **Step 2: Run — expect failure**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: AssertionError — the preamble is not currently emitted.

- [ ] **Step 3: Update `_split_faq_sections`**

Locate `_split_faq_sections` (around lines 140-152) in `backend/rag/chunking.py`. The current implementation starts at `matches[0].start()`, dropping the preamble. Update so that any non-whitespace content before `matches[0].start()` is emitted as the first parent:

```python
def _split_faq_sections(markdown: str, *, document_title: str) -> list[dict]:
    sections: list[dict] = []
    matches = list(_FAQ_PATTERN.finditer(markdown))

    if not matches:
        body = markdown.strip()
        if body:
            sections.append({"section_title": document_title, "content": body})
        return sections

    preamble_text = markdown[: matches[0].start()].strip()
    # Strip a leading "# Title" so the title isn't duplicated.
    preamble_text = _H1_PATTERN.sub("", preamble_text, count=1).strip()
    # Strip stray --- separators.
    preamble_text = re.sub(r"^-+\s*$", "", preamble_text, flags=re.MULTILINE).strip()
    if preamble_text:
        sections.append({
            "section_title": document_title,
            "content": preamble_text,
        })

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        content = markdown[start:end].strip().strip("-").strip()
        question_line = match.group(0).strip()
        sections.append({
            "section_title": question_line,
            "content": content,
        })
    return sections
```

Update the caller (likely `chunk_documents` or `enrich_document_metadata`) so it computes `document_title` for FAQ files the same way as for Markdown (via `_extract_h1_title` or filename fallback) and passes it in.

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chunking_semantic.py
```

Expected: all checks pass.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chunking.py backend/tests_local/test_rag_chunking_semantic.py
git commit -m "fix: preserve FAQ preamble before first **Q: as parent section"
```

---

## Task 4: `_format_documents` renders `document_title → section_title`

**Files:**
- Modify: `backend/rag/chain.py` (`_format_documents`)
- Test: `backend/tests_local/test_rag_chain_format_documents.py` (new test cases)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests_local/test_rag_chain_format_documents.py`:

```python
def test_format_documents_renders_document_title_with_section():
    from rag.chain import _format_documents
    from types import SimpleNamespace

    doc = SimpleNamespace(
        page_content="Nội dung DTI.",
        metadata={
            "source": "policy.md",
            "document_title": "Chính sách",
            "section_title": "DTI",
        },
    )
    text = _format_documents([doc])
    assert "Chính sách" in text
    assert "DTI" in text
    assert "→" in text or "->" in text  # arrow connector


def test_format_documents_collapses_when_titles_match():
    from rag.chain import _format_documents
    from types import SimpleNamespace

    doc = SimpleNamespace(
        page_content="Toàn văn.",
        metadata={
            "source": "plain.md",
            "document_title": "Plain",
            "section_title": "Plain",
        },
    )
    text = _format_documents([doc])
    # Document_title shouldn't appear twice in the header.
    assert text.count("Plain") == 1
```

Wire into `if __name__ == "__main__":`.

- [ ] **Step 2: Run — expect failures**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_format_documents.py
```

Expected: the arrow assertion fails — current `_format_documents` only renders `section_title`.

- [ ] **Step 3: Update `_format_documents`**

In `backend/rag/chain.py`, find `_format_documents` (around lines 168-173 per the audit). The current code probably renders `[N] {source} — {section_title}`. Update:

```python
def _format_documents(documents: list[Any]) -> str:
    if not documents:
        return "Không tìm thấy tài liệu liên quan trong kho kiến thức."

    chunks = []
    for index, doc in enumerate(documents, start=1):
        content = getattr(doc, "page_content", str(doc))
        metadata = getattr(doc, "metadata", {}) or {}
        source = metadata.get("source") or metadata.get("file_path") or metadata.get("title")
        document_title = metadata.get("document_title")
        section_title = metadata.get("section_title")

        if source and document_title and section_title and document_title != section_title:
            header = f"[{index}] {source} :: {document_title} → {section_title}"
        elif source and section_title:
            header = f"[{index}] {source} :: {section_title}"
        elif source:
            header = f"[{index}] {source}"
        else:
            header = f"[{index}]"

        chunks.append(f"{header}\n{content}")
    return "\n\n".join(chunks)
```

- [ ] **Step 4: Run — expect pass**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend && PYTHONPATH=. ../.venv/bin/python tests_local/test_rag_chain_format_documents.py
```

Expected: all checks pass.

- [ ] **Step 5: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add backend/rag/chain.py backend/tests_local/test_rag_chain_format_documents.py
git commit -m "feat: _format_documents shows document_title → section_title when both set"
```

---

## Task 5: Migration note in `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (Qdrant section)

- [ ] **Step 1: Add the note**

Open `/home/taitu/GitHub/Loan_ETL/CLAUDE.md`. Locate the Qdrant ingest section (the `## Qdrant (local, for RAG)` heading). Insert this block immediately AFTER the existing three ingest commands (dry-run, default, recreate):

```markdown
> **Note:** Sau khi nâng cấp chunking (V1+), bạn PHẢI chạy `--recreate` một lần để xoá chunks fixed-size cũ. Chạy không có `--recreate` sẽ trộn parent-child mới và fixed-size cũ trong cùng collection và làm hỏng parent expansion ở query time.
```

- [ ] **Step 2: Verify markdown renders cleanly**

```bash
grep -A 3 "PHẢI chạy" /home/taitu/GitHub/Loan_ETL/CLAUDE.md
```

Expected: the note appears once, code fence is closed correctly above and below.

- [ ] **Step 3: Commit**

```bash
cd /home/taitu/GitHub/Loan_ETL
git add CLAUDE.md
git commit -m "docs: warn about --recreate requirement after chunking upgrade"
```

---

## Task 6: Final sweep

- [ ] **Step 1: Run every chunking / retrieval / chain test**

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
for f in tests_local/test_rag_chunking_semantic.py \
         tests_local/test_rag_parent_retriever.py \
         tests_local/test_rag_ingest_semantic_chunks.py \
         tests_local/test_rag_chain_format_documents.py \
         tests_local/test_rag_chain_retriever_fallback.py \
         tests_local/test_rag_chain_import.py \
         tests_local/test_rag_ingest_cli.py \
         tests_local/test_rag_timeout_config.py \
         tests_local/test_rag_routing_guardrail_personalized.py; do
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All chunking + chain tests passed"
```

- [ ] **Step 2: No commit (verification only).**

---

## Acceptance criteria

- [x] `#`-level heading is captured as `document_title` metadata, not as a peer parent.
- [x] `##` is the section boundary; sub-headings (`###`+) stay inside the parent.
- [x] Preamble (content between `#` and first `##`) becomes its own parent with `section_title = document_title`.
- [x] FAQ files with content before the first `**Q:` keep that preamble as a parent.
- [x] Every chunk (parent and child) has `document_title` metadata.
- [x] `_format_documents` renders `document_title → section_title` when both are set and differ.
- [x] `CLAUDE.md` warns operators to use `--recreate` after upgrading chunking.
- [x] All chunking + retrieval + chain tests pass.
