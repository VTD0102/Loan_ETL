from sqlalchemy.orm import Session


def build_user_context(db: Session, user_id: int) -> str:
    """Query loan_applications + risk data for user, return formatted string for prompt."""
    # TODO: fetch latest loan_application for user_id
    # TODO: format as readable text block (see RAG_chatbot_plan.md §7.2)
    raise NotImplementedError
