from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI

from backend.core.config import settings
from backend.rag.config import LLM_MODEL, OPENROUTER_BASE_URL
from backend.rag.prompts import chat_prompt
from backend.rag.retriever import get_retriever

_chain = None


def get_chain() -> ConversationalRetrievalChain:
    global _chain
    if _chain is None:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0.3,
        )
        _chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=get_retriever(),
            combine_docs_chain_kwargs={"prompt": chat_prompt},
            return_source_documents=True,
        )
    return _chain


def invoke(question: str, user_context: str, chat_history: list) -> dict:
    # TODO: call get_chain().invoke with question, user_context, chat_history
    # TODO: return {"answer": str, "source_documents": list}
    raise NotImplementedError
