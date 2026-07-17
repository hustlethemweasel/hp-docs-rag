from app.providers.base import ChatMessage, ChatProvider

REWRITE_SYSTEM_PROMPT = (
    "Rewrite the user's latest message as a standalone search query for "
    "retrieving relevant manual passages, resolving pronouns and implicit "
    "references using the conversation history. Reply with only the "
    "rewritten query, no preamble."
)


async def rewrite_query(
    provider: ChatProvider,
    history: list[ChatMessage],
    question: str,
    temperature: float | None = None,
) -> str:
    """Condense history + question into a standalone query; skipped on turn one."""
    if not history:
        return question
    messages = [*history, ChatMessage(role="user", content=question)]
    kwargs: dict[str, object] = {"system": REWRITE_SYSTEM_PROMPT}
    if temperature is not None:
        kwargs["temperature"] = temperature
    tokens = [token async for token in provider.stream_chat(messages, **kwargs)]
    return "".join(tokens).strip()
