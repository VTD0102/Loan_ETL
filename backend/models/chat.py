from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[UUID] = None


class SourceChunk(BaseModel):
    file: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    session_id: UUID
    created_at: datetime


class ChatMessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    sources: Optional[list[SourceChunk]]
    created_at: datetime


class ChatSessionOut(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
