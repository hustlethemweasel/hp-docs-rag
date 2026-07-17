"""Slow suite: real figure extraction + real Ollama captioning.

Requires a reachable Ollama with qwen3.5:4b pulled, and the real HP ENVY PDF
checked into docs/.
"""

from pathlib import Path

import httpx
import pytest

from app.ingest.captioning import OllamaCaptioner
from app.ingest.figures import extract_figures

pytestmark = pytest.mark.slow

ENVY_PDF = Path(__file__).parent.parent.parent / "docs" / "hp-envy-6000-user-guide.pdf"


def _ollama_reachable() -> bool:
    try:
        return (
            httpx.get("http://localhost:11434/api/tags", timeout=2).status_code == 200
        )
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(
    not ENVY_PDF.is_file(), reason="requires docs/hp-envy-6000-user-guide.pdf"
)
@pytest.mark.skipif(
    not _ollama_reachable(), reason="requires a reachable Ollama server"
)
def test_captions_a_real_figure_from_the_envy_manual():
    [figure, *_] = extract_figures(ENVY_PDF, min_dimension=100)
    client = httpx.Client(base_url="http://localhost:11434", timeout=120)
    captioner = OllamaCaptioner(client=client, model="qwen3.5:4b")

    caption = captioner.caption(figure.image_bytes)

    assert isinstance(caption, str)
    assert len(caption) > 20
