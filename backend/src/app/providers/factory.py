import anthropic
import httpx

from app.config import Settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ChatProvider
from app.providers.ollama import OllamaProvider
from app.providers.scripted import ScriptedProvider

# A canned, citation-shaped answer so scenario (a) load-test traffic still
# exercises SSE token framing realistically; latency approximates ~33
# tokens/s, in the ballpark of real cloud LLM streaming throughput.
_SCRIPTED_ANSWER: str = (
    "To replace the ink cartridge, open the front access door, wait for the "
    "carriage to center, then press down on the old cartridge and pull it "
    "out. Insert the new cartridge until it clicks into place "
    "[HP ENVY 6000 User Guide, p. 42]."
)
_SCRIPTED_LATENCY = 0.03


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
    # Falling through means llm_provider == "scripted": the Literal on
    # Settings makes the branches exhaustive, so no trailing raise is needed.
    return ScriptedProvider(
        tokens=_SCRIPTED_ANSWER.split(" "), latency=_SCRIPTED_LATENCY
    )
