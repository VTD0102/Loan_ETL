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

    assert "[1] policy.md :: 4.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)" in formatted
    assert "DTI dưới 35%" in formatted


def test_format_documents_keeps_existing_fallback_for_no_metadata():
    docs = [Document(page_content="plain text", metadata={})]

    formatted = _format_documents(docs)

    assert "[1]" in formatted
    assert "plain text" in formatted


def test_format_documents_renders_document_title_with_section():
    docs = [
        Document(
            page_content="Nội dung DTI.",
            metadata={
                "source": "policy.md",
                "document_title": "Chính sách",
                "section_title": "DTI",
            },
        )
    ]

    formatted = _format_documents(docs)

    assert "Chính sách" in formatted
    assert "DTI" in formatted
    assert "→" in formatted or "->" in formatted


def test_format_documents_collapses_when_titles_match():
    docs = [
        Document(
            page_content="Toàn văn.",
            metadata={
                "source": "plain.md",
                "document_title": "Plain",
                "section_title": "Plain",
            },
        )
    ]

    formatted = _format_documents(docs)

    assert formatted.count("Plain") == 1


if __name__ == "__main__":
    test_format_documents_includes_source_and_section_title()
    test_format_documents_keeps_existing_fallback_for_no_metadata()
    test_format_documents_renders_document_title_with_section()
    test_format_documents_collapses_when_titles_match()
    print("rag chain document formatting tests passed")
