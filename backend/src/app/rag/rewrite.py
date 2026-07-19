from app.providers.base import ChatMessage, ChatProvider

REWRITE_SYSTEM_PROMPT = (
    "Rewrite the user's latest message as a standalone search query in "
    "English (the manuals' language, whatever language the user writes in) "
    "for retrieving relevant manual passages, resolving pronouns and "
    "implicit references using the conversation history. Keep exact tokens "
    "like part numbers and error codes verbatim. Reply with only the "
    "rewritten query, no preamble."
)


async def rewrite_query(
    provider: ChatProvider,
    history: list[ChatMessage],
    question: str,
    temperature: float | None = None,
) -> str:
    """Condense history + question into a standalone English query.

    Runs on every turn, including the first: retrieval always sees an
    English query, so the corpus's foreign-language notice pages can't
    outrank topical chunks on non-English questions (SPEC's multilingual
    section).
    """
    messages = [*history, ChatMessage(role="user", content=question)]
    kwargs: dict[str, object] = {"system": REWRITE_SYSTEM_PROMPT}
    if temperature is not None:
        kwargs["temperature"] = temperature
    tokens = [token async for token in provider.stream_chat(messages, **kwargs)]
    return "".join(tokens).strip()
