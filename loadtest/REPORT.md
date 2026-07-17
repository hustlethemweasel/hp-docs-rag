# Load Test Report (R12)

**Tool:** Locust, containerized (`docker compose --profile loadtest up`), driving
`loadtest/locustfile.py` against a real running `api` instance backed by the
real, already-ingested Postgres database (522 chunks, both HP manuals).

**Flow under test:** the real browser flow — create a conversation, then send
a message and consume the SSE stream to its terminal event (`done`/`error`),
mixed with occasional `GET /api/conversations` (sidebar) and new-conversation
traffic (task weights 6:2:1). Two named metrics are recorded per chat message:
time-to-first-byte (`[ttfb]`, Locust's automatic per-request timer, which for
a streamed response measures time to the response headers) and full-answer
latency (`[full answer]`, manually timed end-to-end — the metric that matches
what a user actually waits for).

**Method (SPEC §12):** ramp concurrent users until p95 latency on the
non-LLM endpoints (conversation create/list) exceeds 2s, or error rate
exceeds 1%; report sustained requests/minute and latency percentiles at that
point, for both scenarios.

Both scenarios run the identical script; the only difference is how the
`api` instance under test is configured (`LLM_PROVIDER`).

---

## Scenario (a) — `LLM_PROVIDER=scripted`

Isolates API + retrieval + DB scalability from LLM throughput:
`ScriptedProvider` streams a fixed 36-token canned answer at ~33 tokens/s
(`_SCRIPTED_LATENCY = 0.03s`/token in `providers/factory.py`), so there's no
real network call or generation-time variance in this scenario at all.

### A load test caught a real bug: query embedding blocked the event loop

The first run (30 users, 2 min) was surprising: **p95 for `GET
/api/conversations [list]`** — a pure DB read with no LLM or embedding
involvement — **was 3000ms**, and `POST /api/conversations [create]` p95 was
2800ms, both already past the 2s threshold at a fairly modest 30 users, with
the whole system moving at only ~7.2 req/s.

The cause: [`HybridRetriever.retrieve`](../backend/src/app/rag/retrieval.py)
called `self.embedder.embed_query(query)` — a synchronous, CPU-bound
`sentence-transformers` call — directly inside an `async def`, on
uvicorn's single worker process. Every concurrent request, including ones
that never touch the embedder, shares that one process and its one event
loop; a synchronous CPU-bound call blocks it for everyone until it returns.
With 30 concurrent chat messages each triggering an embedding call (once for
query rewriting, once for retrieval), the whole API serialized behind CPU
inference.

**Fix** (TDD, [`test_retrieval.py`](../backend/tests/test_retrieval.py)):
offload the embedding call with `await asyncio.to_thread(...)` so it runs on
a worker thread instead of blocking the loop.

| 30 users, 2 min | Before fix | After fix |
|---|---|---|
| `list` p50 / p95 | 1200ms / 3000ms | **58ms** / 980ms |
| `create` p50 / p95 | 310ms / 2800ms | **130ms** / 15000ms* |
| Aggregated throughput | 7.25 req/s (435/min) | **9.86 req/s (591/min)** |
| Errors | 0 | 0 |

\* See below — fixing the event-loop stall didn't remove the ceiling, it
moved it: median latency and throughput both improved substantially (the
typical-case win is real and large), but tail latency on writes got *worse*.
More requests now execute concurrently instead of queueing behind a blocked
loop, and they collide on a second, previously-masked constraint.

### The real ceiling: the DB connection pool

Ramping further (10/20/40/60 users, 60s each, post-fix) locates it exactly:

| Users | `list` p95 | `create` p95 | Aggregated req/s | Errors |
|---|---|---|---|---|
| 10 | 26ms | 94ms | 4.10 (246/min) | 1/242 (transient, spawn burst) |
| 20 | 15ms | 120ms | 9.02 (**541/min**) | 0/533 |
| **40** | **2400ms** | **2500ms** | 13.33 (800/min) | 0/783 |
| 60 | 4500ms | 4700ms | 13.93 (835/min) | 1/821 (0.12%) |

Throughput plateaus between 40 and 60 users (13.3 → 13.9 req/s) while p95
keeps climbing — a classic saturation curve, not a slow linear degradation.
At 40–60 users the API logs `sqlalchemy...InterfaceError: connection is
closed` from `Database.from_url()`'s engine, which is created with no pool
overrides — SQLAlchemy's async default (`pool_size=5`, `max_overflow=10`,
~15 connections total). A chat message checks out a connection across
several sequential queries (history read, user-message insert, retrieval,
assistant-message insert, conversation touch), so in-flight chat requests
alone can exhaust the pool well before 60 users. Not fixed here — it's a
one-line `create_async_engine(url, pool_size=..., max_overflow=...)` change,
flagged as a follow-up rather than made under load-test time pressure.

**Sustained throughput within the 2s/1%-error threshold: ~541 requests/min**
(20 concurrent users). The system saturates at **~800–835 requests/min**
(40–60 concurrent users), past which p95 degrades sharply but the service
stays up (error rate never exceeds ~0.1%).

---

## Scenario (b) — real provider (`LLM_PROVIDER=anthropic`, claude-haiku-4-5)

Realistic end-to-end throughput. Kept intentionally modest (5 and 10
concurrent users, 45s each) — this hits the real Anthropic API for every
request (a query-rewrite call plus a full generation call per chat message),
and scaling it to the same concurrency as scenario (a) would mean deliberately
spending real API cost to re-confirm what's already the expected, unsurprising
result: LLM generation dominates.

| Users | `list`/`create` p95 (non-LLM) | Full-answer p95 | Aggregated req/s | Errors |
|---|---|---|---|---|
| 5 | 11ms / 49ms | 8900ms (max 14100ms) | 1.80 (108/min) | 0/78 |
| 10 | 47ms / 59ms | 8500ms (max 9200ms) | 3.47 (**208/min**) | 0/153 |

Confirms SPEC's expectation directly: the non-LLM endpoints stay well under
the 2s threshold even under this scenario's traffic — the entire
API/retrieval/DB path proved itself in scenario (a); it's not what limits
scenario (b). Full-answer latency (p95 ~8.5–8.9s) is set almost entirely by
Anthropic's real network + generation time (query rewrite + streamed answer,
two sequential model calls per message), not by anything this system
controls. Sustained throughput in the tested range: **~208 requests/min**
(~1.3 chat messages/s) at 10 concurrent users, with zero errors — no
threshold was actually crossed in this scenario; concurrency was capped by
cost, not by an observed ceiling.

---

## Bottleneck analysis vs. SPEC's expectation

SPEC §12 expected "LLM generation dominates [scenario b]; retrieval scales
well [scenario a]." Partially corrected by evidence:

- **Scenario (b): confirmed.** LLM generation (network + token streaming)
  is the dominant cost by roughly two orders of magnitude versus the API's
  own overhead (p95 8.5s vs. p95 47-59ms for non-LLM endpoints at the same
  concurrency).
- **Scenario (a): corrected.** "Retrieval scales well" was true only after
  fixing a real bug this load test surfaced — a synchronous embedding call
  blocking the single-process event loop, serializing *all* concurrent
  requests regardless of whether they touched the embedder. After the fix,
  retrieval/API does scale well up to ~20 concurrent users (~541 req/min,
  p95 well under 2s), but the ceiling above that is the **default
  SQLAlchemy async connection pool** (~15 connections), not retrieval math
  or embedding CPU cost. Both are addressable (thread offload shipped here;
  pool sizing flagged as a follow-up) but neither is "scales well"
  unconditionally, which is why this is a correction rather than a
  confirmation.

## Reproducing

```bash
# Scenario (a): point the api service at ScriptedProvider
# (set LLM_PROVIDER=scripted in .env, then)
docker compose up -d --build api
docker compose --profile loadtest run --rm --no-deps locust \
  -f /mnt/locust/locustfile.py --headless \
  --users 20 --spawn-rate 2 --run-time 3m \
  --csv /mnt/locust/results/scenario_a --host http://api:8000

# Scenario (b): restore the real provider (LLM_PROVIDER=anthropic, .env), then
docker compose up -d --build api
docker compose --profile loadtest run --rm --no-deps locust \
  -f /mnt/locust/locustfile.py --headless \
  --users 10 --spawn-rate 10 --run-time 45s \
  --csv /mnt/locust/results/scenario_b --host http://api:8000
```

`--no-deps` skips Compose's `ingest`/`db` dependency checks so `locust` and
`api` can be pointed at an already-ingested database without re-running
ingestion (ingest's figure-captioning factory doesn't recognize
`LLM_PROVIDER=scripted`, matching the same provider-factory gap as `openai`
— captioning is an ingestion-time concern the load test never exercises).
Raw CSVs (`loadtest/results/*.csv`) are gitignored, reproducible from the
commands above.
