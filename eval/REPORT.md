# Retrieval Eval Report

Dense-retrieval quality on the golden set (`retrieval.jsonl`, 24 questions),
per the retrieval eval described in SPEC.md. Run with
`uv run --project backend python -m eval.retrieval` against a fully ingested
database.

## Baseline and candidates

| Model | Dim | recall@6 | recall@20 | MRR | Verdict |
|---|---|---|---|---|---|
| microsoft/harrier-oss-v1-270m | 640 | 0.958 | 0.958 | 0.826 | **kept** |
| intfloat/e5-small-v2 | 384 | 0.917 | 0.958 | 0.731 | rejected |

Notes (2026-07-17):

- Harrier: 23/24 questions hit within the top 6 chunks; 18 hit at rank 1.
- The one shared miss — "How do I add more RAM to this machine?" — is a
  vocabulary gap: the OMEN guide only says "memory module", and dense
  retrieval doesn't bridge the paraphrase within the top 20. Kept in the set
  as an honest hard case; hybrid FTS+RRF retrieval (Milestone 3) is the
  intended mitigation.
- e5-small-v2 was trialed for its size (~130MB vs ~1GB; ~20x faster CPU
  embedding) via an in-memory index re-chunked with e5's tokenizer and the
  same golden set. It lost measurably — recall@6 −0.041, MRR −0.095 (the wifi
  card question fell to rank 8, paper jam to rank 6) — and 9 chunks exceeded
  its 512-token input limit, which would be silently truncated. Not worth the
  quality trade now that the HF cache volume removes the repeated-download
  pain of the larger model.
- The trial surfaced a latent chunking issue independent of model choice:
  blocks with no sentence boundaries (large markdown tables) can produce
  chunks far above the ~450-token target — the worst was 4,414 tokens.
  Harmless for harrier's 32k context but bad for retrieval precision;
  tracked as a follow-up chunker fix (hard token-split fallback), to be
  re-evaluated here when done.

## Chunker: hard token-window fallback

Blocks with no sentence boundary (large markdown tables in the HP manuals)
were passing `_split_oversized` as a single unit far above the ~450-token
target (worst observed: 4,414 tokens with the e5 tokenizer). Added a hard
word-window fallback in `_split_by_word_window` for units still over
`chunk_tokens` after sentence splitting. Re-ingested and re-ran the eval:

| Model | Dim | recall@6 | recall@20 | MRR | max chunk tokens |
|---|---|---|---|---|---|
| microsoft/harrier-oss-v1-270m | 640 | 0.958 | 0.958 | 0.833 | 450 |

Notes (2026-07-17):

- Max chunk size across all 522 ingested chunks is now 450 tokens (down from
  the 4,414-token outlier); no chunk exceeds `chunk_tokens`.
- recall@6/@20 unchanged; MRR improved slightly (0.826 → 0.833). The same
  "How do I add more RAM to this machine?" miss remains — expected, since
  it's a vocabulary gap, not a chunking artifact.

## Golden dataset (`golden.jsonl`)

37 curated Q&A pairs across both manuals, seeded from `retrieval.jsonl`'s 24
factual/procedure questions plus new cases added for Milestone 5: 5
figure-dependent questions grounded in real indexed `figure_caption` chunks
(scanner callouts p. 8, SSD/RAM/keyboard/WLAN diagrams in the OMEN guide), 4
multi-turn follow-ups that reuse an earlier question's page range but require
resolving a pronoun/reference from the prior turn, and 4 negative
(unanswerable) questions from unrelated domains (car tire pressure, router
admin passwords, Thunderbolt 5 support, HP's return policy).

## Refusal threshold tuning (Milestone 5)

`REFUSAL_THRESHOLD` gates `HybridRetriever.retrieve()`: when the best fused
candidate scores below it, the system refuses instead of answering (§8).
Tuning it required understanding what the fused score actually measures.

**RRF fused scores don't discriminate relevant from irrelevant queries.**
Probed the top fused score for every golden question (`candidates=20`,
`k=60`): every single question — the 4 unanswerable negative cases included
— landed at either `1/61 ≈ 0.0164` (top-ranked by only one retriever) or
`2/61 ≈ 0.0328` (top-ranked by both). Reciprocal-rank fusion is blind to
absolute relevance by design — dense search always returns its 20
closest chunks by cosine distance no matter how unrelated the query, so
"top of the list" carries no signal about whether the list is any good. No
scalar cutoff on the fused score can separate real matches from near-misses.

**Raw dense cosine similarity doesn't either, cleanly.** Compared top-1
cosine similarity (pre-fusion) for negative vs. positive questions:
negatives scored 0.41–0.66, positives scored 0.50–0.70 — heavily
overlapping (e.g. `neg-return-policy` at 0.66 scores higher than 30 of the
33 answerable questions). harrier's embedding space is too compressed in
this domain for a global similarity threshold to reject the negative cases
without also rejecting legitimate low-signal questions like `f-add-ram` — a
worse trade, since a false refusal on a real question is worse than an
occasional unrefused negative.

**The actual gap was in the benchmark, not the system.** Inspecting the
first run's 3 refusal "misses" showed the model had already correctly
declined 2 of them in prose ("I'm unable to help with that question... "
/ "do not contain any information about Thunderbolt 5 support") — the
system prompt's refusal instruction (§9.1) was working; `eval/refusal.py`'s
phrase list just didn't recognize that phrasing. Broadened it
(`unable to help with that`, `do not contain`, `not mentioned in the
available context`) and re-ran: refusal accuracy went from 0.919 to 0.973
(34/37 → 36/37) with no threshold change at all. The one remaining case,
`neg-return-policy`, is a defensible partial answer — the OMEN guide does
contain a narrow EULA-rejection refund clause, and the model cited it while
explicitly noting the ENVY guide has no general return policy — not a
hallucination.

**Decision: keep `REFUSAL_THRESHOLD=0.0`.** Neither candidate signal
(fused RRF score or raw cosine similarity) safely separates the golden
set's negative cases from its hardest positive ones without costing real
recall, and the system prompt's own refusal instruction already covers the
negative cases correctly once measured properly. Revisit only if a future
embedding model produces a less compressed similarity distribution for this
domain.

## Re-ranker experiment (§18 open question, resolved)

Spiked a cross-encoder re-ranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`,
`eval/rerank_experiment.py`) on top of the RRF-fused top-20, re-scoring and
re-truncating to top-6, against the 33 answerable golden questions:

| | recall@6 | MRR | context precision |
|---|---|---|---|
| baseline (RRF top-6) | 0.939 | 0.791 | 0.731 |
| + cross-encoder re-rank | 0.939 | 0.785 | 0.763 |

Recall@6 is unchanged — the re-ranker can only reorder RRF's top-20, and
both misses (`f-add-ram`, `mt-wifi-then-still-fails`) were absent from that
pool to begin with, so no re-ranking recovers them. Context precision
improves modestly (+0.032, pulling a few buried-but-present hits toward the
top), but MRR gets slightly worse (−0.006, since a handful of correct
rank-1 hits get displaced to rank 2 by the cross-encoder's different
notion of relevance). Net effect is a wash on quality, for the cost of a
second model on CPU and a slower request path.

**Decision: not adopted.** No evidence in this golden set justifies the
added latency (§8's stretch goal stays a stretch goal). The spike script is
kept in `eval/rerank_experiment.py` as a reusable regression check if a
future embedding/chunking change meaningfully lowers recall@6 or context
precision — that's the scenario where a re-ranker's precision lift would
actually be worth its cost.

## Response Quality Benchmark

LLM-as-judge quality benchmark on the golden set (`golden.jsonl`), per the response-quality benchmark described in SPEC.md. Run with `uv run --project backend python -m eval.run` against a fully ingested database; temperature is pinned to 0 on every provider call for reproducibility.

### anthropic / claude-haiku-4-5 (37 cases)

| Metric | Score |
|---|---|
| refusal accuracy | 0.973 |
| context precision | 0.748 |
| context recall | 0.970 |
| faithfulness | 0.915 |
| answer relevancy | 0.938 |

| Category | n | refusal acc. | ctx precision | ctx recall | faithfulness | relevancy |
|---|---|---|---|---|---|---|
| factual | 10 | 1.000 | 0.742 | 1.000 | 0.915 | 0.983 |
| figure | 5 | 1.000 | 0.748 | 1.000 | 0.910 | 0.930 |
| multiturn | 4 | 1.000 | 0.717 | 1.000 | 0.900 | 0.970 |
| negative | 4 | 0.750 | — | — | — | — |
| procedure | 14 | 1.000 | 0.762 | 0.929 | 0.921 | 0.900 |

<details><summary>Per-question breakdown</summary>

| id | category | refusal ok | ctx precision | ctx recall | faithfulness | relevancy |
|---|---|---|---|---|---|---|
| f-wifi-connect | procedure | ✓ | 0.667 | 1.000 | 0.850 | 0.950 |
| f-paper-jam | procedure | ✓ | 0.833 | 1.000 | 0.950 | 0.980 |
| f-ink-level | factual | ✓ | 1.000 | 1.000 | 0.850 | 1.000 |
| f-swap-cartridges | procedure | ✓ | 1.000 | 1.000 | 0.950 | 0.980 |
| f-light-bar-amber | factual | ✓ | 1.000 | 1.000 | 0.950 | 1.000 |
| f-double-sided | factual | ✓ | 0.200 | 1.000 | 0.850 | 0.950 |
| f-envelopes | procedure | ✓ | 0.500 | 1.000 | 0.950 | 1.000 |
| f-scan-phone | procedure | ✓ | 0.417 | 1.000 | 0.950 | 0.950 |
| f-sleep-timer | factual | ✓ | 1.000 | 1.000 | 0.950 | 1.000 |
| f-factory-reset | procedure | ✓ | 1.000 | 1.000 | 0.750 | 0.950 |
| f-photo-quality | factual | ✓ | 0.500 | 1.000 | 0.950 | 0.950 |
| f-wont-print | procedure | ✓ | 0.750 | 1.000 | 0.950 | 0.980 |
| f-battery-removal | procedure | ✓ | 1.000 | 1.000 | 0.950 | 0.980 |
| f-add-ram | procedure | ✓ | 0.000 | 0.000 | 0.950 | 0.150 |
| f-replace-ssd | procedure | ✓ | 0.750 | 1.000 | 0.950 | 0.980 |
| f-open-bottom-cover | procedure | ✓ | 1.000 | 1.000 | 0.950 | 1.000 |
| f-replace-wifi-card | procedure | ✓ | 1.000 | 1.000 | 0.950 | 0.900 |
| f-replace-fan | procedure | ✓ | 1.000 | 1.000 | 0.950 | 0.850 |
| f-replace-display | procedure | ✓ | 0.750 | 1.000 | 0.850 | 0.950 |
| f-static-precautions | factual | ✓ | 0.887 | 1.000 | 0.950 | 0.980 |
| f-battery-part-number | factual | ✓ | 0.583 | 1.000 | 1.000 | 1.000 |
| f-wlan-part-number | factual | ✓ | 0.667 | 1.000 | 0.850 | 0.950 |
| f-bios-version | factual | ✓ | 0.833 | 1.000 | 0.850 | 1.000 |
| f-display-panel-only | factual | ✓ | 0.750 | 1.000 | 0.950 | 1.000 |
| fig-scanner-callouts | figure | ✓ | 1.000 | 1.000 | 0.950 | 0.950 |
| fig-ssd-install-diagram | figure | ✓ | 0.833 | 1.000 | 0.850 | 0.900 |
| fig-ram-install-diagram | figure | ✓ | 0.325 | 1.000 | 0.850 | 0.900 |
| fig-keyboard-removal-diagram | figure | ✓ | 1.000 | 1.000 | 0.950 | 1.000 |
| fig-wlan-diagram | figure | ✓ | 0.583 | 1.000 | 0.950 | 0.900 |
| mt-cartridges-then-ink-level | multiturn | ✓ | 1.000 | 1.000 | 0.850 | 0.950 |
| mt-battery-then-part-number | multiturn | ✓ | 0.700 | 1.000 | 0.850 | 1.000 |
| mt-wifi-then-still-fails | multiturn | ✓ | 0.167 | 1.000 | 0.950 | 0.950 |
| mt-bottom-cover-then-static | multiturn | ✓ | 1.000 | 1.000 | 0.950 | 0.980 |
| neg-tire-pressure | negative | ✓ | — | — | — | — |
| neg-router-password | negative | ✓ | — | — | — | — |
| neg-thunderbolt | negative | ✓ | — | — | — | — |
| neg-return-policy | negative | ✗ | — | — | — | — |

</details>
