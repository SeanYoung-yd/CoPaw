# -*- coding: utf-8 -*-
"""Evaluation benchmark API routes."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from copaw.evals.memory_bench import (
    MemoryBenchSuite,
    load_builtin_suite,
    run_memory_benchmark,
)


router = APIRouter(prefix="/evals", tags=["evals"])


class MemoryEvalRequest(BaseModel):
    """Request body for running a memory benchmark."""

    backend: Literal["keyword", "copaw"] = "keyword"
    suite: dict[str, Any] | None = None


@router.post("/memory")
async def run_memory_eval(request: MemoryEvalRequest) -> dict:
    """Run the memory benchmark and return a full report."""
    try:
        suite = (
            MemoryBenchSuite.from_dict(request.suite)
            if request.suite is not None
            else load_builtin_suite()
        )
        report = await run_memory_benchmark(
            suite=suite,
            backend_name=request.backend,
        )
        return report.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
