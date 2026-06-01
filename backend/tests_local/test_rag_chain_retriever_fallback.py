import logging

import rag.chain as chain
from rag.exceptions import RetrievalError


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class FailingRetriever:
    def invoke(self, question):
        raise RetrievalError("qdrant is down")


class FakeChain:
    def invoke(self, payload):
        assert payload["question"] == "Tôi nên cải thiện hồ sơ vay như thế nào?"
        assert payload["user_context"] == "customer context"
        assert "Không tìm thấy tài liệu liên quan" in payload["context"]
        return "fallback answer"


def main():
    original_chain = chain._chain
    original_get_retriever = chain.get_retriever
    original_classify_intent = chain.classify_intent
    capture_handler = CaptureHandler()
    chain.logger.addHandler(capture_handler)
    try:
        chain._chain = FakeChain()
        chain.get_retriever = lambda: FailingRetriever()
        chain.classify_intent = lambda question, chat_history: "personal_advice"

        result = chain.invoke(
            "Tôi nên cải thiện hồ sơ vay như thế nào?",
            "customer context",
            [],
        )

        assert result["answer"] == "fallback answer"
        assert result["source_documents"] == []
        retrieval_logs = [
            record for record in capture_handler.records
            if "Retrieval failed" in record.getMessage()
        ]
        assert retrieval_logs, "expected retrieval fallback to be logged"
        assert retrieval_logs[-1].exc_info is None, "expected no traceback for fallback log"
        print("RAG retriever fallback test passed")
    finally:
        chain.logger.removeHandler(capture_handler)
        chain._chain = original_chain
        chain.get_retriever = original_get_retriever
        chain.classify_intent = original_classify_intent


if __name__ == "__main__":
    main()
