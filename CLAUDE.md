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
mise run eval:quality                    # response-quality benchmark (golden set + LLM-as-judge)
mise run eval:rerank                     # cross-encoder re-ranker spike

mise run frontend:install                # npm ci
mise run frontend:test                   # Vitest suite
mise run frontend:fmt                    # Prettier, check-only (matches CI)
mise run frontend:lint                   # ESLint (matches CI)
mise run frontend:typecheck              # tsc --noEmit
mise run frontend:check                  # fmt + lint + typecheck + test — the full frontend CI gate
```

Equivalent raw commands still work from `backend/` if mise isn't installed
(`uv run pytest --cov=app`, `uv run black src tests migrations`, etc.) —
`mise.toml` is a thin wrapper, not a new source of truth. Same for `frontend/`
(`npm run test`, `npm run lint`, etc.). `mise.toml` provisions Node via
`[tools]`; no separate Node install is required.

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
- **Milestone 3 done:** `HybridRetriever` (dense + Postgres FTS, RRF fusion
  k=60, top-6, refusal-threshold guard) → `ChatProvider` abstraction
  (`AnthropicProvider`, `OllamaProvider`, `ScriptedProvider`; `openai` still
  unimplemented, matching the M2 captioning factory) → history windowing +
  query rewriting → `ChatService` orchestration → SSE chat endpoint +
  conversation CRUD, all backed by real `conversations`/`messages`
  repositories. 106 fast tests @ 92.8% coverage. Verified live (curl) against
  real ingested chunks and the real Anthropic provider: cited multi-turn
  answers, correct query rewriting on a pronoun follow-up, persisted history,
  and a terminal `error` event with the partial message saved as
  `status='error'` on an unreachable-provider run.
- **Milestone 4 done:** Next.js 16 App Router SPA — conversation sidebar
  (create/switch/delete), streamed chat (POST-based SSE, since `EventSource`
  can't send a body), citation chips, history restored on reload via
  `X-User-Id`. 37 Vitest/RTL tests. CORS restricted to the frontend origin.
  `frontend` Compose service rebuilt as a real multi-stage Next.js build.
  Verified live in the browser against real ingested chunks and the real
  Anthropic provider. Manual verification (not the unit suite) caught two
  real bugs: CORS middleware added inside `lifespan()` crashed under a real
  ASGI server (Starlette locks its middleware stack on the first call,
  including the lifespan dispatch itself — fixed by wiring it in
  `create_app()` instead), and the sidebar didn't refresh after a message
  completed, leaving a new conversation's title blank until reload (fixed
  with a shared `ConversationsContext`).
- **Milestone 5 done:** 37-question golden set (`eval/golden.jsonl`) across
  factual, procedure, figure-dependent, multi-turn, and negative categories,
  seeded from `eval/retrieval.jsonl`. `eval/run.py` scores RAGAS-style
  LLM-as-judge metrics (faithfulness, answer relevancy, context
  precision/recall, refusal correctness) against the real `HybridRetriever`
  + configured `ChatProvider`, temperature pinned to 0; results cached
  per-provider under `eval/results/` (gitignored) and rendered into
  `eval/REPORT.md`. Live run against claude-haiku-4-5: refusal accuracy
  0.973, context recall 0.970, context precision 0.748, faithfulness 0.915,
  answer relevancy 0.938. `REFUSAL_THRESHOLD` tuning investigated the fused
  RRF score and raw dense cosine similarity as candidate signals — neither
  cleanly separates negative from positive cases in this embedding space
  without costing real recall, so it stays at 0; the real gap turned out to
  be the benchmark's own refusal-phrase detector missing valid refusal
  phrasings, fixed with before/after evidence (0.919 → 0.973). The
  cross-encoder re-ranker open question (SPEC §18) is resolved: a spike
  (`eval/rerank_experiment.py`) showed a wash on the golden set (recall@6
  unchanged, MRR −0.006, context precision +0.032) — not adopted. 142 fast
  backend tests.
- The oversized-chunk edge case the eval surfaced (sentence-less blocks, e.g.
  large markdown tables, bypassing the ~450-token target) is fixed — a hard
  word-window fallback in the chunker, evidence in `eval/REPORT.md`.
- **Milestone 6 done:** `RequestIDMiddleware` + structured error envelope
  closed R2. `loadtest/locustfile.py` drives the real conversation-create +
  SSE chat flow; a `locust` Compose service (`loadtest` profile) runs it
  headless. `LLM_PROVIDER=scripted` makes `ScriptedProvider` selectable on a
  live `api` for load-test scenario (a). That scenario caught and fixed two
  real bugs in sequence: synchronous query embedding blocking uvicorn's
  single-process event loop for *all* concurrent requests, not just
  embedding ones (`asyncio.to_thread`, TDD) — which, once fixed, exposed a
  PyTorch thread-safety race on the shared embedding model now genuinely
  called concurrently (`threading.Lock` in `Embedder`, TDD). The DB
  connection pool was also sized up with `pool_pre_ping=True`
  (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`, TDD). Full ramp, before/after evidence,
  and scenario (b) (real claude-haiku-4-5 provider) results are in
  `loadtest/REPORT.md`: scenario (a) sustains ~891 req/min within threshold
  (60 users, zero errors) after all three fixes — up from ~541 req/min
  pre-fix, roughly 3x the safe-concurrency ceiling; scenario (b) confirms
  LLM generation dominates (p95 ~8.5s), ~208 req/min at 10 users, zero
  errors. 152 fast backend tests @ 93.4% coverage. SPEC.md §3's
  requirements table reads Done on every row.

## Layout

`backend/src/app/` — application (`api/`, `ingest/`, `repositories/`, `rag/`,
`providers/`) · `backend/tests/` — fast + slow suites · `backend/migrations/`
— Alembic owns all DDL · `frontend/src/` — Next.js App Router SPA
(`app/` routes, `components/`, `hooks/`, `lib/`) · `docs/` — source PDFs +
checksums.txt · `eval/` — retrieval eval and the full response-quality
benchmark (Milestone 5) · `loadtest/` — Locust scenario + `REPORT.md`
(Milestone 6).
