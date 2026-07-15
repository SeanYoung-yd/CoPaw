# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.evals.memory_bench import (
    MemoryBenchSuite,
    run_memory_benchmark_sync,
)


def test_memory_strategy_discrimination_suite_runs() -> None:
    suite_path = Path(__file__).with_name(
        "memory_strategy_discrimination_suite.json",
    )
    suite = MemoryBenchSuite.from_json(suite_path)

    report = run_memory_benchmark_sync(suite, backend_name="keyword")

    assert report.suite_name == "memory-strategy-discrimination-suite"
    assert len(report.search_cases) == 8
    assert len(report.compaction_cases) == 6
    assert report.summary["search_error_rate"] == 0.0
    assert report.summary["compaction_error_rate"] == 0.0
    assert report.summary["search_avg_recall_at_k"] >= 0.75
    assert report.summary["compaction_avg_retention_rate"] >= 0.70
    assert "profile-obsolete" in report.search_cases[0].forbidden_returned_ids
    assert report.summary["search_avg_exclusion_rate"] < 1.0
    assert report.summary["compaction_avg_safety_rate"] < 1.0
