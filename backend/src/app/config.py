from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration contract mirroring the .env.example table in SPEC.md."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "openai", "ollama"] = "ollama"
    llm_model: str = "qwen3.5:4b"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_url: str = "http://ollama:11434"

    embedding_model: str = "microsoft/harrier-oss-v1-270m"

    chunk_tokens: int = 450
    chunk_overlap: int = 80
    retrieval_candidates: int = 20
    top_k: int = 6
    refusal_threshold: float = 0.0  # tuned in Milestone 5

    database_url: str
    docs_dir: str = "/docs"
    log_level: str = "info"
    frontend_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
