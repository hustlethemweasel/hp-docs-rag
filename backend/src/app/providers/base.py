from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


class ChatProvider(Protocol):
    """Streams response text for a conversation.

    `kwargs` carries provider-agnostic extras (e.g. `system` for the system
    prompt) that not every provider needs but all must accept.
    """

    def stream_chat(
        self, messages: list[ChatMessage], **kwargs: object
    ) -> AsyncIterator[str]: ...
