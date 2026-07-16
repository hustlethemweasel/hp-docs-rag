# HP Docs RAG ChatBot

A chatbot that answers questions about two HP product documents using
Retrieval-Augmented Generation. See [SPEC.md](SPEC.md) for the full technical
specification, including the project constitution (§2) that governs how this
codebase is built: TDD, real collaborators, truthful test doubles, fail-fast
error handling, logfmt logging, and Conventional Commits.

**Status: Milestone 1** — infra skeleton: Compose, migrations, health endpoint,
checksum-verified document ingestion scaffolding, CI.

## Quickstart

```bash
./scripts/fetch_docs.sh          # download the HP PDFs, pin SHA-256s (once)
cp .env.example .env             # defaults to the fully-local profile
docker compose --profile local up --build
```

Backend: http://localhost:8000/api/health · Frontend: http://localhost:3000

## Development

```bash
cd backend
uv sync
uv run pytest --cov=app          # fast suite + 90% coverage gate
uv run pytest -m slow --no-cov   # slow suite (needs DATABASE_URL)
uv run black src tests migrations && uv run ruff check src tests migrations
uv run pyrefly check
```

## Licensing note

PDF parsing uses PyMuPDF/pymupdf4llm (AGPL-3.0). This repository is a public
take-home project, compatible with AGPL distribution terms.
