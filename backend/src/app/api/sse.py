import json
import uuid
from typing import Any, Literal

EventName = Literal["token", "done", "error"]


def format_event(event: EventName, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def token_event(text: str) -> str:
    return format_event("token", {"text": text})


def done_event(
    *,
    sources: list[dict[str, Any]],
    user_message_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    latency_ms: int,
) -> str:
    return format_event(
        "done",
        {
            "sources": sources,
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
            "latency_ms": latency_ms,
        },
    )


def error_event(
    *,
    message: str,
    user_message_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
) -> str:
    return format_event(
        "error",
        {
            "message": message,
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
        },
    )
