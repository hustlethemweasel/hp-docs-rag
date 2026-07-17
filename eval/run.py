"""Response-quality benchmark runner (§13): golden Q&A set -> RAGAS-style
LLM-as-judge metrics, scored against the real production RAG path
(HybridRetriever + the configured ChatProvider).

Run from the repo root against a fully ingested database:

    uv run --project backend python -m eval.run

Environment: reads the same Settings as the API (DATABASE_URL, LLM_PROVIDER,
LLM_MODEL, EMBEDDING_MODEL, RETRIEVAL_CANDIDATES, TOP_K, REFUSAL_THRESHOLD).
Every provider call pins temperature=0 for reproducibility, matching §13's
tuning-harness requirement. Re-run once per provider (e.g. once with
LLM_PROVIDER=anthropic, once with LLM_PROVIDER=ollama) to build the
per-provider comparison in REPORT.md.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.ingest.embedding import load_embedder
from app.providers.base import ChatMessage
from app.providers.factory import build_provider
from app.rag.chat_service import REFUSAL_MESSAGE
from app.rag.prompting import build_system_prompt
from app.rag.retrieval import HybridRetriever
from app.rag.rewrite import rewrite_query
from app.repositories.chunks import ChunkRepository, RetrievedChunk
from eval.golden import GoldenCase, load_golden
from eval.judge import judge
from eval.metrics import context_precision, context_recall
from eval.refusal import is_refusal
from eval.report import CaseRecord, ProviderRun, save_run, update_report

TEMPERATURE = 0.0
logger = structlog.get_logger(__name__)


async def run_case(
    case: GoldenCase, *, retriever: HybridRetriever, provider
) -> CaseRecord:
    search_query = await rewrite_query(
        provider, case.history, case.question, temperature=TEMPERATURE
    )
    retrieved: list[RetrievedChunk] = await retriever.retrieve(search_query)

    if not retrieved:
        answer = REFUSAL_MESSAGE
    else:
        system_prompt = build_system_prompt(retrieved)
        messages = [*case.history, ChatMessage(role="user", content=case.question)]
        tokens = [
            token
            async for token in provider.stream_chat(
                messages, system=system_prompt, temperature=TEMPERATURE
            )
        ]
        answer = "".join(tokens)

    refused = is_refusal(answer)
    refusal_correct = refused == case.expect_refusal

    ctx_precision = ctx_recall = faithfulness = relevancy = None
    if not case.expect_refusal and case.document is not None:
        ctx_precision = context_precision(
            retrieved, document=case.document, pages=case.pages
        )
        ctx_recall = context_recall(retrieved, document=case.document, pages=case.pages)
        if retrieved and not refused:
            context_text = "\n\n".join(c.content for c in retrieved)
            score = await judge(
                provider,
                question=case.question,
                answer=answer,
                context=context_text,
                temperature=TEMPERATURE,
            )
            faithfulness = score.faithfulness
            relevancy = score.relevancy

    logger.info(
        "eval_case_scored",
        id=case.id,
        category=case.category,
        refused=refused,
        refusal_correct=refusal_correct,
        context_precision=ctx_precision,
        context_recall=ctx_recall,
        faithfulness=faithfulness,
        relevancy=relevancy,
    )

    return CaseRecord(
        id=case.id,
        category=case.category,
        question=case.question,
        expect_refusal=case.expect_refusal,
        refused=refused,
        refusal_correct=refusal_correct,
        context_precision=ctx_precision,
        context_recall=ctx_recall,
        faithfulness=faithfulness,
        relevancy=relevancy,
    )


async def run() -> None:
    settings = get_settings()
    embedder = load_embedder(settings.embedding_model)
    provider = build_provider(settings)
    engine = create_async_engine(settings.database_url)
    golden = load_golden()

    cases: list[CaseRecord] = []
    try:
        async with engine.connect() as connection:
            retriever = HybridRetriever(
                embedder=embedder,
                chunks=ChunkRepository(connection),
                candidates=settings.retrieval_candidates,
                top_k=settings.top_k,
                refusal_threshold=settings.refusal_threshold,
            )
            for golden_case in golden:
                record = await run_case(
                    golden_case, retriever=retriever, provider=provider
                )
                cases.append(record)
                status = "ok" if record.refusal_correct else "REFUSAL MISMATCH"
                print(f"  [{status:>16}]  {golden_case.id:<28} {golden_case.category}")
    finally:
        await engine.dispose()

    run_result = ProviderRun(
        provider=settings.llm_provider, model=settings.llm_model, cases=cases
    )
    save_run(run_result)
    update_report()

    n = len(cases)
    refusal_acc = sum(1 for c in cases if c.refusal_correct) / n
    print()
    print(f"provider:  {settings.llm_provider} / {settings.llm_model}")
    print(f"questions: {n}")
    print(f"refusal accuracy: {refusal_acc:.3f}")
    print("eval/REPORT.md updated.")


if __name__ == "__main__":
    asyncio.run(run())
