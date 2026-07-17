import base64
from typing import Protocol

import anthropic
import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)

CAPTION_PROMPT = (
    "Describe this technical manual figure in one dense paragraph: labels, "
    "arrows, part numbers, and any step references visible. No preamble."
)

# Captions are one dense paragraph — a deliberately short output.
MAX_CAPTION_TOKENS = 1024

# Errors any captioner may raise for a single figure; ingestion skips the
# figure and continues rather than losing the whole document (SPEC §7.4).
CAPTION_ERRORS = (httpx.HTTPError, anthropic.APIError)


class Captioner(Protocol):
    def caption(self, image_bytes: bytes) -> str: ...


class OllamaCaptioner:
    """Offline VLM figure captioning via Ollama (SPEC §7.4).

    `think: false` is required — qwen3.5:4b is a reasoning model that, left
    to its default, spends the whole call on hidden thinking tokens and
    returns an empty `content` field.
    """

    def __init__(self, client: httpx.Client, model: str) -> None:
        self._client = client
        self._model = model

    def caption(self, image_bytes: bytes) -> str:
        image_b64 = base64.b64encode(image_bytes).decode()
        response = self._client.post(
            "/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": CAPTION_PROMPT,
                        "images": [image_b64],
                    }
                ],
                "stream": False,
                "think": False,
            },
        )
        response.raise_for_status()
        caption = response.json()["message"]["content"].strip()
        logger.info("figure_captioned", model=self._model, caption_length=len(caption))
        return caption


class AnthropicCaptioner:
    """Cloud VLM figure captioning via the Anthropic API (SPEC §7.4)."""

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def caption(self, image_bytes: bytes) -> str:
        image_b64 = base64.b64encode(image_bytes).decode()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_CAPTION_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": CAPTION_PROMPT},
                    ],
                }
            ],
        )
        caption = next(
            block.text for block in response.content if block.type == "text"
        ).strip()
        logger.info(
            "figure_captioned",
            model=self._model,
            caption_length=len(caption),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return caption


def build_captioner(settings: Settings) -> Captioner:
    """Select the captioning provider from LLM_PROVIDER (SPEC §7.4, §14)."""
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return AnthropicCaptioner(
            client=anthropic.Anthropic(api_key=settings.anthropic_api_key),
            model=settings.llm_model,
        )
    if settings.llm_provider == "ollama":
        return OllamaCaptioner(
            client=httpx.Client(base_url=settings.ollama_url, timeout=120),
            model=settings.llm_model,
        )
    raise NotImplementedError(f"no captioner for LLM_PROVIDER={settings.llm_provider}")
