from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

import anthropic
import httpx

Role = Literal["user", "assistant"]

# Errors any provider may raise mid-stream; the chat service catches these
# specifically to persist a partial message and emit a terminal error event.
PROVIDER_ERRORS = (httpx.HTTPError, anthropic.APIError)


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
