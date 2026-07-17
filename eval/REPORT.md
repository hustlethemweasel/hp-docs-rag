# Retrieval Eval Report

Dense-retrieval quality on the golden set (`retrieval.jsonl`, 24 questions),
per the retrieval eval described in SPEC.md. Run with
`uv run --project backend python -m eval.retrieval` against a fully ingested
database.

## Baseline

| Model | Dim | recall@6 | recall@20 | MRR |
|---|---|---|---|---|
| microsoft/harrier-oss-v1-270m | 640 | 0.958 | 0.958 | 0.826 |

Notes (2026-07-17):

- 23/24 questions hit within the top 6 chunks; 18 hit at rank 1.
- The one miss — "How do I add more RAM to this machine?" — is a vocabulary
  gap: the OMEN guide only says "memory module", and dense retrieval doesn't
  bridge the paraphrase within the top 20. Kept in the set as an honest hard
  case; hybrid FTS+RRF retrieval (Milestone 3) is the intended mitigation.
