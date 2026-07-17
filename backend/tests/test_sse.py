"""Behavior: SSE event framing for the chat stream (token/done/error).

Exactly one terminal event (done or error) per stream; this module only
covers framing itself, per the constitution's call-out that the fast suite
tests all three event types at the framing level.
"""

import json
import uuid

from app.api.sse import done_event, error_event, token_event


def parse(frame: str) -> tuple[str, dict]:
    event_line, data_line = frame.strip("\n").split("\n", 1)
    return event_line.removeprefix("event: "), json.loads(
        data_line.removeprefix("data: ")
    )


def test_token_event_frames_a_text_delta():
    event, payload = parse(token_event("Hello"))

    assert event == "token"
    assert payload == {"text": "Hello"}


def test_done_event_carries_sources_and_message_ids():
    user_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    sources = [{"chunk_id": 1, "document": "ENVY Guide", "pages": "12", "score": 0.9}]

    event, payload = parse(
        done_event(
            sources=sources,
            user_message_id=user_id,
            assistant_message_id=assistant_id,
            latency_ms=850,
        )
    )

    assert event == "done"
    assert payload == {
        "sources": sources,
        "user_message_id": str(user_id),
        "assistant_message_id": str(assistant_id),
        "latency_ms": 850,
    }


def test_error_event_carries_the_message_and_ids():
    user_id = uuid.uuid4()
    assistant_id = uuid.uuid4()

    event, payload = parse(
        error_event(
            message="provider unreachable",
            user_message_id=user_id,
            assistant_message_id=assistant_id,
        )
    )

    assert event == "error"
    assert payload == {
        "message": "provider unreachable",
        "user_message_id": str(user_id),
        "assistant_message_id": str(assistant_id),
    }
