"""Behavior: cap conversation history to the last N messages (SPEC: 10 = 5 turns)."""

from app.providers.base import ChatMessage
from app.rag.history import DEFAULT_WINDOW, window


def message(i: int) -> ChatMessage:
    role = "user" if i % 2 == 0 else "assistant"
    return ChatMessage(role=role, content=f"message {i}")


def test_window_keeps_only_the_last_n_messages():
    messages = [message(i) for i in range(14)]

    windowed = window(messages, limit=10)

    assert windowed == messages[-10:]


def test_window_returns_everything_when_under_the_limit():
    messages = [message(i) for i in range(3)]

    assert window(messages, limit=10) == messages


def test_window_defaults_to_ten():
    messages = [message(i) for i in range(14)]

    assert window(messages) == messages[-DEFAULT_WINDOW:]
    assert DEFAULT_WINDOW == 10
