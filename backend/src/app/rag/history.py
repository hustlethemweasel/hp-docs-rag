from app.providers.base import ChatMessage

DEFAULT_WINDOW = 10  # SPEC: last 10 messages = 5 turns


def window(
    messages: list[ChatMessage], limit: int = DEFAULT_WINDOW
) -> list[ChatMessage]:
    return messages[-limit:]
