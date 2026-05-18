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
