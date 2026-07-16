# CLAUDE.md

HP Docs RAG ChatBot — a take-home project built spec-first. **SPEC.md is the
source of truth**; read it before making changes. If implementation needs to
deviate from the spec, amend SPEC.md in a `docs:` commit *before* the code.

## Constitution (SPEC.md §2 — non-negotiable)

1. **TDD.** Tests are the behavior specification. Write the failing test first.
2. **Real collaborators.** Prefer the real thing over doubles. The fast suite
   is self-contained (no external resources — in-process SQLite counts as a
   real engine); the slow suite (`-m slow`) uses real Postgres/pgvector.
3. **No double naming.** Never `Fake*`/`Mock*`/`Stub*`. Name doubles for what
   they do (e.g. `ScriptedProvider`). Never an unspecced mock — use
   `create_autospec` when a mock is necessary.
4. **Fail fast.** `try/except` blocks are short and guard one specific
   exception at the exact spot. Never handle unforeseen errors.
5. **Logging.** structlog, logfmt. Log decisions and boundaries, not noise.
6. **Conventional Commits.** Allowed: feat, fix, test, refactor, perf, docs,
   build, ci. **No `chore`** — if nothing fits, reconsider the change.

## Commands (run from `backend/`)

```bash
uv sync                                  # install (src layout)
uv run pytest --cov=app                  # fast suite; 90% gate must stay green
uv run pytest -m slow --no-cov           # slow suite; needs DATABASE_URL
uv run black src tests migrations        # user codes in Black style
uv run ruff check src tests migrations
uv run pyrefly check
uv run alembic upgrade head              # schema; migrations own the DDL
```

## Status

- **Milestone 1 done:** Compose, baseline migration (verified against real
  pg16+pgvector, reversible), health endpoint, checksum-verified ingest
  scaffolding, CI (fast gate + slow suite + commitlint).
- **Next — Milestone 2 (SPEC §7):** pymupdf4llm parsing → section-aware
  chunking (~450 tokens, ~80 overlap) → harrier embeddings (asymmetric:
  query-side instruction prompt only) → pgvector writes. First red test:
  the chunker.
- Before first compose up: run `./scripts/fetch_docs.sh` (verify HP URLs
  inside it first) to pin document checksums.

## Layout

`backend/src/app/` — application (api/, ingest/, rag/ and providers/ arrive in
M2–M3) · `backend/tests/` — fast + slow suites · `backend/migrations/` —
Alembic owns all DDL · `docs/` — source PDFs + checksums.txt · `eval/`,
`loadtest/` — arrive in M5–M6.
