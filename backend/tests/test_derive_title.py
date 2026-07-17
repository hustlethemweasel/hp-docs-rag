"""Behavior: conversation titles auto-derive from the first message, truncated."""

from app.rag.chat_service import TITLE_MAX_LENGTH, derive_title


def test_short_content_becomes_the_title_verbatim():
    assert derive_title("How do I replace the cartridge?") == (
        "How do I replace the cartridge?"
    )


def test_whitespace_is_collapsed():
    assert derive_title("How do I\n replace   it?") == "How do I replace it?"


def test_long_content_is_truncated_with_an_ellipsis():
    content = "x" * 100

    title = derive_title(content)

    assert len(title) == TITLE_MAX_LENGTH
    assert title.endswith("…")
    assert title[:-1] == "x" * (TITLE_MAX_LENGTH - 1)
