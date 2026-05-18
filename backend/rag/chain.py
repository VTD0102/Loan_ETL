"""
chain.py

Main RAG pipeline for CreditIntel with routing, guardrails, and personalization.

Pipeline flow:
    1. Input guardrail  → block unsafe messages
    2. Intent router    → classify question intent
    3. Retrieval        → fetch docs (intent-aware: skip for greeting/off_topic)
    4. Personalization  → inject user name + tone + intent instructions
    5. LLM call         → generate response
    6. Output guardrail → sanitize unsafe content
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from core.config import settings
from rag.config import LLM_MODEL, OPENROUTER_BASE_URL
from rag.guardrails import check_input, check_output
from rag.personalizer import PersonalizationContext, get_intent_instructions
from rag.prompts import chat_prompt
from rag.retriever import get_retriever
from rag.router import classify_intent, needs_retrieval

logger = logging.getLogger(__name__)

_chain = None


def get_chain() -> Any:
    """Return the cached LangChain LCEL chain (prompt | llm | parser)."""
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


def invoke(
    question: str,
    user_context: str,
    chat_history: list,
    personalization: "PersonalizationContext | None" = None,
) -> dict:
    """Full RAG pipeline: guardrail → route → retrieve → personalise → LLM → guardrail.

    Parameters
    ----------
    question : str
        The user's message.
    user_context : str
        Pre-built textual context from ``context_builder.build_user_context``.
    chat_history : list
        LangChain message objects for conversation memory.
    personalization : PersonalizationContext, optional
        Pre-built personalization context. If ``None``, defaults are used.

    Returns
    -------
    dict
        ``answer``, ``source_documents``, ``intent``, and optionally ``blocked``.
    """
    # ── Step 1: Input guardrail ───────────────────────────────────────────
    input_check = check_input(question)
    if not input_check.passed:
        logger.info("Input guardrail blocked message: %s", input_check.reason)
        return {
            "answer": input_check.reason,
            "source_documents": [],
            "intent": "blocked",
            "blocked": True,
        }

    # ── Step 2: Intent routing ────────────────────────────────────────────
    intent = classify_intent(question, chat_history)
    logger.info("Classified intent: %s", intent)

    # ── Step 3: Retrieval (intent-aware) ──────────────────────────────────
    documents: list[Any] = []
    if needs_retrieval(intent):
        try:
            documents = _retrieve_documents(question)
        except Exception:
            logger.exception("Retrieval failed, continuing without docs")
            documents = []

    # ── Step 4: Personalization (caller-provided) ─────────────────────────
    if personalization is None:
        personalization = PersonalizationContext()
    intent_instructions = get_intent_instructions(intent)

    # ── Step 5: LLM call ─────────────────────────────────────────────────
    answer = get_chain().invoke({
        "question": question,
        "user_context": user_context,
        "context": _format_documents(documents),
        "chat_history": chat_history,
        "user_display_name": personalization.user_display_name,
        "personalization_instructions": personalization.tone_instructions,
        "intent_instructions": intent_instructions,
    })

    # ── Step 6: Output guardrail ──────────────────────────────────────────
    output_check = check_output(answer)
    if output_check.sanitized_text is not None:
        logger.info("Output guardrail modified response (reason=%s)", output_check.reason)
        answer = output_check.sanitized_text

    return {
        "answer": answer,
        "source_documents": documents,
        "intent": intent,
    }


# ── Internal helpers (unchanged) ─────────────────────────────────────────────

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
