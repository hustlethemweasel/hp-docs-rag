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

All six milestones are done — SPEC.md's requirements table reads Done on
every row, with per-milestone evidence recorded in SPEC.md's Milestones
section. This section is the current state; the history (which bugs each
harness caught, which decisions the evals settled) lives in SPEC.md,
`eval/REPORT.md`, and `loadtest/REPORT.md`.

- **Ingest:** pymupdf4llm parsing → section-aware chunking (~450 tokens, ~80
  overlap, hard word-window fallback for sentence-less blocks like large
  tables) → harrier embeddings (asymmetric: query-side instruction prompt
  only) → pgvector. Figure captioning is provider-selectable via
  `build_captioner` (`LLM_PROVIDER=anthropic|ollama`). Both real PDFs
  ingested end-to-end in Compose (515 chunks).
- **Serving:** `HybridRetriever` (dense + Postgres FTS with OR-of-words
  query construction, RRF k=60, top-6, refuses when retrieval comes back
  empty) → history windowing + query rewriting to English on **every turn
  including the first** (see SPEC's multilingual section) → `ChatService`
  → SSE chat endpoint + conversation CRUD, with
  `RequestIDMiddleware` and a structured error envelope. Providers:
  `AnthropicProvider`, `OllamaProvider`, `ScriptedProvider` (fast suite +
  load-test scenario (a)). The never-implemented `openai` option and the
  dead `REFUSAL_THRESHOLD` knob were removed in the post-M6 polish pass.
- **Frontend:** Next.js 16 App Router SPA — conversation sidebar
  (create/switch/delete), POST-based SSE streaming (`EventSource` can't send
  a body), citation chips, history restored on reload via `X-User-Id`; CORS
  restricted to the frontend origin.
- **Evidence:** `eval/REPORT.md` — retrieval eval (recall@k/MRR@20, the gate
  for model/chunking changes; hybrid beats dense 0.971/0.838 vs 0.941/0.782
  on the 34-question basis since the FTS OR-of-words fix) and the
  response-quality benchmark on the 50-case golden set (incl. the
  exact-token and pt-BR slices), judged by pinned `claude-sonnet-5`:
  claude-haiku-4-5 refusal 0.980 / faithfulness 0.857; local qwen3.5:4b
  0.940 / 0.726 (context recall 0.932 for both — same retriever; the pt-BR
  slice is 1.000 refusal / 1.000 context recall on both providers).
  `loadtest/REPORT.md` — ~891 req/min within threshold (scenario a),
  LLM-dominated p95 ~8.5s (scenario b). The rejected re-ranker spike is
  restorable from commit `f1b92a9`.
- **Suites:** 165 fast backend tests @ ~93.6% coverage; 37 Vitest/RTL
  frontend tests.
- Verified live (browser + curl) against real ingested chunks with both the
  real Anthropic provider and the Ollama local path (`qwen3.5:4b` on host
  Ollama, Metal, `think:false`): cited procedure answers, pronoun-resolving
  query rewriting across a multi-turn follow-up, and out-of-domain refusal
  all confirmed streaming end-to-end through `OllamaProvider`.

## Layout

`backend/src/app/` — application (`api/`, `ingest/`, `repositories/`, `rag/`,
`providers/`) · `backend/tests/` — fast + slow suites · `backend/migrations/`
— Alembic owns all DDL · `frontend/src/` — Next.js App Router SPA
(`app/` routes, `components/`, `hooks/`, `lib/`) · `docs/` — source PDFs +
checksums.txt · `eval/` — retrieval eval and the full response-quality
benchmark (Milestone 5) · `loadtest/` — Locust scenario + `REPORT.md`
(Milestone 6).
