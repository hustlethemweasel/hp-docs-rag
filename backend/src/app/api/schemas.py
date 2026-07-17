import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ConversationSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[dict[str, Any]] | None
    provider: str | None
    model: str | None
    latency_ms: int | None
    status: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    content: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
