import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import get_settings
from app.ingest.embedding import Embedder, load_embedder
from app.rag.chat_service import ChatService
from app.rag.retrieval import HybridRetriever
from app.repositories.chunks import ChunkRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.messages import MessageRepository


async def get_user_id(
    x_user_id: Annotated[uuid.UUID, Header(alias="X-User-Id")],
) -> uuid.UUID:
    return x_user_id


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    async with request.app.state.database.connection() as connection:
        yield connection


def get_embedder(request: Request) -> Embedder:
    """Lazily load embedding weights on first use, cached on app.state.

    Loading real model weights is too slow/networked for the fast suite's
    lifespan to pay eagerly; routes that need it are dependency-overridden
    in tests instead.
    """
    if not hasattr(request.app.state, "embedder"):
        request.app.state.embedder = load_embedder(get_settings().embedding_model)
    return request.app.state.embedder


async def get_conversations(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ConversationRepository:
    return ConversationRepository(connection)


async def get_messages(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> MessageRepository:
    return MessageRepository(connection)


async def get_chat_service(
    request: Request,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    conversations: Annotated[ConversationRepository, Depends(get_conversations)],
    messages: Annotated[MessageRepository, Depends(get_messages)],
) -> ChatService:
    settings = get_settings()
    retriever = HybridRetriever(
        embedder=embedder,
        chunks=ChunkRepository(connection),
        candidates=settings.retrieval_candidates,
        top_k=settings.top_k,
    )
    return ChatService(
        provider=request.app.state.provider,
        provider_name=settings.llm_provider,
        model=settings.llm_model,
        retriever=retriever,
        conversations=conversations,
        messages=messages,
    )
