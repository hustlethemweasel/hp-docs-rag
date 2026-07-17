"""Behavior: configuration is read from the environment with spec'd defaults.

The .env.example table in SPEC.md is the contract; these tests hold the
config module to it.
"""

from app.config import Settings

# Fields under test here have spec'd defaults; clearing their env vars keeps
# this hermetic regardless of what's exported in the developer's shell or
# loaded from the repo's .env by mise.
_SPEC_DEFAULT_ENV_VARS = [
    "LLM_PROVIDER",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "CHUNK_TOKENS",
    "CHUNK_OVERLAP",
    "RETRIEVAL_CANDIDATES",
    "TOP_K",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "LOG_LEVEL",
    "FRONTEND_ORIGIN",
]


def test_defaults_match_spec_contract(monkeypatch):
    for var in _SPEC_DEFAULT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    settings = Settings(database_url="postgresql+asyncpg://x/y")

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "qwen3.5:4b"
    assert settings.embedding_model == "microsoft/harrier-oss-v1-270m"
    assert settings.chunk_tokens == 450
    assert settings.chunk_overlap == 80
    assert settings.retrieval_candidates == 20
    assert settings.top_k == 6
    assert settings.db_pool_size == 20
    assert settings.db_max_overflow == 20
    assert settings.log_level == "info"
    assert settings.frontend_origin == "http://localhost:3000"


def test_environment_overrides_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("CHUNK_TOKENS", "300")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x/y")

    settings = Settings()

    assert settings.llm_provider == "anthropic"
    assert settings.chunk_tokens == 300
