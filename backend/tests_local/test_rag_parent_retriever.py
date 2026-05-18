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
