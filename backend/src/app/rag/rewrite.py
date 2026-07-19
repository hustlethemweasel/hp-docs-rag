from app.providers.base import ChatMessage, ChatProvider

# Wording tuned against qwen3.5:4b, not just claude: the 4B model ignores a
# parenthetical "in English" (it rewrote pt-BR questions in Portuguese), and
# any clause about copying part numbers/error codes makes it append literal
# "[Part Number]" placeholders. The imperative MUST phrasing translates
# reliably, and real tokens survive the rewrite without being asked for.
REWRITE_SYSTEM_PROMPT = (
    "Translate and rewrite the user's latest message as a standalone "
    "search query written in English, for retrieving passages from "
    "English-language manuals. The query MUST be in English even when "
    "the user writes in another language. Resolve pronouns and implicit "
    "references using the conversation history. Reply with only the "
    "rewritten English query, no preamble."
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
