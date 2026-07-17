import anthropic
import httpx

from app.config import Settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ChatProvider
from app.providers.ollama import OllamaProvider


def build_provider(settings: Settings) -> ChatProvider:
    """Select the chat provider from LLM_PROVIDER."""
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return AnthropicProvider(
            client=anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key),
            model=settings.llm_model,
        )
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            client=httpx.AsyncClient(base_url=settings.ollama_url, timeout=120),
            model=settings.llm_model,
        )
    raise NotImplementedError(
        f"no chat provider for LLM_PROVIDER={settings.llm_provider}"
    )
