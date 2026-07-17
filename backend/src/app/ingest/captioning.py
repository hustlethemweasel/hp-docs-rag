import base64

import httpx
import structlog

logger = structlog.get_logger(__name__)

CAPTION_PROMPT = (
    "Describe this technical manual figure densely: labels, arrows, "
    "part numbers, and any step references visible."
)


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
