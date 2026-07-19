"""Response-quality benchmark runner (§13): golden Q&A set -> RAGAS-style
LLM-as-judge metrics, scored against the real production RAG path
(HybridRetriever + the configured ChatProvider).

Run from the repo root against a fully ingested database:

    uv run --project backend python -m eval.run

Environment: reads the same Settings as the API (DATABASE_URL, LLM_PROVIDER,
LLM_MODEL, EMBEDDING_MODEL, RETRIEVAL_CANDIDATES, TOP_K).
Every provider call pins temperature=0 for reproducibility, matching §13's
tuning-harness requirement. Re-run once per provider (e.g. once with
LLM_PROVIDER=anthropic, once with LLM_PROVIDER=ollama) to build the
per-provider comparison in REPORT.md.

The judge is pinned to JUDGE_MODEL regardless of LLM_PROVIDER, so every
provider's answers are graded by the same model — one deliberately stronger
than any graded model, so no contestant grades its own answers
(ANTHROPIC_API_KEY is therefore required even for local-provider runs).
"""

import asyncio

import anthropic
import structlog
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.ingest.embedding import load_embedder
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ChatMessage, ChatProvider
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
JUDGE_MODEL = "claude-sonnet-5"
logger = structlog.get_logger(__name__)


def build_judge(settings) -> ChatProvider:
    """Fixed judge, independent of the generation provider under test."""
    if not settings.anthropic_api_key:
        raise ValueError("the pinned judge requires ANTHROPIC_API_KEY")
    return AnthropicProvider(
        client=anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key),
        model=JUDGE_MODEL,
    )


async def run_case(
    case: GoldenCase, *, retriever: HybridRetriever, provider, judge_provider
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
                judge_provider,
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
    judge_provider = build_judge(settings)
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
            )
            for golden_case in golden:
                record = await run_case(
                    golden_case,
                    retriever=retriever,
                    provider=provider,
                    judge_provider=judge_provider,
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
