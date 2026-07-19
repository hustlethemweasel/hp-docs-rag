# HP Docs RAG ChatBot — Technical Specification

**Status:** v1.0 — all six milestones done (§16)
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
| R1 | Frontend with GUI | Next.js (React) SPA — chat UI with history sidebar | Done — Next.js 16 App Router SPA: conversation sidebar (create/switch/delete), streamed chat with live tokens, citation chips, history restored on reload via `X-User-Id` (M4) |
| R2 | Backend in Python with FastAPI | FastAPI app, async, Pydantic v2 models | Done — health endpoint (M1), ingest job/repositories (M2), conversation CRUD + SSE chat routes (M3), CORS restricted to the frontend origin (M4), `RequestIDMiddleware` (generates/propagates `X-Request-ID`, binds it to structlog contextvars) + a structured `{"error": {code, message, request_id}}` envelope for both `HTTPException` and unhandled exceptions (M6) |
| R3 | Unit tests ≥90% coverage | pytest + pytest-cov, `--cov-fail-under=90` enforced | Done — gate enforced in CI and green since M1; 152 fast backend tests @ 93.4% coverage as of M6 (adds request-ID/error-envelope, scripted-provider-factory, event-loop-offload, connection-pool, and embedder-thread-safety tests); frontend adds 37 Vitest tests (TDD discipline on real logic, not a numeric coverage target — this requirement is backend-scoped); the response-quality benchmark (M5) is the automated answer-quality evidence referenced in §1's Goals |
| R4 | Cloud or local models | Provider abstraction: `anthropic` / `ollama`, chosen via env var | Done — `ChatProvider` protocol + `AnthropicProvider`/`OllamaProvider`/`ScriptedProvider`, factory reads `LLM_PROVIDER` (M3); `LLM_PROVIDER=scripted` selectable too, for load-test scenario (a) (M6). An `openai` option was carried as an unimplemented enum value from M2 and removed in the post-M6 polish pass — one cloud plus one local provider satisfies the requirement (§9.3) |
| R5 | Open-source vector DB | PostgreSQL 16 + pgvector extension | Done — HNSW schema populated with real embeddings from both PDFs and verified queryable via cosine-distance search (M2) |
| R6 | Only the attached documents | Ingestion pipeline reads exactly the two PDFs baked into the repo | Done — checksum-gated, idempotent, verified end-to-end in Compose against both real PDFs (M2) |
| R7 | Chunking strategy | Heading/structure-aware recursive chunking with overlap (§7.2) | Done — full ingest pipeline verified in Compose against both real PDFs; 522 chunks (419 text + 103 figure captions) with embeddings and tsv queryable in Postgres; revised from 515 by a M3 follow-up fix (hard word-window fallback for sentence-less blocks like large tables) — see `eval/REPORT.md` |
| R8 | Search strategy | Hybrid retrieval: dense (cosine) + sparse (Postgres FTS), fused with RRF (§8) | Done — `HybridRetriever` runs dense + sparse top-20, fuses with RRF (k=60), caps at top-6, refuses when retrieval comes back empty (M3; the configurable score threshold was removed after M5 tuning — §8) |
| R9 | Conversation with chat history | Rolling window of prior turns injected into the prompt | Done — last 10 messages windowed into the prompt; query rewriting condenses history + question before retrieval (M3) |
| R10 | Store chats/history in backend | `conversations` and `messages` tables in Postgres | Done — schema migrated (M1); `ConversationRepository`/`MessageRepository` persist every turn, incl. partial content + `status='error'` on a mid-stream provider failure (M3) |
| R11 | Docker Compose | `frontend`, `api`, `db`, optional `ollama` services + one-shot `ingest` job | Done — first boot (M1) and full real ingest run (M2) both verified locally; `frontend` a real multi-stage Next.js build, image verified standalone (M4); `local` profile (`ollama`) since M1, `loadtest` profile (`locust`) added M6, both verified with `docker compose --profile <name> up` |
| R12 | Load tests | Locust scenario; report requests/minute at latency thresholds (§12) | Done — `loadtest/locustfile.py` drives the real conversation-create + SSE chat flow against a live `api` instance; run for both scenarios in §12 against real ingested data, results and bottleneck analysis in `loadtest/REPORT.md` (M6). Scenario (a) caught and fixed two real bugs in sequence: synchronous query embedding blocking the single-process event loop (`asyncio.to_thread`), which — once fixed — exposed a PyTorch thread-safety race on the shared embedding model under genuine concurrency (`threading.Lock` in `Embedder`); the DB connection pool was also sized up (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`, `pool_pre_ping=True`). After all three fixes, sustained throughput within the 2s p95/1%-error threshold rose from ~541 to ~891 req/min (60 users, 0 errors), roughly 3x the safe-concurrency ceiling. Scenario (b) confirmed LLM generation dominates (p95 ~8.5s) with non-LLM endpoints unaffected, ~208 req/min at 10 users, 0 errors |
| R13 | Benchmark response quality | Golden Q&A set + RAGAS-style metrics with LLM-as-judge (§13) | Done — 37-question golden set (`eval/golden.jsonl`) across factual/procedure/figure/multi-turn/negative categories; `eval/run.py` scores faithfulness, answer relevancy, context precision/recall, and refusal correctness against the real HybridRetriever + AnthropicProvider, temperature pinned to 0; results in `eval/REPORT.md` (refusal accuracy 0.973, faithfulness 0.915, relevancy 0.938, context recall 0.970) |

---

## 4. Architecture

```
┌─────────────┐     HTTP/SSE      ┌──────────────────┐
│  Next.js    │ ────────────────▶ │  FastAPI backend │
│  SPA (web)  │ ◀──────────────── │                  │
└─────────────┘                   │  ┌────────────┐  │
                                  │  │ RAG service│  │
                                  │  │ Chat svc   │  │
                                  │  │ Providers  │──┼──▶ Anthropic API
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
- **Fixed embedding model, swappable chat model.** The vector index must not change when the chat provider changes. Embeddings are always produced by a local open-source model (`sentence-transformers`, `microsoft/harrier-oss-v1-270m`, 640-dim) running inside the API container on CPU. Only the *generation* step is provider-swappable. This avoids re-indexing and dimension mismatches when switching between cloud and local LLMs. Replacing the embedding model itself (e.g. with a smaller one for faster CPU inference) is allowed only with before/after evidence from the retrieval eval (§13.1) and a full re-ingest.
- **Local serving via Ollama, not vLLM.** The local provider optimizes for the "runs anywhere via `docker compose up`" goal, not for local-inference throughput. Ollama runs a quantized model on a plain laptop CPU or Apple Silicon (Metal) with one `ollama pull`, and its `images` API keeps the figure-captioning VLM path (§7.4) trivial. vLLM (or TGI/SGLang) would win decisively on concurrent throughput via continuous batching — but that advantage targets a load profile this project deliberately doesn't serve (load-test scenario (a) in §12 isolates infra scaling from LLM cost with `ScriptedProvider`; nothing requires serving many concurrent users through the local LLM), and it effectively requires a CUDA GPU, which contradicts the runs-anywhere goal and has no first-class Apple Silicon support. If this were deployed to GPU hardware fronting real concurrency, vLLM would be the right call — and it's a drop-in via the provider abstraction (§9.3): vLLM ships an OpenAI-compatible server, so `VLLMProvider` is a thin httpx client added with the same three-step change as any provider.
- **SSE streaming** for token-by-token responses in the chat UI.

---

## 5. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind | Chat UI, conversation sidebar, source-citation display |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, Alembic (migrations), structlog (logfmt) | Black code style, ruff lint, pyrefly type checking |
| Embeddings | sentence-transformers `microsoft/harrier-oss-v1-270m` | 270M, 640-dim, top MTEB score for its size; CPU-friendly, fixed across providers |
| Generation | Provider layer: Anthropic API, Ollama (`qwen3.5:4b` default — 3.4 GB, vision-capable) | Selected via `LLM_PROVIDER` env var; Ollama over vLLM for local serving (§4 rationale) |
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
- **Page numbers are the document's own printed numbers, not physical PDF position.** Both HP manuals have front matter (cover, notices, table of contents) before their own "page 1", so pymupdf4llm's physical page index is offset from what a reader sees printed on the page — and would type into a citation (a real bug: citations read "p. 65" for content the manual itself prints as "p. 59"). The offset is constant across a document's body (confirmed against both manuals, including their appendices/index); `parse_pdf` detects it once per document via majority vote across pages whose printed number can be read from the page's own trailing text, then applies it uniformly — including to figure captions, extracted separately via raw PyMuPDF and corrected the same way. Falls back to physical indexing (no correction) when too few pages yield a confident reading. The golden datasets' expected pages were originally curated against physical PDF position (matching the pre-fix convention) and were shifted to match; recall@6 unaffected (0.958 after, matching the historical baseline) since only page *labels* changed, not retrieval itself.

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
4. Refusal guard: if fusion produces no candidates at all, the assistant answers "I couldn't find this in the HP documents" instead of hallucinating. (This was originally a configurable `REFUSAL_THRESHOLD` on the fused score; the M5 tuning writeup in `eval/REPORT.md` found neither the RRF score nor raw cosine similarity separates negative from positive cases in this embedding space without costing real recall, so the knob sat pinned at 0 — where the comparison can never fire on a non-empty RRF result — and was removed as dead code in the post-M6 polish pass.)

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
    def stream_chat(
        self, messages: list[ChatMessage], **kwargs
    ) -> AsyncIterator[str]: ...
```

(`def`, not `async def` — implementations are async-generator functions, whose call signature is `Callable[..., AsyncGenerator[str, None]]`; declaring the protocol method `async def` would type-check as returning a coroutine instead and reject every real implementation.)

Implementations: `AnthropicProvider`, `OllamaProvider`, and `ScriptedProvider` — a genuine implementation of the protocol that streams pre-scripted responses with configurable latency. Per the constitution (§2), it carries no fake/mock naming because it honors the full interface and real streaming behavior; it serves the fast test suite and load-test scenario (a) in §12. A factory reads `LLM_PROVIDER` + `LLM_MODEL` env vars. An `openai` slot (enum value, API-key setting, `NotImplementedError` branches in both the chat and captioning factories) rode along unimplemented from M2 through M6 and was removed in the post-M6 polish pass: R4 asks for cloud *or* local generation, which Anthropic + Ollama already covers, and an advertised-but-unimplemented option is config surface without behavior. Adding a new provider back is the same three-step change in either factory: implement the class, extend the `Literal`, wire the branch.

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
| `GET /api/documents` | Indexed documents + chunk counts (transparency/debug) — not yet implemented, not required by the M3 exit criterion |

**SSE contract:** the message stream emits named events — `token` (text delta), `done` (terminal: sources, user/assistant message ids, latency), and `error` (terminal: emitted if the provider fails mid-stream; the partial assistant message is persisted with `status='error'` so history stays truthful, and the client renders a retry affordance). Exactly one terminal event per stream; the fast suite tests all three event types at the framing level.

**User scoping:** all conversation endpoints are scoped by a client-generated UUID sent as the `X-User-Id` header (stored in the frontend's localStorage). No authentication — this is isolation, not security, per the non-goals.

Conventions: Pydantic response models, structured error envelope, structlog logfmt logging with request-ID middleware, CORS restricted to the frontend origin. Exception handling follows the constitution (§2): narrow, specific `try/except` at the exact guarded operation; unforeseen errors propagate to a single top-level handler that logs and returns a 500 — never silently swallowed. As of M4, routes use Pydantic response models and FastAPI's default error responses (404/422), and CORS is restricted to the configured frontend origin; the structured error envelope and request-ID middleware are remaining polish deferred to M6.

---

## 11. Testing Strategy (R3)

Per the constitution (§2): development is test-driven, tests are the behavior specification, and real collaborators are preferred. Two suites:

- **Fast suite (unit)** — self-contained, no external resources, runs in seconds. Real collaborators throughout: the real chunker on real extracted-text fixtures, real RRF fusion math, real query rewriting and prompt assembly, real SSE framing, real provider factory. Where a boundary would require an external resource, the double honors the real interface: API routes run against `ScriptedProvider` (a genuine `ChatProvider`), and the embedding model is replaced with a `create_autospec`-based mock of the embedder interface — never an unspecced mock.
- **Slow suite (integration)** — simulates the actual application as closely as possible: repositories against a real Postgres + pgvector instance, ingestion on the real PDFs, and the full chat flow end-to-end inside Compose with the local model. Marked `slow`; run before every delivery and in CI.
- **Coverage:** `pytest --cov=app --cov-fail-under=90` gated on the fast suite (the "unit tests" of R3), with combined fast+slow coverage also reported. Logic is kept out of I/O modules (thin routers, thin repositories) so the fast suite clears the gate on real behavior rather than on mocked ceremony. Report committed as artifact/README badge.
- **CI:** GitHub Actions on every push/PR — Black check, ruff, pyrefly, fast suite with the coverage gate, and commitlint enforcing the §2 commit-type allowlist (no `chore`). The slow suite runs on PRs to `main`.
- **Frontend:** Vitest + React Testing Library, TDD'd for real logic (the SSE stream parser, the API client, data-fetching hooks) and lighter render/interaction tests for components with non-trivial behavior. No numeric coverage gate — R3 is a backend requirement — but `npm run test` runs in CI alongside Prettier, ESLint, and `tsc --noEmit`.

---

## 12. Load Testing (R12)

- **Tool:** Locust, containerized (`docker compose --profile loadtest up`).
- **Scenarios:** (a) chat flow with `ScriptedProvider` (fixed-latency scripted streaming, selected with `LLM_PROVIDER=scripted` on the `api` service under test) — measures API + retrieval + DB scalability independent of LLM throughput; (b) chat flow with the real provider — measures realistic end-to-end throughput. Both scenarios run the same `loadtest/locustfile.py` against a differently-configured `api` instance.
- **Method:** ramp users until p95 latency exceeds threshold (e.g. 2 s for non-LLM endpoints) or error rate > 1%; report sustained **requests/minute** at that point, plus latency percentiles, for each scenario.
- Deliverable: `loadtest/REPORT.md` with numbers, graphs, and the bottleneck analysis (expected: LLM generation dominates; retrieval scales to high RPM).

---

## 13. Response Quality Benchmark (R13)

- **Golden dataset:** ~30 curated Q&A pairs stored in `eval/golden.jsonl`, covering both documents — factual lookups (specs, part numbers), procedures (cartridge replacement, battery removal), **figure-dependent questions** (validates the captioning pipeline in §7.4), multi-turn follow-ups, and **negative cases** (questions the docs can't answer, expecting an honest refusal).
- **Metrics (RAGAS-style, LLM-as-judge pinned to `claude-haiku-4-5` regardless of `LLM_PROVIDER`, so per-provider scores share one grader and are comparable — a judge that swaps with the generator would score each provider on its own curve, and a 4B local judge is not a credible grader; requires `ANTHROPIC_API_KEY` even for local-provider runs):**
  - *Faithfulness* — is the answer supported by retrieved context?
  - *Answer relevancy* — does it address the question?
  - *Context precision/recall* — did retrieval surface the right chunks (golden set stores expected pages)?
  - *Refusal correctness* — negative cases answered with "not in the documents".
- **Runner:** `python -m eval.run` → scores table + per-question breakdown in `eval/REPORT.md`. Also used as the regression harness when tuning chunk size, top-k, or hybrid weights.
- **Reproducibility:** benchmark runs pin `temperature=0` (and fixed seeds where the provider supports them) so tuning comparisons are apples-to-apples rather than sampling noise. (The original harness passed the generation provider to the judge — fine while only the Anthropic provider had been benchmarked, since haiku graded haiku either way, but self-judging would have invalidated the cross-provider comparison; the judge was pinned before the first Ollama run.)

### 13.1 Retrieval eval (pulled forward from Milestone 5)

A retrieval-only subset of the benchmark, needing no LLM judge, built early
because it gates infrastructure decisions that are expensive to revisit later —
above all **changing the embedding model**. No model swap (nor chunking change)
ships without before/after numbers from this eval.

- **Golden set:** `eval/golden.jsonl` (the single source of truth shared
  with §13's full benchmark), filtered to the retrieval-measurable cases —
  answerable (not `expect_refusal`) and single-turn (no `history`, since
  this eval runs no query rewriting). Question wording is written from the
  user's perspective, not copied from the manuals, so lexical overlap
  doesn't inflate scores. (Historically a separate `eval/retrieval.jsonl`
  seeded the full golden dataset; it was merged back once the duplication
  proved a drift risk — the two files had to be page-shifted in lockstep —
  and a coverage gap: the figure-dependent questions never reached the
  retrieval eval.)
- **Metrics:** recall@k (is an expected page in the top-k chunks?) and MRR,
  reported both for dense retrieval alone (embeddings — the retriever a
  model swap actually changes, and the gate for any swap) and for the full
  hybrid pipeline (dense + FTS fused with RRF, via the real
  `HybridRetriever`) — what production actually retrieves, and the direct
  evidence for §8's claim that keyword search complements embeddings on
  exact-token queries.
- **Runner:** `python -m eval.retrieval` against an ingested database →
  per-question hits + aggregate table; results recorded in `eval/REPORT.md`
  when used to justify a change.

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
| `LLM_PROVIDER` | `ollama` | `anthropic` \| `ollama` \| `scripted` (fixed-latency `ScriptedProvider`, no live LLM — load-test scenario (a) in §12, never the Compose default) |
| `LLM_MODEL` | `qwen3.5:4b` | Generation model for the selected provider |
| `ANTHROPIC_API_KEY` | — | Only required for `LLM_PROVIDER=anthropic` |
| `OLLAMA_URL` | `http://ollama:11434` | Local provider endpoint |
| `EMBEDDING_MODEL` | `microsoft/harrier-oss-v1-270m` | Fixed; changing it requires re-ingestion |
| `CHUNK_TOKENS` / `CHUNK_OVERLAP` | `450` / `80` | Chunking strategy (§7.2), tunable via benchmark |
| `RETRIEVAL_CANDIDATES` / `TOP_K` | `20` / `6` | Per-retriever candidates and fused context size (§8) |
| `DATABASE_URL` | compose-internal | asyncpg DSN |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `20` / `20` | SQLAlchemy async engine connection pool; raised from the library defaults (5/10) after `loadtest/REPORT.md` found the default pool saturating around 40-60 concurrent chat requests. The engine also sets `pool_pre_ping=True` (not configurable — always on) so a connection silently closed underneath the pool (e.g. by a cancelled/disconnected request) is discarded and replaced instead of surfacing `InterfaceError: connection is closed` to the next caller |
| `LOG_LEVEL` | `info` | structlog level |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS-allowed origin for the browser SPA |

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
│   │       ├── rag/           # retrieval, fusion, prompts, query rewrite, chat orchestration
│   │       ├── providers/     # anthropic.py, ollama.py, scripted.py
│   │       ├── api/           # routers, schemas, sse
│   │       └── repositories/  # conversations, messages, chunks
│   ├── tests/
│   ├── migrations/            # Alembic (schema + pgvector extension)
│   ├── pyproject.toml         # src layout; Black, ruff, pytest config
│   └── uv.lock
├── frontend/              # Next.js app
├── docs/                  # the two HP PDFs + checksums.txt (pinned SHA-256s)
├── eval/                  # metrics.py, retrieval.py, golden.{py,jsonl},
│                          # judge.py, refusal.py, report.py, run.py (all live)
├── loadtest/              # locustfile.py, REPORT.md
├── .github/workflows/     # CI: lint, types, fast suite + coverage, commitlint
├── docker-compose.yml
├── mise.toml              # task runner: fmt/lint/typecheck/test/test:slow/check/
│                          # eval/eval:quality
├── .env.example
├── SPEC.md                # this file
└── README.md              # setup, decisions summary, results
```

The backend uses a **src layout** managed with uv: `uv sync` installs `app` as a proper package alongside its dependencies, so tests import the installed package (no `PYTHONPATH` hacks or accidental imports of the working tree), and the Docker build is a straightforward `uv sync --frozen`. [mise](https://mise.jdx.dev) wraps the recurring `uv run ...` commands (formatting, linting, type-checking, both test suites, the retrieval eval) as `mise run <task>` from the repo root — a convenience layer, not a new source of truth; the raw commands still work from `backend/`.

---

## 16. Milestones

Each milestone has an observable exit criterion; the box is checked in the same
commit that satisfies it. In-progress work is visible as red tests (TDD).

- [x] **1. Skeleton & infra** — fetch script + checksum pinning; Compose with db/api/frontend placeholders; Alembic baseline migration; health endpoint; CI pipeline (lint, pyrefly, fast suite, commitlint).
  *Exit: quality gates green; schema verified against real Postgres.*
  *Evidence: 13 fast tests @ 97.8% coverage; migration applied + reversed against pg16/pgvector; slow-suite health test green; Black/ruff/pyrefly clean; `./scripts/fetch_docs.sh` run against verified HP URLs (checksums pinned in `docs/checksums.txt`); `docker compose up --build` verified locally — db healthy, ingest verified both documents and exited 0, `GET /api/health` returned `{"status":"ok"}`, frontend placeholder served 200.*
- [x] **2. Ingestion** — pymupdf4llm parsing, chunking, figure captioning, embeddings, pgvector writes; unit tests.
  *Exit: `ingest` completes in Compose against the real PDFs; chunks with embeddings + tsv queryable in Postgres; fast gate green.*
  *Evidence: 46 fast tests @ 95.3% coverage; ingest ran in Compose end-to-end (exit 0, idempotent) writing 515 chunks — 412 text + 103 figure captions (deduped from 122 raw figures) — all with embeddings and tsv; FTS and cosine-distance queries return sensible chunks; captioning provider-selectable (anthropic/ollama), 103 figures in ~70s parallel via claude-haiku-4-5 (~$0.14/full re-ingest) vs ~22 min local qwen3.5:4b.*
- [x] **3. Retrieval & chat** — hybrid search, provider layer, SSE endpoint, history persistence; unit tests to ≥90%.
  *Exit: a curl'd SSE chat answers a doc question with citations, persists history, and survives a mid-stream provider failure with a terminal `error` event.*
  *Evidence: 106 fast tests @ 92.8% coverage; verified live against real ingested chunks and the real Anthropic provider — cited, multi-page-referenced answer streamed and persisted with sources/provider/model/latency; a pronoun-resolving follow-up correctly rewrote its search query from history; an unreachable-provider run emitted a terminal `error` event with the partial content persisted as `status='error'`. Also includes a follow-up chunker fix (hard word-window fallback for sentence-less blocks; R7, `eval/REPORT.md`).*
- [x] **4. Frontend** — chat UI, streaming, conversation sidebar, citations.
  *Exit: full flow in the browser — new conversation, streamed answer with sources, history restored on reload via `X-User-Id`.*
  *Evidence: Next.js 16 App Router SPA (TypeScript, Tailwind), 37 Vitest/RTL tests covering the SSE stream parser, API client, and every component/hook. Verified live in the browser against real ingested chunks and the real Anthropic provider: created a conversation, sent an HP-doc question, watched tokens stream in and citation chips render, reloaded via direct navigation to `/c/{id}` and saw full history restore, and confirmed a second conversation appears and is switchable/deletable in the sidebar. Manual verification caught and fixed two real bugs a unit test alone wouldn't have: CORS middleware added inside `lifespan()` crashed under a real ASGI server (Starlette locks its middleware stack on the first call, including the lifespan dispatch itself — fixed by wiring it in `create_app()`), and the sidebar never refreshed after a message completed, leaving a new conversation's title blank until reload (fixed with a shared `ConversationsContext`). CORS restricted to the configured frontend origin (R2). `frontend` Compose service rebuilt as a real multi-stage Next.js build (`output: "standalone"`), verified as a standalone container. `mise run frontend:check` (fmt/lint/typecheck/test) mirrors the backend gate and runs in CI alongside it.*
- [x] **5. Evaluation** — golden dataset, benchmark runner, tune chunking/top-k.
  *Exit: `eval/REPORT.md` committed with per-provider metrics and tuning decisions recorded; re-ranker question (§18) resolved.*
  *Evidence: 37-question golden set (`eval/golden.jsonl`) spanning factual, procedure, figure-dependent, multi-turn, and negative cases; `eval/run.py` runs the real HybridRetriever + AnthropicProvider end to end (rewrite → retrieve → generate → LLM-judge), temperature pinned to 0, results cached per-provider under `eval/results/` and rendered into `eval/REPORT.md` (refusal accuracy 0.973, context recall 0.970, context precision 0.748, faithfulness 0.915, answer relevancy 0.938 on claude-haiku-4-5). `REFUSAL_THRESHOLD` tuning investigated two candidate signals (RRF fused score, raw dense cosine similarity) and found neither safely separates negative from positive cases in this embedding space without costing real recall — kept at 0.0 (the setting itself was later removed as dead code, see §8); the actual gap was a too-narrow refusal-phrase list in the benchmark itself, fixed with evidence (refusal accuracy 0.919 → 0.973). Re-ranker question (§18) resolved: a cross-encoder spike (`eval/rerank_experiment.py`) showed a wash (recall@6 unchanged, MRR −0.006, context precision +0.032) — not adopted. 142 fast backend tests passing.*
- [x] **6. Load tests & polish** — Locust runs, reports, README, final review.
  *Exit: `loadtest/REPORT.md` committed with sustained req/min for both scenarios; §3 table reads Done on every row.*
  *Evidence: `RequestIDMiddleware` + structured error envelope closed R2. `loadtest/locustfile.py` drives the real conversation-create + SSE chat flow; a new `locust` service under the `loadtest` Compose profile runs it headless against a live `api` instance. `LLM_PROVIDER=scripted` made `ScriptedProvider` selectable on a running `api` so scenario (a) could isolate API/retrieval/DB scalability for real. Scenario (a) caught and fixed two real bugs in sequence: synchronous CPU-bound query embedding blocking uvicorn's single-process event loop, serializing unrelated concurrent requests (`asyncio.to_thread`, TDD interleaving test) — which, once fixed, exposed a PyTorch thread-safety race on the shared embedding model now called concurrently from multiple threads (`threading.Lock` in `Embedder`, TDD mutual-exclusion test). The DB connection pool was also sized up and given `pool_pre_ping=True` (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`, TDD). Full before/after evidence and ramps (10 through 80 users, at each stage) are in `loadtest/REPORT.md`. After all three fixes, scenario (a) sustains ~891 req/min within the 2s p95/1%-error threshold (60 users, zero errors) — up from ~541 req/min pre-fix, roughly 3x the safe-concurrency ceiling. Scenario (b) (real claude-haiku-4-5 provider, 5/10 users) confirmed LLM generation dominates (p95 ~8.5s) while non-LLM endpoints stay fast (p95 11–59ms), ~208 req/min sustained with zero errors. 152 fast backend tests @ 93.4% coverage. §3's requirements table reads Done on every row.*

---

## 17. Risks & Mitigations

- **PDF extraction quality** (tables, multi-column layouts) → PyMuPDF + cleaning heuristics; verify worst pages manually; benchmark catches retrieval gaps.
- **Local model quality** (4B model weaker at grounding than cloud models) → strict prompt + empty-retrieval refusal; benchmark reports per-provider scores honestly.
- **90% coverage on async/streaming code** → design for testability (thin routers, injectable providers/embedders), `ScriptedProvider` honoring the real streaming interface, SSE unit-tested at the framing level.
- **Embedding model download size in Docker** → a named `hf_cache` volume persists the Hugging Face cache across container rebuilds, so weights download once per machine (optionally authenticated via `HF_TOKEN` to avoid rate limits). Baking weights into the image was rejected: without a published registry image it re-downloads on every build anyway, and bloats the image.

---

## 18. Open Questions

None outstanding.

**Resolved** (recorded in the relevant sections): conversations are scoped by a client-generated UUID sent as `X-User-Id` (§6, §10); minimal GitHub Actions CI is in scope (§11, Milestone 1); re-ranker (cross-encoder) not worth the latency — a spike showed a wash on the golden set (recall@6 unchanged, MRR −0.006, context precision +0.032), see `eval/REPORT.md` (§8, Milestone 5). The spike's code was removed from the tree after the decision, per standard spike hygiene — the evidence outlives the experiment, the experiment doesn't ship. To rerun it (e.g. if a future embedding/chunking change meaningfully lowers recall@6), restore `eval/rerank_experiment.py` and `backend/tests/test_eval_rerank.py` from commit `f1b92a9`. Two more decisions from the post-M6 polish pass: the never-implemented `openai` provider option was removed (§9.3), and the `REFUSAL_THRESHOLD` knob was removed as dead code (§8).
