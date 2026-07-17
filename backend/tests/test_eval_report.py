"""Behavior: render and persist the Response Quality Benchmark section of
eval/REPORT.md from cached per-provider run results.

Pure rendering logic plus filesystem I/O against tmp_path; no doubles needed.
"""

from eval.report import (
    SECTION_HEADING,
    CaseRecord,
    ProviderRun,
    load_cached_runs,
    render_section,
    save_run,
    update_report,
)


def case(
    id: str = "c1",
    category: str = "factual",
    expect_refusal: bool = False,
    refused: bool = False,
    refusal_correct: bool = True,
    context_precision: float | None = 1.0,
    context_recall: float | None = 1.0,
    faithfulness: float | None = 0.9,
    relevancy: float | None = 0.8,
) -> CaseRecord:
    return CaseRecord(
        id=id,
        category=category,
        question="q",
        expect_refusal=expect_refusal,
        refused=refused,
        refusal_correct=refusal_correct,
        context_precision=context_precision,
        context_recall=context_recall,
        faithfulness=faithfulness,
        relevancy=relevancy,
    )


def test_render_provider_section_reports_overall_and_per_category_scores():
    run = ProviderRun(
        provider="anthropic",
        model="claude-haiku-4-5",
        cases=[
            case(id="a", category="factual", context_precision=1.0, faithfulness=1.0),
            case(
                id="b", category="negative", context_precision=None, faithfulness=None
            ),
        ],
    )

    text = render_section([run])

    assert "### anthropic / claude-haiku-4-5 (2 cases)" in text
    assert "| factual |" in text
    assert "| negative |" in text
    assert "1.000" in text  # case a's context precision/faithfulness
    assert "a" in text and "b" in text


def test_render_section_omits_metrics_with_no_scored_cases():
    run = ProviderRun(
        provider="anthropic",
        model="claude-haiku-4-5",
        cases=[
            case(
                id="n1",
                expect_refusal=True,
                context_precision=None,
                context_recall=None,
                faithfulness=None,
                relevancy=None,
            )
        ],
    )

    text = render_section([run])

    assert "—" in text


def test_render_section_joins_multiple_providers_sorted_by_name():
    ollama = ProviderRun(provider="ollama", model="qwen3.5:4b", cases=[case()])
    anthropic = ProviderRun(
        provider="anthropic", model="claude-haiku-4-5", cases=[case()]
    )

    text = render_section([ollama, anthropic])

    assert text.index("### anthropic") < text.index("### ollama")


def test_save_and_load_cached_runs_round_trip(monkeypatch, tmp_path):
    import eval.report as report_module

    monkeypatch.setattr(report_module, "RESULTS_DIR", tmp_path / "results")
    run = ProviderRun(provider="anthropic", model="claude-haiku-4-5", cases=[case()])

    save_run(run)
    [loaded] = load_cached_runs()

    assert loaded == run


def test_update_report_appends_the_section_when_absent(monkeypatch, tmp_path):
    import eval.report as report_module

    report_path = tmp_path / "REPORT.md"
    report_path.write_text("# Retrieval Eval Report\n\nExisting content.\n")
    monkeypatch.setattr(report_module, "REPORT_PATH", report_path)
    monkeypatch.setattr(report_module, "RESULTS_DIR", tmp_path / "results")
    save_run(
        ProviderRun(provider="anthropic", model="claude-haiku-4-5", cases=[case()])
    )

    update_report()

    text = report_path.read_text()
    assert "Existing content." in text
    assert SECTION_HEADING in text


def test_update_report_replaces_only_its_own_section_on_rerun(monkeypatch, tmp_path):
    import eval.report as report_module

    report_path = tmp_path / "REPORT.md"
    report_path.write_text("# Retrieval Eval Report\n\nExisting content.\n")
    monkeypatch.setattr(report_module, "REPORT_PATH", report_path)
    monkeypatch.setattr(report_module, "RESULTS_DIR", tmp_path / "results")
    save_run(
        ProviderRun(provider="anthropic", model="claude-haiku-4-5", cases=[case()])
    )
    update_report()

    save_run(
        ProviderRun(
            provider="anthropic", model="claude-haiku-4-5", cases=[case(id="new-case")]
        )
    )
    update_report()

    text = report_path.read_text()
    assert "Existing content." in text
    assert text.count(SECTION_HEADING) == 1
    assert "new-case" in text
    assert text.count("### anthropic") == 1
