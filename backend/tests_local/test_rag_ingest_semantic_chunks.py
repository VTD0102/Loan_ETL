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
