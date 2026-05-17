from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from core.config import settings
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL
from rag.prompts import chat_prompt
from rag.retriever import get_retriever

_chain = None


def get_chain() -> Any:
    global _chain
    if _chain is None:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0.3,
        )
        _chain = chat_prompt | llm | StrOutputParser()
    return _chain


def invoke(question: str, user_context: str, chat_history: list) -> dict:
    try:
        documents = _retrieve_documents(question)
    except Exception:
        documents = []
    answer = get_chain().invoke({
        "question": question,
        "user_context": user_context,
        "context": _format_documents(documents),
        "chat_history": chat_history,
    })
    return {
        "answer": answer,
        "source_documents": documents,
    }


def _retrieve_documents(question: str) -> list[Any]:
    retriever = get_retriever()
    if hasattr(retriever, "invoke"):
        return retriever.invoke(question)
    return retriever.get_relevant_documents(question)


def _format_documents(documents: list[Any]) -> str:
    if not documents:
        return "Không tìm thấy tài liệu liên quan trong kho kiến thức."

    chunks = []
    for index, doc in enumerate(documents, start=1):
        content = getattr(doc, "page_content", str(doc))
        metadata = getattr(doc, "metadata", {}) or {}
        source = metadata.get("source") or metadata.get("file_path") or metadata.get("title")
        header = f"[{index}] {source}" if source else f"[{index}]"
        chunks.append(f"{header}\n{content}")
    return "\n\n".join(chunks)
