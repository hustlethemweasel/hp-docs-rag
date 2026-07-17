import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service, get_conversations, get_messages, get_user_id
from app.api.schemas import (
    ConversationDetailResponse,
    ConversationSummaryResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.rag.chat_service import ChatService
from app.repositories.conversations import ConversationRepository, ConversationSummary
from app.repositories.messages import MessageRepository, StoredMessage

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _summary_response(summary: ConversationSummary) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        id=summary.id, title=summary.title, updated_at=summary.updated_at
    )


def _message_response(message: StoredMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=message.sources,
        provider=message.provider,
        model=message.model,
        latency_ms=message.latency_ms,
        status=message.status,
        created_at=message.created_at,
    )


@router.post("", response_model=ConversationSummaryResponse, status_code=201)
async def create_conversation(
    user_id: Annotated[uuid.UUID, Depends(get_user_id)],
    conversations: Annotated[ConversationRepository, Depends(get_conversations)],
) -> ConversationSummaryResponse:
    conversation_id = await conversations.create(user_id)
    summary = await conversations.get(conversation_id, user_id)
    if summary is None:
        raise RuntimeError("conversation vanished immediately after creation")
    return _summary_response(summary)


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    user_id: Annotated[uuid.UUID, Depends(get_user_id)],
    conversations: Annotated[ConversationRepository, Depends(get_conversations)],
) -> list[ConversationSummaryResponse]:
    summaries = await conversations.list_for_user(user_id)
    return [_summary_response(s) for s in summaries]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_user_id)],
    conversations: Annotated[ConversationRepository, Depends(get_conversations)],
    messages: Annotated[MessageRepository, Depends(get_messages)],
) -> ConversationDetailResponse:
    summary = await conversations.get(conversation_id, user_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    stored = await messages.list_for_conversation(conversation_id)
    return ConversationDetailResponse(
        id=summary.id,
        title=summary.title,
        messages=[_message_response(m) for m in stored],
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_user_id)],
    conversations: Annotated[ConversationRepository, Depends(get_conversations)],
) -> Response:
    deleted = await conversations.delete(conversation_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="conversation not found")
    return Response(status_code=204)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    user_id: Annotated[uuid.UUID, Depends(get_user_id)],
    conversations: Annotated[ConversationRepository, Depends(get_conversations)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    owned = await conversations.get(conversation_id, user_id)
    if owned is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return StreamingResponse(
        chat_service.stream_message(conversation_id, body.content),
        media_type="text/event-stream",
    )
