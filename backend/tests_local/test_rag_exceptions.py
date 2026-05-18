"""Verify RAGError hierarchy."""
from rag.exceptions import RAGError, RetrievalError, LLMError, RAGTimeoutError


def test_hierarchy():
    assert issubclass(RetrievalError, RAGError)
    assert issubclass(LLMError, RAGError)
    assert issubclass(RAGTimeoutError, RAGError)
    assert issubclass(RAGError, Exception)


def test_instantiation_and_message():
    exc = RetrievalError("qdrant down")
    assert isinstance(exc, RAGError)
    assert str(exc) == "qdrant down"


if __name__ == "__main__":
    test_hierarchy()
    test_instantiation_and_message()
    print("rag.exceptions hierarchy tests passed")
