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
    assert all(chunk.metadata.get("document_title") == "Chính sách" for chunk in chunks)


def test_h1_preamble_becomes_parent_when_h2_follows():
    md = (
        "# Chính sách cho vay\n\n"
        "Phần giới thiệu chung.\n\n"
        "## DTI\n\n"
        "Nội dung DTI.\n\n"
        "### Nested Criteria\n\n"
        "Chi tiết phụ vẫn thuộc DTI.\n\n"
        "## Credit Score\n\n"
        "Nội dung credit score."
    )
    chunks = split_documents_semantically([
        Document(page_content=md, metadata={"source": "policy.md"}),
    ])

    parents = expand_child_documents_to_parents(chunks)
    titles = sorted(parent.metadata["section_title"] for parent in parents)
    assert titles == ["Chính sách cho vay", "Credit Score", "DTI"]

    preamble = next(
        parent for parent in parents
        if parent.metadata["section_title"] == "Chính sách cho vay"
    )
    assert "giới thiệu chung" in preamble.page_content
    assert preamble.metadata["document_title"] == "Chính sách cho vay"

    dti = next(parent for parent in parents if parent.metadata["section_title"] == "DTI")
    assert "Nested Criteria" in dti.page_content
    assert dti.metadata["document_title"] == "Chính sách cho vay"


def test_document_without_h2_uses_h1_as_section_boundary():
    md = "# Section A\n\nNội dung A.\n\n# Section B\n\nNội dung B."
    chunks = split_documents_semantically([
        Document(page_content=md, metadata={"source": "two-h1.md"}),
    ])

    parents = expand_child_documents_to_parents(chunks)
    titles = sorted(parent.metadata["section_title"] for parent in parents)
    assert titles == ["Section A", "Section B"]


def test_document_without_headings_becomes_single_parent():
    md = "Chỉ có nội dung.\n\nKhông có heading nào."
    chunks = split_documents_semantically([
        Document(page_content=md, metadata={"source": "plain.md"}),
    ])

    parents = expand_child_documents_to_parents(chunks)
    assert len(parents) == 1
    assert "Không có heading" in parents[0].page_content


def test_children_inherit_document_title():
    md = "# Doc Title\n\nIntro.\n\n## Section X\n\n" + ("Nội dung dài. " * 200)
    chunks = split_documents_semantically([
        Document(page_content=md, metadata={"source": "doc.md"}),
    ])

    assert chunks, "expected at least one child chunk"
    for child in chunks:
        assert child.metadata["document_title"] == "Doc Title"


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


def test_faq_preamble_is_preserved_as_parent():
    md = (
        "# FAQ về CreditIntel\n\n"
        "Tài liệu này trả lời các câu hỏi thường gặp.\n\n"
        "---\n\n"
        "**Q: Bao lâu thì được duyệt?**\n\n"
        "**A:** 1-3 ngày làm việc."
    )
    chunks = split_documents_semantically([
        Document(page_content=md, metadata={"source": "faq.md"}),
    ])

    parents = expand_child_documents_to_parents(chunks)
    titles = [parent.metadata["section_title"] for parent in parents]
    assert "FAQ về CreditIntel" in titles, "preamble parent must exist"
    preamble = next(
        parent for parent in parents
        if parent.metadata["section_title"] == "FAQ về CreditIntel"
    )
    assert "câu hỏi thường gặp" in preamble.page_content


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


def test_extract_h1_title_returns_first_h1_text():
    from rag.chunking import _extract_h1_title

    md = "# Chính sách cho vay\n\nPhần intro.\n\n## DTI\nNội dung."
    assert _extract_h1_title(md) == "Chính sách cho vay"


def test_extract_h1_title_returns_none_when_absent():
    from rag.chunking import _extract_h1_title

    assert _extract_h1_title("## Only h2\n\nNội dung.") is None
    assert _extract_h1_title("Không có heading.") is None


if __name__ == "__main__":
    test_enrich_document_metadata_infers_source_fields()
    test_heading_sections_become_parent_child_chunks()
    test_h1_preamble_becomes_parent_when_h2_follows()
    test_document_without_h2_uses_h1_as_section_boundary()
    test_document_without_headings_becomes_single_parent()
    test_children_inherit_document_title()
    test_faq_question_answer_block_stays_together()
    test_faq_preamble_is_preserved_as_parent()
    test_expand_child_documents_to_parents_deduplicates_by_parent_id()
    test_extract_h1_title_returns_first_h1_text()
    test_extract_h1_title_returns_none_when_absent()
    print("semantic chunking tests passed")
