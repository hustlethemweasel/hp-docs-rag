"""Renders and persists the Response Quality Benchmark section of
eval/REPORT.md from cached per-provider run results, per the benchmark
described in SPEC.md.

Each provider's run is cached as JSON under `eval/results/` (gitignored) so
`update_report` can render every provider evaluated so far, even across
separate CLI invocations, without clobbering other sections of REPORT.md.
"""

import json
from dataclasses import asdict, dataclass

from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
REPORT_PATH = Path(__file__).parent / "REPORT.md"
SECTION_HEADING = "## Response Quality Benchmark"

INTRO = (
    "LLM-as-judge quality benchmark on the golden set (`golden.jsonl`), per "
    "the response-quality benchmark described in SPEC.md. Run with "
    "`uv run --project backend python -m eval.run` against a fully ingested "
    "database; temperature is pinned to 0 on every provider call for "
    "reproducibility."
)


@dataclass(frozen=True)
class CaseRecord:
    id: str
    category: str
    question: str
    expect_refusal: bool
    refused: bool
    refusal_correct: bool
    context_precision: float | None
    context_recall: float | None
    faithfulness: float | None
    relevancy: float | None


@dataclass(frozen=True)
class ProviderRun:
    provider: str
    model: str
    cases: list[CaseRecord]


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "—"


def render_provider_section(run: ProviderRun) -> str:
    lines = [f"### {run.provider} / {run.model} ({len(run.cases)} cases)", ""]

    overall = {
        "refusal accuracy": _avg(
            [1.0 if c.refusal_correct else 0.0 for c in run.cases]
        ),
        "context precision": _avg([c.context_precision for c in run.cases]),
        "context recall": _avg([c.context_recall for c in run.cases]),
        "faithfulness": _avg([c.faithfulness for c in run.cases]),
        "answer relevancy": _avg([c.relevancy for c in run.cases]),
    }
    lines += ["| Metric | Score |", "|---|---|"]
    lines += [f"| {name} | {_fmt(value)} |" for name, value in overall.items()]
    lines.append("")

    lines.append(
        "| Category | n | refusal acc. | ctx precision | ctx recall "
        "| faithfulness | relevancy |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for category in sorted({c.category for c in run.cases}):
        subset = [c for c in run.cases if c.category == category]
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                category,
                len(subset),
                _fmt(_avg([1.0 if c.refusal_correct else 0.0 for c in subset])),
                _fmt(_avg([c.context_precision for c in subset])),
                _fmt(_avg([c.context_recall for c in subset])),
                _fmt(_avg([c.faithfulness for c in subset])),
                _fmt(_avg([c.relevancy for c in subset])),
            )
        )
    lines.append("")

    lines.append("<details><summary>Per-question breakdown</summary>")
    lines.append("")
    lines.append(
        "| id | category | refusal ok | ctx precision | ctx recall "
        "| faithfulness | relevancy |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for c in run.cases:
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                c.id,
                c.category,
                "✓" if c.refusal_correct else "✗",
                _fmt(c.context_precision),
                _fmt(c.context_recall),
                _fmt(c.faithfulness),
                _fmt(c.relevancy),
            )
        )
    lines += ["", "</details>"]
    return "\n".join(lines)


def render_section(runs: list[ProviderRun]) -> str:
    parts = [SECTION_HEADING, "", INTRO, ""]
    for run in sorted(runs, key=lambda r: r.provider):
        parts.append(render_provider_section(run))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def save_run(run: ProviderRun) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{run.provider}.json"
    data = {
        "provider": run.provider,
        "model": run.model,
        "cases": [asdict(c) for c in run.cases],
    }
    path.write_text(json.dumps(data, indent=2))


def load_cached_runs() -> list[ProviderRun]:
    if not RESULTS_DIR.exists():
        return []
    runs = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        cases = [CaseRecord(**c) for c in data["cases"]]
        runs.append(
            ProviderRun(provider=data["provider"], model=data["model"], cases=cases)
        )
    return runs


def update_report() -> None:
    """Rewrite the Response Quality Benchmark section from cached runs.

    Only that section is touched — everything before it (the retrieval-eval
    history) is preserved verbatim.
    """
    runs = load_cached_runs()
    if not runs:
        return
    new_section = render_section(runs)
    text = REPORT_PATH.read_text()
    idx = text.find(SECTION_HEADING)
    before = text if idx == -1 else text[:idx]
    REPORT_PATH.write_text(before.rstrip() + "\n\n" + new_section)
