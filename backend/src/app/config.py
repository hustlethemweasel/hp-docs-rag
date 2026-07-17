from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# CORS is wired in main.create_app() before Settings (which requires
# DATABASE_URL) can safely be instantiated there; this constant is the single
# source of truth shared by both that default and this field's default.
DEFAULT_FRONTEND_ORIGIN = "http://localhost:3000"


class Settings(BaseSettings):
    """Configuration contract mirroring the .env.example table in SPEC.md."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "openai", "ollama", "scripted"] = "ollama"
    llm_model: str = "qwen3.5:4b"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_url: str = "http://ollama:11434"

    embedding_model: str = "microsoft/harrier-oss-v1-270m"

    chunk_tokens: int = 450
    chunk_overlap: int = 80
    retrieval_candidates: int = 20
    top_k: int = 6
    refusal_threshold: float = 0.0  # kept at 0 in Milestone 5 — see eval/REPORT.md

    database_url: str
    # Raised from SQLAlchemy's async engine defaults (5/10) — see
    # loadtest/REPORT.md for the saturation evidence.
    db_pool_size: int = 20
    db_max_overflow: int = 20
    docs_dir: str = "/docs"
    log_level: str = "info"
    frontend_origin: str = DEFAULT_FRONTEND_ORIGIN


@lru_cache
def get_settings() -> Settings:
    return Settings()
