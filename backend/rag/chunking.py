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
