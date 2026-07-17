# HP Docs RAG ChatBot

A chatbot that answers questions about two HP product documents using
Retrieval-Augmented Generation. See [SPEC.md](SPEC.md) for the full technical
specification, including the project constitution that governs how this
codebase is built: TDD, real collaborators, truthful test doubles, fail-fast
error handling, logfmt logging, and Conventional Commits.

**Status: Milestone 2 done** — ingestion pipeline (parsing, chunking,
embeddings, figure captioning, pgvector writes) verified end-to-end against
both real HP manuals in Compose. Milestone 3 (retrieval + chat) is next.

## Quickstart

```bash
./scripts/fetch_docs.sh          # download the HP PDFs, pin SHA-256s (once)
cp .env.example .env             # set LLM_PROVIDER + API key, or use the local profile
docker compose up --build                    # cloud provider (e.g. anthropic)
docker compose --profile local up --build    # fully local, no API keys
```

Backend: http://localhost:8000/api/health · Frontend: http://localhost:3000

## Development

Task runner: [mise](https://mise.jdx.dev). Commands run from the repo root:

```bash
mise run install      # uv sync
mise run test         # fast suite + coverage gate
mise run test:slow    # slow suite (needs `docker compose up db`)
mise run check        # fmt + lint + typecheck + fast suite — the full CI gate
mise run eval         # retrieval eval against an ingested database
```

Without mise, the equivalent commands run from `backend/` — see
[CLAUDE.md](CLAUDE.md) for the full list.

## Licensing note

PDF parsing uses PyMuPDF/pymupdf4llm (AGPL-3.0). This repository is a public
take-home project, compatible with AGPL distribution terms.
