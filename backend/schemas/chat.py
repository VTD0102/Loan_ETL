from pydantic import BaseModel, Field
from typing import Any, Optional
from uuid import UUID

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[UUID] = None

class ChatResponse(BaseModel):
    response: str
    session_id: UUID
    sources: list[dict[str, Any]] = Field(default_factory=list)
    pending_action: Optional[dict[str, Any]] = None
