# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.evals.memory_bench import (
    MemoryBenchSuite,
    run_memory_benchmark_sync,
)


def test_frontend_memory_eval_suite_runs() -> None:
    suite_path = Path(__file__).with_name("memory_eval_frontend_suite.json")
    suite = MemoryBenchSuite.from_json(suite_path)

    report = run_memory_benchmark_sync(suite, backend_name="keyword")

    assert report.suite_name == "memory-eval-frontend-demo-suite"
    assert report.summary["search_error_rate"] == 0.0
    assert report.summary["compaction_error_rate"] == 0.0
    assert len(report.search_cases) == 6
    assert len(report.compaction_cases) == 4
    assert report.summary["search_avg_recall_at_k"] >= 0.8
    assert report.summary["compaction_avg_retention_rate"] >= 0.8
