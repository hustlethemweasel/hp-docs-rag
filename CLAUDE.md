# CLAUDE.md

HP Docs RAG ChatBot — a take-home project built spec-first. **SPEC.md is the
source of truth**; read it before making changes. If implementation needs to
deviate from the spec, amend SPEC.md in a `docs:` commit *before* the code.
Never cite SPEC.md section numbers in code, comments, or commit messages —
they shift when the spec is edited. Reference by topic instead.

## Constitution (non-negotiable — SPEC.md's Project Constitution)

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

## Commands (task runner: mise — see `mise.toml`; run from repo root)

```bash
mise run install                         # uv sync (src layout)
mise run test                            # fast suite; coverage gate must stay green
mise run test:slow                       # slow suite; needs db reachable (docker compose up db)
mise run fmt                             # Black, check-only (matches CI)
mise run fmt:fix                         # Black, applies formatting
mise run lint                            # ruff check (matches CI)
mise run lint:fix                        # ruff check --fix
mise run typecheck                       # pyrefly
mise run check                           # fmt + lint + typecheck + test — the full CI gate
mise run eval                            # retrieval eval against an ingested database
```

Equivalent raw commands still work from `backend/` if mise isn't installed
(`uv run pytest --cov=app`, `uv run black src tests migrations`, etc.) —
`mise.toml` is a thin wrapper, not a new source of truth.

## Status

- **Milestone 1 done:** Compose, baseline migration (verified against real
  pg16+pgvector, reversible), health endpoint, checksum-verified ingest
  scaffolding, CI (fast gate + slow suite + commitlint).
- **Milestone 2 done:** pymupdf4llm parsing → section-aware chunking (~450
  tokens, ~80 overlap) → harrier embeddings (asymmetric: query-side
  instruction prompt only) → pgvector writes, verified end-to-end in Compose
  against both real PDFs (515 chunks). Figure captioning is provider-selectable
  (`LLM_PROVIDER=anthropic|ollama`) via `build_captioner`. A retrieval-only
  eval (`eval/`) was pulled forward from Milestone 5 to gate model/chunking
  changes with recall@k/MRR evidence before they ship — see `eval/REPORT.md`
  for the harrier-vs-e5-small-v2 decision.
- **Next — Milestone 3:** hybrid search (dense + Postgres FTS, RRF fusion),
  `ChatProvider` abstraction (+ `ScriptedProvider` for the fast suite and
  load tests), SSE chat endpoint, conversation history persistence.
- A background task is fixing an oversized-chunk edge case the eval surfaced
  (sentence-less blocks, e.g. large markdown tables, bypassing the ~450-token
  target) — re-run `mise run eval` after it lands to confirm no regression.

## Layout

`backend/src/app/` — application (`api/`, `ingest/`, `repositories/`; `rag/`
and `providers/` arrive in Milestone 3) · `backend/tests/` — fast + slow
suites · `backend/migrations/` — Alembic owns all DDL · `docs/` — source PDFs
+ checksums.txt · `eval/` — retrieval eval (live) and the full quality
benchmark (Milestone 5) · `loadtest/` — arrives in Milestone 6.
