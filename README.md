# HP Docs RAG ChatBot

A chatbot that answers questions about two HP product manuals — the HP ENVY
6000 All-in-One printer and the OMEN 17.3" gaming laptop — using
Retrieval-Augmented Generation over the manuals' own text and figures. Ask a
question in the chat UI and get a grounded answer with inline citations back to
the exact document and page, or a plain "not in the documents" when the manuals
don't cover it.

## Features

- **Grounded answers with citations.** Every claim cites its source as
  `[Document, p. X]`; the assistant refuses rather than guessing when retrieval
  finds nothing relevant.
- **Hybrid retrieval.** Dense vector search (pgvector) fused with Postgres
  full-text search via Reciprocal Rank Fusion, so both paraphrased questions and
  exact tokens (part numbers, error codes) retrieve well.
- **Figure-aware.** Diagrams and figures are captioned at ingestion time and
  indexed alongside text, so questions about callouts and diagrams are
  answerable.
- **Conversational.** Multi-turn history with follow-up resolution — each turn's
  query is rewritten to a standalone form before retrieval.
- **Multilingual.** Ask in Brazilian Portuguese (or another language) against the
  English manuals; queries are translated for retrieval and answers come back in
  the language you asked in.
- **Pluggable LLM providers.** A cloud provider (Anthropic) or a fully local one
  (Ollama) via a single environment variable — no API keys required for the
  local path.
- **Streaming chat UI.** Next.js single-page app with a conversation sidebar,
  live token streaming over SSE, citation chips, and history restored on reload.

## Architecture

```
PDFs ──▶ Ingestion ──▶ Postgres + pgvector ──▶ Retrieval ──▶ Chat API ──▶ Web UI
        (parse,          (chunks: vectors        (dense + FTS    (SSE stream,
         chunk,           + FTS index             fused w/ RRF)   citations)
         embed,           + chat history)
         caption)
```

- **Backend** — FastAPI (Python), SQLAlchemy async over Postgres 16 + pgvector.
  A single datastore serves as vector store, full-text index, and chat-history
  database.
- **Frontend** — Next.js App Router SPA (TypeScript).
- **Migrations** — Alembic owns all schema DDL.

See [SPEC.md](SPEC.md) for the full technical specification and design
rationale.

## Quickstart

```bash
./scripts/fetch_docs.sh          # download the HP PDFs, pin SHA-256s (once)
cp .env.example .env             # set LLM_PROVIDER + API key, or use the local profile
docker compose up --build                    # cloud provider (e.g. anthropic)
docker compose --profile local up --build    # fully local (Ollama), no API keys
```

Compose ingests both manuals on first boot, then starts the API and UI.

- Frontend: http://localhost:3000
- API health: http://localhost:8000/api/health

## Configuration

Copy `.env.example` to `.env` and adjust. Key settings:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `anthropic` (cloud) \| `ollama` (local) \| `scripted` (load testing) |
| `LLM_MODEL` | `qwen3.5:4b` | Generation model for the selected provider |
| `ANTHROPIC_API_KEY` | — | Required only for `LLM_PROVIDER=anthropic` |
| `OLLAMA_URL` | `http://ollama:11434` | Local provider endpoint |
| `TOP_K` | `6` | Number of retrieved chunks used as context |

See [SPEC.md](SPEC.md)'s configuration table for the full list (chunking,
embedding model, connection pool, log level).

## Development

Task runner: [mise](https://mise.jdx.dev). Commands run from the repo root:

```bash
mise run install      # uv sync
mise run test         # fast suite + coverage gate
mise run test:slow    # slow suite (needs `docker compose up db`)
mise run check        # fmt + lint + typecheck + fast suite — the full CI gate
mise run eval         # retrieval eval against an ingested database
mise run eval:quality # response-quality benchmark (golden set + LLM-as-judge)

mise run frontend:install   # npm ci
mise run frontend:check     # fmt + lint + typecheck + test — the full frontend gate
```

Without mise, the equivalent commands run from `backend/` and `frontend/` — see
[CLAUDE.md](CLAUDE.md) for the full list. The codebase follows the project
constitution in [SPEC.md](SPEC.md): TDD, real collaborators over mocks,
fail-fast error handling, structured logging, and Conventional Commits.

## Evaluation

- **Response quality** — `eval/run.py` scores a golden Q&A set with RAGAS-style
  LLM-as-judge metrics (faithfulness, answer relevancy, context precision/recall,
  refusal correctness), comparing the cloud and local providers. Results and
  tuning decisions: [eval/REPORT.md](eval/REPORT.md).
- **Retrieval** — `eval/retrieval.py` reports recall@k and MRR, the gate for
  embedding-model and chunking changes.

## Load testing

Locust drives the real conversation-create + SSE chat flow against a running
API instance:

```bash
docker compose --profile loadtest run --rm --no-deps locust \
  -f /mnt/locust/locustfile.py --headless \
  --users 20 --spawn-rate 2 --run-time 3m \
  --csv /mnt/locust/results/run --host http://api:8000
```

Requires `api` already running (see Quickstart). Set `LLM_PROVIDER=scripted`
and rebuild `api` to isolate API/retrieval/DB scalability from LLM throughput;
leave it on the real provider for end-to-end numbers. Throughput, latency
percentiles, and analysis: [loadtest/REPORT.md](loadtest/REPORT.md).

## Licensing note

PDF parsing uses PyMuPDF/pymupdf4llm (AGPL-3.0). This repository is a public
take-home project, compatible with AGPL distribution terms.
