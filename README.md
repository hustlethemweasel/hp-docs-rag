# HP Docs RAG ChatBot

A chatbot that answers questions about two HP product documents using
Retrieval-Augmented Generation. See [SPEC.md](SPEC.md) for the full technical
specification, including the project constitution that governs how this
codebase is built: TDD, real collaborators, truthful test doubles, fail-fast
error handling, logfmt logging, and Conventional Commits.

**Status: all 6 milestones done** — ingestion, hybrid retrieval + chat, a
Next.js chat UI, an automated response-quality benchmark, and load testing
are all verified end-to-end against both real HP manuals. The response-quality
benchmark (`eval/run.py`) scores a 37-question golden set with RAGAS-style
LLM-as-judge metrics; see [eval/REPORT.md](eval/REPORT.md) for results and
tuning decisions. Load testing (`loadtest/locustfile.py`, Locust) exercises
the real conversation-create + SSE chat flow against a live API instance; see
[loadtest/REPORT.md](loadtest/REPORT.md) for sustained throughput, latency
percentiles, and bottleneck analysis for both scenarios — including two real
bugs the load test caught and fixed in sequence (synchronous query embedding
blocking the API's event loop, and the thread-safety race that fix exposed
in the shared embedding model). See [SPEC.md](SPEC.md) §16 for the full milestone history
and §3 for the requirements traceability table (all Done).

## Quickstart

```bash
./scripts/fetch_docs.sh          # download the HP PDFs, pin SHA-256s (once)
cp .env.example .env             # set LLM_PROVIDER + API key, or use the local profile
docker compose up --build                    # cloud provider (e.g. anthropic)
docker compose --profile local up --build    # fully local, no API keys
```

Backend: http://localhost:8000/api/health · Frontend: http://localhost:3000

## Load testing

```bash
docker compose --profile loadtest run --rm --no-deps locust \
  -f /mnt/locust/locustfile.py --headless \
  --users 20 --spawn-rate 2 --run-time 3m \
  --csv /mnt/locust/results/run --host http://api:8000
```

Requires `api` already running (see Quickstart). Set `LLM_PROVIDER=scripted`
in `.env` and rebuild `api` first to run the scenario that isolates
API/retrieval/DB scalability from LLM throughput (scenario (a) in
[loadtest/REPORT.md](loadtest/REPORT.md)); leave it on the real provider for
realistic end-to-end numbers (scenario (b)).

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

Without mise, the equivalent commands run from `backend/` — see
[CLAUDE.md](CLAUDE.md) for the full list.

## Licensing note

PDF parsing uses PyMuPDF/pymupdf4llm (AGPL-3.0). This repository is a public
take-home project, compatible with AGPL distribution terms.
