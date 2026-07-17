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
