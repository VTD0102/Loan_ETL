# RAG KB Chunking V1.1 — Fixes design

**Date**: 2026-05-19
**Status**: Approved (post-audit of KB Chunking V1)
**Scope**: `backend/rag/chunking.py`, `backend/tests_local/test_rag_chunking_semantic.py`, `CLAUDE.md`

## Why

The audit of commits `27e9e91`..`0e46c74` (KB Chunking V1) found one critical and two important defects that all 28 tests miss:

1. **Critical — heading flattening.** `_split_markdown_into_parent_sections` treats every Markdown heading (`#` through `######`) as a peer-level parent boundary. For a typical knowledge-base file:

    ```markdown
    # Chính sách cho vay

    Đoạn giới thiệu.

    ## DTI
    ...
    ## Credit Score
    ...
    ```

    it produces three parents: `Chính sách cho vay` (just the intro paragraph), `DTI`, `Credit Score`. The `#`-level section becomes a near-empty stub parent. Child chunks inside `## DTI` lose the document-level title from their context.

2. **Important — FAQ preamble dropped.** `_split_faq_sections` starts the first section at `matches[0].start()`, silently discarding any content before the first `**Q:` marker — for example, a `# FAQ` heading or an intro paragraph.

3. **Important — no migration note committed.** Spec V1 said `--recreate` is required after rollout; no committed artifact records this. Anyone running `python -m rag.ingest` without `--recreate` mixes old fixed-size chunks with new parent-child payloads in the same Qdrant collection, and parent expansion fails silently at query time.

## Non-goals

- No changes to `expand_child_documents_to_parents`, retriever wrapper, `_format_documents`, or eval framework.
- No new metadata fields beyond what the existing schema supports.
- No re-embedding strategy changes.
- No move away from regex-driven splitting (semantic embedding splitter remains out of scope for this round).

---

## Fix 1 — Heading hierarchy (Critical)

### Approach

Replace the flat heading scan in `_split_markdown_into_parent_sections` with a **two-level** algorithm:

1. **Extract document title.** If the file begins with a single `#` heading (level 1), capture its text as `document_title` and treat everything below it (until the next `#` or EOF) as the document body. If no `#` heading exists, fall back to `_extract_document_title(source_name)`.
2. **Split the body on level-2 (`##`) headings.** Each `## X` block becomes one parent section. Any `###`/`####`/etc. inside a `##` block stays embedded in that parent's content (becomes part of `parent_content`).
3. **Edge cases:**
    - Document with **no `##`** but multiple `#` headings → treat each `#` as a section boundary (legacy behaviour).
    - Document with **only one `#` and no `##`** → whole body is one parent.
    - Document with **no headings at all** → whole body is one parent named after `document_title`.
    - **Preamble** (content between the `#` line and the first `##` line) → keep it as its own parent section with `section_title = document_title` (so it isn't lost), OR fold it into the first `##` section. **Pick the former** — easier to reason about and keeps the preamble retrievable as a standalone unit.

### Metadata additions

Every chunk (parent or child) gets:
- `document_title: str` — the `#`-level heading or the inferred filename title. Already present in some paths; ensure it is set for every chunk produced by both `_split_markdown_into_parent_sections` and `_split_faq_sections`.

This lets `chain._format_documents` display `document_title — section_title` when both exist, giving the LLM document-level context for sub-sections.

### `_format_documents` update

Update `_format_documents` so when both `document_title` and `section_title` are present and different, the header reads `[N] {source} :: {document_title} → {section_title}`. When they match (single-section doc), show just `[N] {source} :: {section_title}`. Out-of-scope: no behavioral change for retrievers that don't supply both fields — fall back to current rendering.

### Acceptance

- For input
  ```markdown
  # Chính sách cho vay

  Phần giới thiệu.

  ## DTI

  Nội dung DTI.

  ## Credit Score

  Nội dung credit score.
  ```
  the parents are:
    - `Chính sách cho vay` with content `Phần giới thiệu.` (preamble parent, `section_title = "Chính sách cho vay"`, `document_title = "Chính sách cho vay"`)
    - `DTI` with content including the `## DTI` block
    - `Credit Score` with content including the `## Credit Score` block
- All children of the `## DTI` block share the same `parent_id` and have `document_title = "Chính sách cho vay"`, `section_title = "DTI"`.
- For a document with no `##`, the whole body is one parent; tests cover this.
- For an FAQ-style file (no `#`, only `**Q:` markers), behaviour is delegated to `_split_faq_sections` and is unchanged by this fix.

---

## Fix 2 — FAQ preamble (Important)

### Approach

In `_split_faq_sections`, capture any content before `matches[0].start()` as a preamble parent section:
- If there is non-whitespace content before the first `**Q:` marker → emit it as a parent section with `section_title = document_title` (or `"Preamble"` if no `document_title`), `source_type = "faq"`.
- Then proceed with the existing Q/A loop unchanged.

### Acceptance

- For input
  ```markdown
  # FAQ về CreditIntel

  Tài liệu này trả lời câu hỏi thường gặp.

  ---

  **Q: Bao lâu thì duyệt?**

  **A:** 1-3 ngày làm việc.
  ```
  parents are:
    - Preamble: `section_title = "FAQ về CreditIntel"`, content includes the intro paragraph.
    - First Q/A: existing behaviour.

---

## Fix 3 — Migration note (Important)

### Approach

Update `CLAUDE.md` (the section about Qdrant ingest commands, added in the resilience-fixes work) to add a one-line callout that `--recreate` is required after upgrading the chunking algorithm:

```markdown
> **Note:** Sau khi nâng cấp chunking (V1+), bạn PHẢI chạy `--recreate` một lần để xoá chunks cũ. Chạy không có `--recreate` sẽ trộn parent-child mới và fixed-size cũ trong cùng collection và làm hỏng parent expansion ở query time.
```

Place this immediately before or after the `--recreate` command in the ingest section, so anyone reading docs sees it.

### Acceptance

- `CLAUDE.md` contains the note in the Qdrant section.
- No code changes.

---

## Tests

Add/update in `backend/tests_local/test_rag_chunking_semantic.py`:

1. **`test_hash_one_heading_does_not_split_at_hash_two`** — Markdown with one `#` and two `##` produces 3 parents (preamble + 2 `##`), each with the same `document_title`, distinct `section_title`s.
2. **`test_document_without_h2_uses_h1_as_section_boundary`** — Markdown with only `#` headings (no `##`) — each `#` becomes a parent section. Backwards compat.
3. **`test_document_without_headings_becomes_single_parent`** — Plain markdown produces 1 parent.
4. **`test_faq_preamble_is_preserved_as_parent`** — FAQ file with intro paragraph before first `**Q:` → preamble parent emitted with correct `section_title` and content.
5. **`test_existing_long_parent_split_invariant`** (or similar) — Long parent section still splits into multiple children that share the same `parent_id` (covers the spec V1 test gap audit flagged).

Update existing test `test_heading_sections_become_parent_child_chunks` (or rename) to assert `document_title` is set on every chunk.

## Order of work

1. **Fix 1 first** — biggest blast radius (touches algorithm core). All tests updated to assert the new shape.
2. **Fix 2 second** — independent function, but easier to verify after Fix 1's tests are passing (shared `document_title` plumbing).
3. **Fix 3 last** — doc-only.

Each fix is its own commit. After all three, run the full test sweep:
```bash
cd backend
for f in tests_local/test_rag_chunking_semantic.py tests_local/test_rag_parent_retriever.py tests_local/test_rag_ingest_semantic_chunks.py tests_local/test_rag_chain_format_documents.py tests_local/test_rag_ingest_cli.py tests_local/test_rag_timeout_config.py; do
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
```
Expected: all pass.

## Acceptance criteria (whole spec)

- The algorithm produces hierarchical parents, not flat heading peers.
- `document_title` flows through every chunk emitted by both splitters.
- FAQ preambles are preserved as parents.
- `CLAUDE.md` documents the `--recreate` migration requirement.
- All new and existing chunking/retrieval/format tests pass.

## Out of scope

- Embedding-based semantic splitter (`langchain-experimental`).
- Re-evaluating fixed metadata fields (parent_content size cap, overlap chars).
- Migrating any non-Markdown source format.
- Automatic re-ingest tooling — operators run `--recreate` manually.
