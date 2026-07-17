# HP Docs RAG ChatBot — Technical Specification

**Status:** Draft v0.1
**Purpose:** Take-home assessment — end-to-end RAG chatbot answering questions about two HP product documents.

---

## 1. Overview

A web-based chatbot that answers user questions about two HP documents (HP ENVY 6000 All-in-One User Guide; OMEN 17.3" Gaming Laptop Maintenance & Service Guide) using Retrieval-Augmented Generation. The system is a Next.js SPA talking to a FastAPI backend, with PostgreSQL + pgvector serving as both the vector store and the chat-history store. The LLM layer is provider-agnostic: the same codebase runs against a cloud API or a local open-source model via Ollama, selected by configuration.

### Goals

- Answer questions grounded strictly in the two provided documents, with source citations (document + page).
- Support multi-turn conversations with persisted history.
- Ship fully containerized via Docker Compose, reproducible with one command.
- Demonstrate engineering rigor: ≥90% backend unit-test coverage, load-test results, and an automated answer-quality benchmark.

### Non-goals

- Authentication/multi-tenancy (single anonymous user or simple client-generated user ID).
- Ingesting arbitrary user-uploaded documents.
- Production-grade autoscaling, observability stacks, or CI/CD pipelines (a minimal CI running tests is a nice-to-have).

---

## 2. Project Constitution

Cross-cutting engineering principles that govern every implementation decision in this project. Where any later section conflicts with these, the constitution wins.

1. **Tests are the behavior specification.** The most effort goes into well-written tests, and development is test-driven (TDD): the test states the intended behavior before the code that satisfies it exists.
2. **Prefer real collaborators.** Doubles are useful, but they never replace the real thing. Unit tests are self-contained — no external dependencies or resources — yet the suite also includes slow tests that simulate the behavior of the actual application as closely as possible (real database, real HTTP boundary, real model where feasible).
3. **No special naming for test doubles.** A double should behave like the real thing as often as possible, and its name should reflect that expectation — name it for what it does, not for being a double. Doubles are kept truthful: never use an unspecced mock; when a mock is necessary, prefer `create_autospec` so the object's real interface is mimicked and interface drift breaks the test.
4. **Short, specific `try/except` blocks.** Exception handling is scoped to the exact unit of code and the specific exception we intend to guard against. We never handle unforeseen errors — better to break fast than to let the application run erroneous behavior silently.
5. **Judicious structured logging.** Logs use the logfmt format via `structlog`: log decisions and boundaries (requests, retrieval results, provider calls, ingestion steps), not noise.
6. **Conventional Commits for versioning.** Allowed types: `feat`, `fix`, `test`, `refactor`, `perf`, `docs`, `build` (dependencies, Docker, packaging), and `ci`. `feat` and `fix` drive semver (`BREAKING CHANGE` for majors). There is deliberately no `chore` — a catch-all type invites abuse; if a change fits no type, that's a signal to reconsider what the change actually is, not to reach for a bucket.

---

## 3. Requirements Traceability

This table is the progress scoreboard. **A requirement is Done only when its
evidence exists and passes in CI** — a green gate, a committed report, a passing
test — never on the strength of intent. Status changes ship in the same commit
as the work they describe.

| # | Requirement | How it's satisfied | Status |
|---|---|---|---|
| R1 | Frontend with GUI | Next.js (React) SPA — chat UI with history sidebar | Not started (placeholder page only) |
| R2 | Backend in Python with FastAPI | FastAPI app, async, Pydantic v2 models | In progress — skeleton + health (M1) |
| R3 | Unit tests ≥90% coverage | pytest + pytest-cov, `--cov-fail-under=90` enforced | In progress — gate enforced in CI and green since M1 (97.8%) |
| R4 | Cloud or local models | Provider abstraction: `anthropic` / `openai` / `ollama`, chosen via env var | Not started |
| R5 | Open-source vector DB | PostgreSQL 16 + pgvector extension | In progress — extension + HNSW schema migrated and verified (M1) |
| R6 | Only the attached documents | Ingestion pipeline reads exactly the two PDFs baked into the repo | In progress — checksum pinning + fail-fast verification built (M1) |
| R7 | Chunking strategy | Heading/structure-aware recursive chunking with overlap (§7.2) | In progress — chunker, parsing, and asymmetric embedder implemented and unit-tested; figure captioning + pgvector writes pending |
| R8 | Search strategy | Hybrid retrieval: dense (cosine) + sparse (Postgres FTS), fused with RRF (§8) | Not started |
| R9 | Conversation with chat history | Rolling window of prior turns injected into the prompt | Not started |
| R10 | Store chats/history in backend | `conversations` and `messages` tables in Postgres | In progress — schema migrated (M1); persistence code pending |
| R11 | Docker Compose | `frontend`, `api`, `db`, optional `ollama` services + one-shot `ingest` job | In progress — compose written and first boot verified locally (M1); `local`/`loadtest` profiles arrive M4/M6 |
| R12 | Load tests | Locust scenario; report requests/minute at latency thresholds (§12) | Not started |
| R13 | Benchmark response quality | Golden Q&A set + RAGAS-style metrics with LLM-as-judge (§13) | Not started |

---

## 4. Architecture

```
┌─────────────┐     HTTP/SSE      ┌──────────────────┐
│  Next.js    │ ────────────────▶ │  FastAPI backend │
│  SPA (web)  │ ◀──────────────── │                  │
└─────────────┘                   │  ┌────────────┐  │
                                  │  │ RAG service│  │
                                  │  │ Chat svc   │  │
                                  │  │ Providers  │──┼──▶ Anthropic / OpenAI APIs
                                  │  └────────────┘  │        or
                                  └───────┬──────────┘   ┌──────────┐
                                          │              │  Ollama  │ (container)
                                          ▼              └──────────┘
                                 ┌──────────────────┐
                                 │ Postgres 16      │
                                 │  + pgvector      │
                                 │  chunks (vectors)│
                                 │  conversations   │
                                 │  messages        │
                                 └──────────────────┘
```

Key decisions and rationale:

- **Single datastore.** pgvector lets Postgres serve as vector DB, full-text index, and relational store for chat history. One fewer container, transactional consistency between messages and retrieval logs, and it's fully open source (R5, R10).
- **Fixed embedding model, swappable chat model.** The vector index must not change when the chat provider changes. Embeddings are always produced by a local open-source model (`sentence-transformers`, `microsoft/harrier-oss-v1-270m`, 640-dim) running inside the API container on CPU. Only the *generation* step is provider-swappable. This avoids re-indexing and dimension mismatches when switching between cloud and local LLMs.
- **SSE streaming** for token-by-token responses in the chat UI.

---

## 5. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind | Chat UI, conversation sidebar, source-citation display |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, Alembic (migrations), structlog (logfmt) | Black code style, ruff lint, pyrefly type checking |
| Embeddings | sentence-transformers `microsoft/harrier-oss-v1-270m` | 270M, 640-dim, top MTEB score for its size; CPU-friendly, fixed across providers |
| Generation | Provider layer: Anthropic API, OpenAI API, Ollama (`qwen3.5:4b` default — 3.4 GB, vision-capable) | Selected via `LLM_PROVIDER` env var |
| Vector DB | Postgres 16 + pgvector (HNSW index) | Also stores chats + FTS index |
| PDF parsing | PyMuPDF + pymupdf4llm | Best fit for born-digital manuals (fast, reliable text + page numbers, built-in heading/structure detection); also powers figure extraction (§7.4). AGPL — fine for a public repo, noted in README. Docling documented as fallback if the benchmark exposes table-extraction gaps |
| Tests | pytest, pytest-cov, pytest-asyncio, httpx test client | ≥90% coverage gate |
| Load tests | Locust | Containerized, reproducible scenario |
| Quality benchmark | Custom harness + RAGAS-style metrics | Golden dataset in repo |
| Orchestration | Docker Compose v2 | Single `docker compose up` |

---

## 6. Data Model (Postgres)

```sql
documents(id, title, filename, sha256, page_count, ingested_at)

chunks(
  id, document_id → documents,
  content TEXT,
  embedding VECTOR(640),        -- HNSW index, cosine
  tsv TSVECTOR,                  -- GIN index for keyword search
  page_start INT, page_end INT,
  section TEXT,                  -- nearest heading, if detected
  token_count INT,
  chunk_index INT
)

conversations(
  id UUID,
  user_id UUID,                  -- client-generated, from X-User-Id header; indexed
  title, created_at, updated_at
)

messages(
  id UUID, conversation_id → conversations,
  role ENUM('user','assistant'),
  content TEXT,
  sources JSONB,                 -- [{chunk_id, document, pages, score}]
  provider TEXT, model TEXT,
  latency_ms INT,
  status TEXT,                   -- 'complete' | 'error' (provider failed mid-stream)
  created_at
)
```

Conversation title is auto-derived from the first user message (truncated).

---

## 7. Ingestion Pipeline

Runs as a one-shot Compose job (`ingest` service): it first applies Alembic migrations (which own the schema and `CREATE EXTENSION vector`), then indexes. `docs/` contains the two PDFs downloaded from HP with their SHA-256s pinned in `docs/checksums.txt`; ingest verifies the checksums at startup and is idempotent — already-indexed documents (matching hash) are skipped.

### 7.1 Parsing

- Extract text per page as structured markdown with **pymupdf4llm** (PyMuPDF's LLM-oriented layer), preserving page numbers and detected headings.
- Light cleaning: de-hyphenate line breaks, collapse whitespace, drop headers/footers detected by repetition across pages.
- Heading/section structure comes from pymupdf4llm's built-in layout analysis (replacing hand-rolled font-size heuristics); chunks are tagged with their nearest section title. Best-effort; falls back gracefully.

### 7.2 Chunking Strategy (R7)

**Structure-aware recursive chunking with overlap:**

1. Split first on detected section boundaries (headings), so a chunk never spans unrelated sections.
2. Within a section, recursively split on paragraph → sentence boundaries targeting **~450 tokens per chunk** with **~80 tokens overlap** (measured with the embedding model's tokenizer).
3. Each chunk stores `section`, `page_start/end`, and `chunk_index` metadata for citations.

Rationale: these are technical manuals with procedural steps and spec tables; section-bounded chunks keep procedures intact, the overlap protects against boundary cuts, and ~450 tokens keeps chunks precise for retrieval and citation granularity (the embedding model's 32k context is not the binding constraint — retrieval precision is). The chunk size/overlap are config values so the quality benchmark (§13) can be used to tune them.

### 7.3 Embedding & Indexing

- Batch-embed chunks with harrier-oss-v1-270m (documents encoded **without** an instruction prompt; embeddings are L2-normalized via last-token pooling).
- **Asymmetric encoding:** the model is instruction-tuned — *queries* must be encoded with a retrieval task instruction (sentence-transformers `prompt_name`/`prompt`), while documents are encoded plain. Omitting the query instruction measurably degrades retrieval, so the embedder wrapper enforces this distinction and unit tests cover it.
- Insert with `tsv = to_tsvector('english', content)`.
- HNSW index on `embedding` (cosine), GIN index on `tsv`.

### 7.4 Images & Figures (offline VLM captioning)

Both manuals rely heavily on figures (disassembly diagrams, LED patterns, part tables rendered as images). Rather than runtime multimodal retrieval, images are handled **once, at ingestion time**:

1. Extract figures/diagrams per page with PyMuPDF (filtering out decorative images by size heuristics).
2. Caption each figure with a vision model (the configured cloud provider, or — in the fully-local profile — the same `qwen3.5:4b`, which is vision-capable, so no extra model is needed) using a prompt that demands dense, technical descriptions — labels, arrows, part numbers, step references.
3. Index captions as regular text chunks with `chunk_type='figure_caption'` plus `page` and `figure_ref` metadata, flowing through the same embedding/FTS/hybrid pipeline.
4. The answer prompt instructs the model to point users to figures when relevant ("see Figure 2-3 on p. 41").

Rationale: captures most of the value of multimodal RAG (figure-dependent questions become answerable) at zero runtime cost — no GPU, no vision requirement on the swappable chat providers, no change to testing or load-test characteristics. The one-shot captioning cost is bounded (two documents, run once, cached by document hash).

**Stretch goal (documented, not default):** true multimodal retrieval with Qwen3-VL-Embedding + Qwen3-VL-Reranker (open-source, text/image/screenshot inputs in a unified vector space; 2B/8B variants; MRL-truncatable dims compatible with pgvector). Deliberately out of the default build because it requires GPU-class inference for query-time embedding (hurting load-test numbers and the "runs anywhere" Compose goal), forces every chat provider to be vision-capable, and complicates the 90% coverage gate and the quality benchmark. If pursued, it would be benchmarked against the captioning baseline on figure-dependent questions in the golden set.

---

## 8. Search Strategy (R8)

**Hybrid retrieval with Reciprocal Rank Fusion (RRF):**

1. **Dense:** embed the user query (after rewriting, see §9.2) and take top-20 chunks by cosine similarity.
2. **Sparse:** Postgres full-text search (`websearch_to_tsquery`) top-20, ranked by `ts_rank`.
3. **Fuse** the two lists with RRF (`k = 60`), deduplicate, keep **top-6** chunks as context.
4. Threshold guard: if the best fused candidate is below a minimum similarity, the assistant answers "I couldn't find this in the HP documents" instead of hallucinating.

Rationale: manuals are full of exact tokens (part numbers like "M08117-001", error codes, button names) where keyword search beats embeddings, while semantic search handles paraphrased questions ("my printer won't connect to wifi"). RRF is simple, tuning-free, and easy to test. A cross-encoder re-ranker is listed as a stretch goal, evaluated against the benchmark before adoption.

---

## 9. Chat & RAG Flow

### 9.1 Prompting

System prompt instructs the model to answer **only** from the provided context, cite sources as `[doc, p. X]`, and say so when the answer isn't in the documents. Context block = the top-6 chunks with their metadata.

### 9.2 Conversation history (R9)

- The last **10 messages** (5 turns) of the conversation are included in the prompt verbatim.
- **Query rewriting:** before retrieval, a lightweight LLM call condenses the history + new question into a standalone search query (so "how do I clean it?" retrieves printhead-cleaning chunks after a printer discussion). Skipped on the first turn.

### 9.3 Provider abstraction (R4)

```python
class ChatProvider(Protocol):
    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs
    ) -> AsyncIterator[str]: ...
```

Implementations: `AnthropicProvider`, `OpenAIProvider`, `OllamaProvider`, and `ScriptedProvider` — a genuine implementation of the protocol that streams pre-scripted responses with configurable latency. Per the constitution (§2), it carries no fake/mock naming because it honors the full interface and real streaming behavior; it serves the fast test suite and load-test scenario (a) in §12. A factory reads `LLM_PROVIDER` + `LLM_MODEL` env vars.

---

## 10. API Design (FastAPI)

| Method & path | Purpose |
|---|---|
| `POST /api/conversations` | Create conversation → `{id}` |
| `GET /api/conversations` | List conversations (id, title, updated_at) |
| `GET /api/conversations/{id}` | Full message history incl. sources |
| `DELETE /api/conversations/{id}` | Delete conversation |
| `POST /api/conversations/{id}/messages` | Send user message → **SSE stream** of tokens, final event carries sources + message ids |
| `GET /api/health` | Liveness (DB ping, provider configured) |
| `GET /api/documents` | Indexed documents + chunk counts (transparency/debug) |

**SSE contract:** the message stream emits named events — `token` (text delta), `done` (terminal: sources, user/assistant message ids, latency), and `error` (terminal: emitted if the provider fails mid-stream; the partial assistant message is persisted with `status='error'` so history stays truthful, and the client renders a retry affordance). Exactly one terminal event per stream; the fast suite tests all three event types at the framing level.

**User scoping:** all conversation endpoints are scoped by a client-generated UUID sent as the `X-User-Id` header (stored in the frontend's localStorage). No authentication — this is isolation, not security, per the non-goals.

Conventions: Pydantic response models, structured error envelope, structlog logfmt logging with request-ID middleware, CORS restricted to the frontend origin. Exception handling follows the constitution (§2): narrow, specific `try/except` at the exact guarded operation; unforeseen errors propagate to a single top-level handler that logs and returns a 500 — never silently swallowed.

---

## 11. Testing Strategy (R3)

Per the constitution (§2): development is test-driven, tests are the behavior specification, and real collaborators are preferred. Two suites:

- **Fast suite (unit)** — self-contained, no external resources, runs in seconds. Real collaborators throughout: the real chunker on real extracted-text fixtures, real RRF fusion math, real query rewriting and prompt assembly, real SSE framing, real provider factory. Where a boundary would require an external resource, the double honors the real interface: API routes run against `ScriptedProvider` (a genuine `ChatProvider`), and the embedding model is replaced with a `create_autospec`-based mock of the embedder interface — never an unspecced mock.
- **Slow suite (integration)** — simulates the actual application as closely as possible: repositories against a real Postgres + pgvector instance, ingestion on the real PDFs, and the full chat flow end-to-end inside Compose with the local model. Marked `slow`; run before every delivery and in CI.
- **Coverage:** `pytest --cov=app --cov-fail-under=90` gated on the fast suite (the "unit tests" of R3), with combined fast+slow coverage also reported. Logic is kept out of I/O modules (thin routers, thin repositories) so the fast suite clears the gate on real behavior rather than on mocked ceremony. Report committed as artifact/README badge.
- **CI:** GitHub Actions on every push/PR — Black check, ruff, pyrefly, fast suite with the coverage gate, and commitlint enforcing the §2 commit-type allowlist (no `chore`). The slow suite runs on PRs to `main`.

---

## 12. Load Testing (R12)

- **Tool:** Locust, containerized (`docker compose --profile loadtest up`).
- **Scenarios:** (a) chat flow with `ScriptedProvider` (fixed-latency scripted streaming) — measures API + retrieval + DB scalability independent of LLM throughput; (b) chat flow with the real provider — measures realistic end-to-end throughput.
- **Method:** ramp users until p95 latency exceeds threshold (e.g. 2 s for non-LLM endpoints) or error rate > 1%; report sustained **requests/minute** at that point, plus latency percentiles, for each scenario.
- Deliverable: `loadtest/REPORT.md` with numbers, graphs, and the bottleneck analysis (expected: LLM generation dominates; retrieval scales to high RPM).

---

## 13. Response Quality Benchmark (R13)

- **Golden dataset:** ~30 curated Q&A pairs stored in `eval/golden.jsonl`, covering both documents — factual lookups (specs, part numbers), procedures (cartridge replacement, battery removal), **figure-dependent questions** (validates the captioning pipeline in §7.4), multi-turn follow-ups, and **negative cases** (questions the docs can't answer, expecting an honest refusal).
- **Metrics (RAGAS-style, LLM-as-judge with the configured provider):**
  - *Faithfulness* — is the answer supported by retrieved context?
  - *Answer relevancy* — does it address the question?
  - *Context precision/recall* — did retrieval surface the right chunks (golden set stores expected pages)?
  - *Refusal correctness* — negative cases answered with "not in the documents".
- **Runner:** `python -m eval.run` → scores table + per-question breakdown in `eval/REPORT.md`. Also used as the regression harness when tuning chunk size, top-k, or hybrid weights.
- **Reproducibility:** benchmark runs pin `temperature=0` (and fixed seeds where the provider supports them) so tuning comparisons are apples-to-apples rather than sampling noise.

---

## 14. Docker Compose (R11)

Services:

- `db` — postgres:16 with pgvector; volume-backed; healthcheck.
- `ingest` — one-shot job (backend image, `python -m app.ingest`); runs after `db` healthy; applies Alembic migrations, verifies pinned document checksums, then indexes; idempotent.
- `api` — FastAPI (uvicorn); depends on successful ingest; env-configured provider.
- `frontend` — Next.js production build behind its own container.
- `ollama` — **profile `local`**; pulls the model on first start; only needed when `LLM_PROVIDER=ollama`.
- `locust` — **profile `loadtest`**.

Usage:

```bash
cp .env.example .env            # set LLM_PROVIDER + API key (or use ollama)
docker compose up --build       # cloud provider
docker compose --profile local up --build   # fully local, no API keys
```

### Configuration (`.env.example`)

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `anthropic` \| `openai` \| `ollama` |
| `LLM_MODEL` | `qwen3.5:4b` | Generation model for the selected provider |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | Only required for the matching cloud provider |
| `OLLAMA_URL` | `http://ollama:11434` | Local provider endpoint |
| `EMBEDDING_MODEL` | `microsoft/harrier-oss-v1-270m` | Fixed; changing it requires re-ingestion |
| `CHUNK_TOKENS` / `CHUNK_OVERLAP` | `450` / `80` | Chunking strategy (§7.2), tunable via benchmark |
| `RETRIEVAL_CANDIDATES` / `TOP_K` | `20` / `6` | Per-retriever candidates and fused context size (§8) |
| `REFUSAL_THRESHOLD` | tuned in M5 | Minimum fused score before answering |
| `DATABASE_URL` | compose-internal | asyncpg DSN |
| `LOG_LEVEL` | `info` | structlog level |

This table is the contract between Compose, the config module (Pydantic settings), and the tests.

---

## 15. Repository Layout

```
/
├── backend/
│   ├── src/
│   │   └── app/
│   │       ├── main.py, config.py, db.py
│   │       ├── ingest/        # parsing, chunking, embedding, figure captioning
│   │       ├── rag/           # retrieval, fusion, prompts, query rewrite
│   │       ├── providers/     # anthropic.py, openai.py, ollama.py, scripted.py
│   │       ├── api/           # routers, schemas, sse
│   │       └── repositories/  # conversations, messages, chunks
│   ├── tests/
│   ├── migrations/            # Alembic (schema + pgvector extension)
│   ├── pyproject.toml         # src layout; Black, ruff, pytest config
│   └── uv.lock
├── frontend/              # Next.js app
├── docs/                  # the two HP PDFs + checksums.txt (pinned SHA-256s)
├── eval/                  # golden.jsonl, run.py, REPORT.md
├── loadtest/              # locustfile.py, REPORT.md
├── .github/workflows/     # CI: lint, types, fast suite + coverage, commitlint
├── docker-compose.yml
├── .env.example
├── SPEC.md                # this file
└── README.md              # setup, decisions summary, results
```

The backend uses a **src layout** managed with uv: `uv sync` installs `app` as a proper package alongside its dependencies, so tests import the installed package (no `PYTHONPATH` hacks or accidental imports of the working tree), and the Docker build is a straightforward `uv sync --frozen`.

---

## 16. Milestones

Each milestone has an observable exit criterion; the box is checked in the same
commit that satisfies it. In-progress work is visible as red tests (TDD).

- [x] **1. Skeleton & infra** — fetch script + checksum pinning; Compose with db/api/frontend placeholders; Alembic baseline migration; health endpoint; CI pipeline (lint, pyrefly, fast suite, commitlint).
  *Exit: quality gates green; schema verified against real Postgres.*
  *Evidence: 13 fast tests @ 97.8% coverage; migration applied + reversed against pg16/pgvector; slow-suite health test green; Black/ruff/pyrefly clean; `./scripts/fetch_docs.sh` run against verified HP URLs (checksums pinned in `docs/checksums.txt`); `docker compose up --build` verified locally — db healthy, ingest verified both documents and exited 0, `GET /api/health` returned `{"status":"ok"}`, frontend placeholder served 200.*
- [ ] **2. Ingestion** — pymupdf4llm parsing, chunking, figure captioning, embeddings, pgvector writes; unit tests.
  *Exit: `ingest` completes in Compose against the real PDFs; chunks with embeddings + tsv queryable in Postgres; fast gate green.*
- [ ] **3. Retrieval & chat** — hybrid search, provider layer, SSE endpoint, history persistence; unit tests to ≥90%.
  *Exit: a curl'd SSE chat answers a doc question with citations, persists history, and survives a mid-stream provider failure with a terminal `error` event.*
- [ ] **4. Frontend** — chat UI, streaming, conversation sidebar, citations.
  *Exit: full flow in the browser — new conversation, streamed answer with sources, history restored on reload via `X-User-Id`.*
- [ ] **5. Evaluation** — golden dataset, benchmark runner, tune chunking/top-k.
  *Exit: `eval/REPORT.md` committed with per-provider metrics and tuning decisions recorded; re-ranker question (§18) resolved.*
- [ ] **6. Load tests & polish** — Locust runs, reports, README, final review.
  *Exit: `loadtest/REPORT.md` committed with sustained req/min for both scenarios; §3 table reads Done on every row.*

---

## 17. Risks & Mitigations

- **PDF extraction quality** (tables, multi-column layouts) → PyMuPDF + cleaning heuristics; verify worst pages manually; benchmark catches retrieval gaps.
- **Local model quality** (4B model weaker at grounding than cloud models) → strict prompt + refusal threshold; benchmark reports per-provider scores honestly.
- **90% coverage on async/streaming code** → design for testability (thin routers, injectable providers/embedders), `ScriptedProvider` honoring the real streaming interface, SSE unit-tested at the framing level.
- **Embedding model download size in Docker** → bake model weights into the backend image at build time for offline, reproducible startup.

---

## 18. Open Questions

- Re-ranker (cross-encoder) worth the latency? Decide via benchmark in Milestone 5.

**Resolved** (recorded in the relevant sections): conversations are scoped by a client-generated UUID sent as `X-User-Id` (§6, §10); minimal GitHub Actions CI is in scope (§11, Milestone 1).
