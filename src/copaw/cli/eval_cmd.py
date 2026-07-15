# -*- coding: utf-8 -*-
"""CLI commands for local evaluation benchmarks."""
from __future__ import annotations

from pathlib import Path

import click

from ..evals.memory_bench import (
    MemoryBenchSuite,
    load_builtin_suite,
    run_memory_benchmark_sync,
)


@click.group("eval")
def eval_group() -> None:
    """Run local evaluation benchmarks."""


@eval_group.command("memory")
@click.option(
    "--suite",
    "suite_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="JSON benchmark suite. Uses the built-in smoke suite by default.",
)
@click.option(
    "--backend",
    type=click.Choice(["keyword", "copaw"]),
    default="keyword",
    show_default=True,
    help="Memory backend to evaluate.",
)
@click.option(
    "--working-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "Base directory for temporary copaw backend fixtures. "
        "Real memory files are not overwritten."
    ),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Report output format.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the full JSON report to a file.",
)
def memory_eval_cmd(
    suite_path: Path | None,
    backend: str,
    working_dir: Path | None,
    output_format: str,
    output_path: Path | None,
) -> None:
    """Evaluate memory retrieval and compaction metrics."""
    suite = (
        MemoryBenchSuite.from_json(suite_path)
        if suite_path is not None
        else load_builtin_suite()
    )
    report = run_memory_benchmark_sync(
        suite=suite,
        backend_name=backend,
        working_dir=working_dir,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_json() + "\n", encoding="utf-8")

    if output_format == "json":
        click.echo(report.to_json())
    else:
        click.echo(report.to_text())
