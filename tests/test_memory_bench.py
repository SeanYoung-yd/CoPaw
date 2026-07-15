# -*- coding: utf-8 -*-
from __future__ import annotations

from click.testing import CliRunner

from copaw.cli.main import cli
from copaw.agents.memory import REDACTION, sanitize_memory_text
from copaw.evals.memory_bench import (
    CompactionCase,
    MemoryBenchmark,
    KeywordMemoryBackend,
    MemoryBenchSuite,
    MemoryDocument,
    SearchCase,
    _score_search_case,
    evaluate_memory_architecture,
    load_builtin_suite,
    materialize_documents,
    run_memory_benchmark_sync,
)


def test_search_metrics_rank_relevant_first() -> None:
    metrics = _score_search_case(
        SearchCase(
            id="case-1",
            query="query",
            relevant_ids=["doc-a"],
            max_results=3,
        ),
        returned_ids=["doc-a", "doc-b"],
        latency_ms=12.5,
    )

    assert metrics.precision_at_k == 1 / 3
    assert metrics.recall_at_k == 1.0
    assert metrics.hit_rate == 1.0
    assert metrics.mrr == 1.0
    assert metrics.ndcg == 1.0
    assert metrics.exclusion_rate == 1.0
    assert metrics.contamination_rate == 0.0


def test_search_metrics_penalize_forbidden_results() -> None:
    metrics = _score_search_case(
        SearchCase(
            id="case-1",
            query="query",
            relevant_ids=["doc-a"],
            must_not_return_ids=["doc-old"],
            max_results=3,
        ),
        returned_ids=["doc-a", "doc-old", "doc-b"],
        latency_ms=12.5,
    )

    assert metrics.recall_at_k == 1.0
    assert metrics.forbidden_returned_ids == ["doc-old"]
    assert metrics.exclusion_rate == 0.0
    assert metrics.contamination_rate == 1 / 3


async def test_inactive_documents_are_not_searched_or_materialized(
    tmp_path,
) -> None:
    suite = MemoryBenchSuite(
        name="inactive-doc-suite",
        documents=[
            MemoryDocument(
                id="current",
                path="MEMORY.md",
                content="Current preference is pytest.",
            ),
        ],
        inactive_documents=[
            MemoryDocument(
                id="obsolete",
                path="memory/user/obsolete.md",
                content="Obsolete preference was unittest.",
            ),
        ],
        search_cases=[
            SearchCase(
                id="current-wins",
                query="pytest unittest preference",
                relevant_ids=["current"],
                must_not_return_ids=["obsolete"],
                max_results=3,
            ),
        ],
    )
    materialize_documents(suite, tmp_path)
    benchmark = MemoryBenchmark(
        suite=suite,
        backend=KeywordMemoryBackend(suite.documents),
        backend_name="keyword",
        working_dir=tmp_path,
    )

    report = await benchmark.run()

    assert not (tmp_path / "memory" / "user" / "obsolete.md").exists()
    assert report.search_cases[0].returned_ids == ["current"]
    assert report.search_cases[0].forbidden_returned_ids == []
    assert report.search_cases[0].exclusion_rate == 1.0


def test_sanitize_memory_text_redacts_secret_values() -> None:
    text = (
        "My API key is sk-test-secret and private tokens must not be "
        "persisted."
    )

    sanitized = sanitize_memory_text(text)

    assert "sk-test-secret" not in sanitized
    assert REDACTION in sanitized
    assert "private tokens must not be persisted" in sanitized


async def test_compaction_metrics_redact_forbidden_terms() -> None:
    suite = MemoryBenchSuite(
        name="forbidden-term-suite",
        documents=[
            MemoryDocument(
                id="policy",
                path="MEMORY.md",
                content="Do not persist API keys.",
            ),
        ],
        compaction_cases=[
            CompactionCase(
                id="secret-leak",
                messages=[
                    {
                        "role": "user",
                        "content": "Do not save API key sk-test-secret.",
                    },
                ],
                expected_terms=["API key"],
                forbidden_terms=["sk-test-secret"],
            ),
        ],
    )
    benchmark = MemoryBenchmark(
        suite=suite,
        backend=KeywordMemoryBackend(suite.documents),
        backend_name="keyword",
    )

    report = await benchmark.run()
    case = report.compaction_cases[0]

    assert case.retention_rate == 1.0
    assert case.safety_rate == 1.0
    assert case.forbidden_terms_found == []
    assert report.summary["compaction_avg_safety_rate"] == 1.0


async def test_builtin_memory_benchmark_runs() -> None:
    suite = load_builtin_suite()
    benchmark = MemoryBenchmark(
        suite=suite,
        backend=KeywordMemoryBackend(suite.documents),
        backend_name="keyword",
    )

    report = await benchmark.run()

    assert report.summary["search_error_rate"] == 0.0
    assert report.summary["compaction_error_rate"] == 0.0
    assert report.summary["search_avg_recall_at_k"] > 0.0
    assert report.summary["compaction_avg_retention_rate"] == 1.0


def test_architecture_metrics_validate_topic_memory(tmp_path) -> None:
    suite = MemoryBenchSuite(
        name="architecture-suite",
        documents=[
            MemoryDocument(
                id="index",
                path="MEMORY.md",
                content=(
                    "# MEMORY\n\n## Project\n"
                    "- [Decision](memory/project/decision.md) - "
                    "Pointer index architecture decision."
                ),
            ),
            MemoryDocument(
                id="decision",
                path="memory/project/decision.md",
                content=(
                    "---\n"
                    "name: Decision\n"
                    "description: Pointer index architecture decision.\n"
                    "type: project\n"
                    "---\n\n"
                    "MEMORY.md is a pointer-only index."
                ),
            ),
            MemoryDocument(
                id="restore",
                path="memory/sessions/session-folded.json",
                content='{"memory":{"semantic":{"facts":[]}},"l1_turns":[]}',
            ),
        ],
    )
    materialize_documents(suite, tmp_path)

    metrics = evaluate_memory_architecture(tmp_path)

    assert metrics is not None
    assert metrics.score == 1.0
    assert metrics.issue_count == 0
    assert metrics.topic_file_count == 1
    assert metrics.session_artifact_count == 1


def test_run_memory_benchmark_reports_architecture_metrics() -> None:
    suite = load_builtin_suite()

    report = run_memory_benchmark_sync(suite, backend_name="keyword")

    assert report.architecture is not None
    assert "architecture_score" in report.summary


def test_memory_eval_cli_json() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["eval", "memory", "--format", "json"])

    assert result.exit_code == 0
    assert '"suite_name": "builtin-memory-smoke"' in result.output
    assert '"search_avg_recall_at_k"' in result.output
    assert '"architecture_score"' in result.output
