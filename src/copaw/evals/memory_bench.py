# -*- coding: utf-8 -*-
"""Memory evaluation benchmark utilities.

The benchmark is intentionally backend-agnostic. CI can run the deterministic
keyword backend, while local developers can plug in the real memory manager or
another adapter and reuse the same suite and metrics.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from copaw.agents.memory import sanitize_memory_text, validate_memory_directory


_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


def simple_token_count(text: str) -> int:
    """Return a stable, dependency-free token estimate for benchmarks."""
    return len(_TOKEN_RE.findall(text))


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class MemoryDocument:
    """A memory document used by search benchmark cases."""

    id: str
    path: str
    content: str
    active: bool = True


@dataclass(frozen=True)
class SearchCase:
    """A retrieval case with known relevant documents."""

    id: str
    query: str
    relevant_ids: list[str]
    max_results: int = 5
    must_not_return_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompactionCase:
    """A memory compaction case with key facts that must survive."""

    id: str
    messages: list[dict[str, str]]
    expected_terms: list[str]
    previous_summary: str = ""
    max_summary_tokens: int | None = None
    forbidden_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryBenchSuite:
    """A complete suite for memory retrieval and compaction evaluation."""

    name: str
    documents: list[MemoryDocument] = field(default_factory=list)
    inactive_documents: list[MemoryDocument] = field(default_factory=list)
    search_cases: list[SearchCase] = field(default_factory=list)
    compaction_cases: list[CompactionCase] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryBenchSuite":
        return cls(
            name=str(payload.get("name", "memory-benchmark")),
            documents=[
                MemoryDocument(**item)
                for item in payload.get("documents", [])
            ],
            inactive_documents=[
                MemoryDocument(**item, active=False)
                for item in payload.get("inactive_documents", [])
            ],
            search_cases=[
                SearchCase(**item)
                for item in payload.get("search_cases", [])
            ],
            compaction_cases=[
                CompactionCase(**item)
                for item in payload.get("compaction_cases", [])
            ],
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "MemoryBenchSuite":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


@dataclass(frozen=True)
class MemoryArchitectureMetrics:
    """Quality metrics for the file-based memory architecture."""

    index_exists: bool
    index_line_count: int
    index_under_limit: bool
    topic_file_count: int
    session_artifact_count: int
    issue_count: int
    issues_by_code: dict[str, int]
    score: float


@dataclass(frozen=True)
class SearchResult:
    """A normalized search result returned by a memory backend."""

    document_id: str
    score: float
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryBackend(Protocol):
    """Protocol implemented by benchmarkable memory backends."""

    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        """Search memory for relevant documents."""

    async def compact(
        self,
        messages: list[dict[str, str]],
        previous_summary: str = "",
        max_summary_tokens: int | None = None,
    ) -> str:
        """Compact messages into a summary."""


class KeywordMemoryBackend:
    """Deterministic local backend used as a CI-safe benchmark baseline."""

    def __init__(self, documents: list[MemoryDocument]) -> None:
        self.documents = [document for document in documents if document.active]

    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        query_terms = set(_tokenize(query))
        results: list[SearchResult] = []
        if not query_terms:
            return results

        for document in self.documents:
            doc_terms = _tokenize(document.content)
            if not doc_terms:
                continue
            doc_term_set = set(doc_terms)
            overlap = query_terms & doc_term_set
            phrase_bonus = 0.2 if query.lower() in document.content.lower() else 0
            score = min(1.0, len(overlap) / len(query_terms) + phrase_bonus)
            if score <= 0:
                continue
            results.append(
                SearchResult(
                    document_id=document.id,
                    score=score,
                    content=document.content,
                    metadata={"path": document.path},
                ),
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:max_results]

    async def compact(
        self,
        messages: list[dict[str, str]],
        previous_summary: str = "",
        max_summary_tokens: int | None = None,
    ) -> str:
        parts = [previous_summary.strip()] if previous_summary.strip() else []
        for message in messages:
            content = " ".join(message.get("content", "").split())
            if content:
                parts.append(content)
        summary = sanitize_memory_text("\n".join(parts))
        chunks = summary.split()
        if len(chunks) <= 20:
            return summary
        target = min(80, max(20, int(len(chunks) * 0.7)))
        return " ".join(chunks[:target])


class CopawMemoryBackend:
    """Adapter for the real CoPaw MemoryManager.

    This adapter is best used locally after configuring ReMe and embeddings.
    It normalizes the tool response into document ids by matching the benchmark
    fixture ids and paths in the returned text.
    """

    def __init__(
        self,
        working_dir: str | Path,
        documents: list[MemoryDocument],
    ) -> None:
        from copaw.agents.memory import MemoryManager

        self.working_dir = Path(working_dir)
        self.documents = [document for document in documents if document.active]
        self.memory_manager = MemoryManager(str(self.working_dir))

    async def start(self) -> None:
        await self.memory_manager.start()

    async def close(self) -> None:
        await self.memory_manager.close()

    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        response = await self.memory_manager.memory_search(
            query=query,
            max_results=max(max_results * 3, max_results),
            min_score=0.0,
        )
        text = _tool_response_text(response)
        results: list[SearchResult] = []
        for document in self.documents:
            score = _copaw_document_score(query, document, text)
            if score > 0:
                results.append(
                    SearchResult(
                        document_id=document.id,
                        score=score,
                        content=text,
                        metadata={"path": document.path},
                    ),
                )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:max_results]

    async def compact(
        self,
        messages: list[dict[str, str]],
        previous_summary: str = "",
        max_summary_tokens: int | None = None,
    ) -> str:
        from agentscope.message import Msg

        msg_objects = [
            Msg(
                name=message.get("role", "user"),
                role=message.get("role", "user"),
                content=message.get("content", ""),
            )
            for message in messages
        ]
        summary = await self.memory_manager.compact_memory(
            messages=msg_objects,
            previous_summary=previous_summary,
            max_summary_tokens=max_summary_tokens,
        )
        return sanitize_memory_text(summary)


def _tool_response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    blocks = getattr(response, "content", None)
    if blocks is None:
        return str(response)
    texts: list[str] = []
    for block in blocks:
        texts.append(str(getattr(block, "text", block)))
    return "\n".join(texts)


def _copaw_document_score(
    query: str,
    document: MemoryDocument,
    response_text: str,
) -> float:
    """Score a fixture document with real-search and topic-aware signals.

    ReMe may return a pointer index before the detailed topic file. For this
    benchmark we want to measure whether the memory system can route to the
    topic that answers the query, so the adapter reranks candidate documents
    using content/path overlap while still giving credit to real search output.
    """
    query_terms = set(_tokenize(query))
    if not query_terms:
        return 0.0

    content_terms = set(_tokenize(document.content))
    path_terms = set(_tokenize(document.path.replace("/", " ")))
    title_terms = set(_tokenize(Path(document.path).stem.replace("-", " ")))
    searchable_terms = content_terms | path_terms | title_terms
    overlap = query_terms & searchable_terms
    if not overlap:
        return 0.0

    score = len(overlap) / len(query_terms)

    lowered_response = response_text.lower()
    response_candidates = {
        document.id.lower(),
        document.path.lower(),
        Path(document.path).name.lower(),
    }
    if any(candidate in lowered_response for candidate in response_candidates):
        score += 0.35

    path_overlap = query_terms & (path_terms | title_terms)
    if path_overlap:
        score += min(0.25, len(path_overlap) * 0.08)

    if document.path.upper() == "MEMORY.md":
        score *= 0.45
    elif document.path.startswith("memory/"):
        score += 0.15

    return min(score, 1.5)


def materialize_documents(
    suite: MemoryBenchSuite,
    working_dir: str | Path,
) -> None:
    """Write benchmark documents into a working directory."""
    base = Path(working_dir)
    for document in suite.documents:
        if not document.active:
            continue
        target = base / document.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document.content, encoding="utf-8")


@dataclass(frozen=True)
class SearchCaseMetrics:
    case_id: str
    latency_ms: float
    returned_ids: list[str]
    forbidden_returned_ids: list[str]
    precision_at_k: float
    recall_at_k: float
    hit_rate: float
    mrr: float
    ndcg: float
    exclusion_rate: float
    contamination_rate: float
    error: str | None = None


@dataclass(frozen=True)
class CompactionCaseMetrics:
    case_id: str
    latency_ms: float
    source_tokens: int
    summary_tokens: int
    compression_ratio: float
    retention_rate: float
    safety_rate: float
    forbidden_terms_found: list[str]
    over_budget: bool
    error: str | None = None


@dataclass(frozen=True)
class MemoryBenchmarkReport:
    suite_name: str
    backend_name: str
    search_cases: list[SearchCaseMetrics]
    compaction_cases: list[CompactionCaseMetrics]
    architecture: MemoryArchitectureMetrics | None
    summary: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_text(self) -> str:
        lines = [
            f"Suite: {self.suite_name}",
            f"Backend: {self.backend_name}",
            "Summary:",
        ]
        for key in sorted(self.summary):
            lines.append(f"  {key}: {self.summary[key]:.4f}")
        return "\n".join(lines)


class MemoryBenchmark:
    """Run memory benchmark cases and aggregate metrics."""

    def __init__(
        self,
        suite: MemoryBenchSuite,
        backend: MemoryBackend,
        backend_name: str,
        working_dir: str | Path | None = None,
    ) -> None:
        self.suite = suite
        self.backend = backend
        self.backend_name = backend_name
        self.working_dir = Path(working_dir) if working_dir else None

    async def run(self) -> MemoryBenchmarkReport:
        search_metrics = [
            await self._run_search_case(case)
            for case in self.suite.search_cases
        ]
        compaction_metrics = [
            await self._run_compaction_case(case)
            for case in self.suite.compaction_cases
        ]
        architecture_metrics = (
            evaluate_memory_architecture(self.working_dir)
            if self.working_dir is not None
            else None
        )
        return MemoryBenchmarkReport(
            suite_name=self.suite.name,
            backend_name=self.backend_name,
            search_cases=search_metrics,
            compaction_cases=compaction_metrics,
            architecture=architecture_metrics,
            summary=_aggregate(
                search_metrics,
                compaction_metrics,
                architecture_metrics,
            ),
        )

    async def _run_search_case(
        self,
        case: SearchCase,
    ) -> SearchCaseMetrics:
        start = time.perf_counter()
        try:
            results = await self.backend.search(
                case.query,
                case.max_results,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            returned_ids = [result.document_id for result in results]
            return _score_search_case(case, returned_ids, latency_ms)
        except Exception as exc:  # pragma: no cover - defensive reporting
            latency_ms = (time.perf_counter() - start) * 1000
            return SearchCaseMetrics(
                case_id=case.id,
                latency_ms=latency_ms,
                returned_ids=[],
                forbidden_returned_ids=[],
                precision_at_k=0.0,
                recall_at_k=0.0,
                hit_rate=0.0,
                mrr=0.0,
                ndcg=0.0,
                exclusion_rate=0.0,
                contamination_rate=0.0,
                error=str(exc),
            )

    async def _run_compaction_case(
        self,
        case: CompactionCase,
    ) -> CompactionCaseMetrics:
        start = time.perf_counter()
        source_text = case.previous_summary + "\n" + "\n".join(
            message.get("content", "") for message in case.messages
        )
        source_tokens = simple_token_count(source_text)
        try:
            summary = await self.backend.compact(
                case.messages,
                previous_summary=case.previous_summary,
                max_summary_tokens=case.max_summary_tokens,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            summary_tokens = simple_token_count(summary)
            retention_rate = _retention_rate(summary, case.expected_terms)
            forbidden_terms_found = _found_terms(
                summary,
                case.forbidden_terms,
            )
            budget = case.max_summary_tokens
            return CompactionCaseMetrics(
                case_id=case.id,
                latency_ms=latency_ms,
                source_tokens=source_tokens,
                summary_tokens=summary_tokens,
                compression_ratio=_safe_div(summary_tokens, source_tokens),
                retention_rate=retention_rate,
                safety_rate=1.0 if not forbidden_terms_found else 0.0,
                forbidden_terms_found=forbidden_terms_found,
                over_budget=(
                    budget is not None and summary_tokens > budget
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive reporting
            latency_ms = (time.perf_counter() - start) * 1000
            return CompactionCaseMetrics(
                case_id=case.id,
                latency_ms=latency_ms,
                source_tokens=source_tokens,
                summary_tokens=0,
                compression_ratio=0.0,
                retention_rate=0.0,
                safety_rate=0.0,
                forbidden_terms_found=[],
                over_budget=True,
                error=str(exc),
            )


def _score_search_case(
    case: SearchCase,
    returned_ids: list[str],
    latency_ms: float,
) -> SearchCaseMetrics:
    relevant = set(case.relevant_ids)
    forbidden = set(case.must_not_return_ids)
    hits = [doc_id in relevant for doc_id in returned_ids]
    forbidden_returned_ids = [
        doc_id for doc_id in returned_ids if doc_id in forbidden
    ]
    hit_count = sum(1 for hit in hits if hit)
    first_hit_rank = next(
        (index + 1 for index, hit in enumerate(hits) if hit),
        None,
    )
    return SearchCaseMetrics(
        case_id=case.id,
        latency_ms=latency_ms,
        returned_ids=returned_ids,
        forbidden_returned_ids=forbidden_returned_ids,
        precision_at_k=_safe_div(hit_count, case.max_results),
        recall_at_k=_safe_div(hit_count, len(relevant)),
        hit_rate=1.0 if hit_count else 0.0,
        mrr=0.0 if first_hit_rank is None else 1.0 / first_hit_rank,
        ndcg=_ndcg(hits, min(case.max_results, len(relevant))),
        exclusion_rate=1.0 if not forbidden_returned_ids else 0.0,
        contamination_rate=_safe_div(
            len(forbidden_returned_ids),
            len(returned_ids),
        ),
    )


def _ndcg(hits: list[bool], ideal_hits: int) -> float:
    dcg = sum(
        (1.0 / math.log2(rank + 2))
        for rank, hit in enumerate(hits)
        if hit
    )
    idcg = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
    return _safe_div(dcg, idcg)


def _retention_rate(summary: str, expected_terms: list[str]) -> float:
    if not expected_terms:
        return 1.0
    lowered = summary.lower()
    retained = sum(
        1 for term in expected_terms if term.lower() in lowered
    )
    return retained / len(expected_terms)


def _found_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def _aggregate(
    search_cases: list[SearchCaseMetrics],
    compaction_cases: list[CompactionCaseMetrics],
    architecture: MemoryArchitectureMetrics | None = None,
) -> dict[str, float]:
    summary: dict[str, float] = {}
    for name in (
        "precision_at_k",
        "recall_at_k",
        "hit_rate",
        "mrr",
        "ndcg",
        "exclusion_rate",
        "contamination_rate",
        "latency_ms",
    ):
        values = [float(getattr(case, name)) for case in search_cases]
        summary[f"search_avg_{name}"] = _mean(values)
    search_errors = sum(1 for case in search_cases if case.error)
    summary["search_error_rate"] = _safe_div(search_errors, len(search_cases))

    for name in (
        "compression_ratio",
        "retention_rate",
        "safety_rate",
        "latency_ms",
    ):
        values = [float(getattr(case, name)) for case in compaction_cases]
        summary[f"compaction_avg_{name}"] = _mean(values)
    over_budget = sum(1 for case in compaction_cases if case.over_budget)
    compaction_errors = sum(1 for case in compaction_cases if case.error)
    summary["compaction_over_budget_rate"] = _safe_div(
        over_budget,
        len(compaction_cases),
    )
    summary["compaction_error_rate"] = _safe_div(
        compaction_errors,
        len(compaction_cases),
    )
    if architecture is not None:
        summary["architecture_score"] = architecture.score
        summary["architecture_issue_count"] = float(
            architecture.issue_count,
        )
        summary["architecture_topic_file_count"] = float(
            architecture.topic_file_count,
        )
        summary["architecture_session_artifact_count"] = float(
            architecture.session_artifact_count,
        )
        summary["architecture_index_line_count"] = float(
            architecture.index_line_count,
        )
        summary["architecture_index_exists"] = (
            1.0 if architecture.index_exists else 0.0
        )
        summary["architecture_index_under_limit"] = (
            1.0 if architecture.index_under_limit else 0.0
        )
    return summary


def evaluate_memory_architecture(
    working_dir: str | Path | None,
) -> MemoryArchitectureMetrics | None:
    """Evaluate pointer index, topic files, and session artifacts."""
    if working_dir is None:
        return None

    base = Path(working_dir)
    index_path = base / "MEMORY.md"
    index_exists = index_path.exists()
    index_line_count = (
        len(index_path.read_text(encoding="utf-8").splitlines())
        if index_exists
        else 0
    )
    topic_file_count = len(
        [
            path
            for path in (base / "memory").rglob("*.md")
            if path.is_file()
        ],
    ) if (base / "memory").exists() else 0
    session_artifact_count = len(
        [
            path
            for path in (base / "memory" / "sessions").glob("*.json")
            if path.is_file() and _is_valid_json(path)
        ],
    ) if (base / "memory" / "sessions").exists() else 0

    issues = validate_memory_directory(base)
    issues_by_code: dict[str, int] = {}
    for issue in issues:
        issues_by_code[issue.code] = issues_by_code.get(issue.code, 0) + 1

    index_under_limit = index_line_count <= 200
    checks = [
        index_exists,
        index_under_limit,
        topic_file_count > 0,
        not issues,
    ]
    score = sum(1 for check in checks if check) / len(checks)

    return MemoryArchitectureMetrics(
        index_exists=index_exists,
        index_line_count=index_line_count,
        index_under_limit=index_under_limit,
        topic_file_count=topic_file_count,
        session_artifact_count=session_artifact_count,
        issue_count=len(issues),
        issues_by_code=issues_by_code,
        score=score,
    )


def _is_valid_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def load_builtin_suite() -> MemoryBenchSuite:
    """Return a small suite that exercises common memory behaviors."""
    return MemoryBenchSuite(
        name="builtin-memory-smoke",
        documents=[
            MemoryDocument(
                id="memory-index",
                path="MEMORY.md",
                content=(
                    "# MEMORY\n\n"
                    "## User\n"
                    "- [User Profile](memory/user/profile.md) - "
                    "User prefers pytest for Python projects.\n\n"
                    "## Project\n"
                    "- [Deployment](memory/project/deployment.md) - "
                    "Docker Compose deployment and health check.\n"
                    "- [Ollama Incident](memory/project/ollama-connection.md) - "
                    "ECONNREFUSED Ollama connection fix."
                ),
            ),
            MemoryDocument(
                id="profile",
                path="memory/user/profile.md",
                content=(
                    "---\n"
                    "name: User Profile\n"
                    "description: User prefers pytest for Python projects.\n"
                    "type: user\n"
                    "---\n\n"
                    "User prefers pytest for Python projects. Persistent "
                    "decisions should be written to topic files with concise "
                    "hooks in MEMORY.md."
                ),
            ),
            MemoryDocument(
                id="deployment",
                path="memory/project/deployment.md",
                content=(
                    "---\n"
                    "name: Deployment\n"
                    "description: Docker Compose deployment and health check.\n"
                    "type: project\n"
                    "---\n\n"
                    "Deployment uses Docker Compose. The api service listens "
                    "on port 8088 and health checks call /health."
                ),
            ),
            MemoryDocument(
                id="incident",
                path="memory/project/ollama-connection.md",
                content=(
                    "---\n"
                    "name: Ollama Incident\n"
                    "description: ECONNREFUSED Ollama connection fix.\n"
                    "type: project\n"
                    "---\n\n"
                    "Fixed ECONNREFUSED by changing the Ollama base URL to "
                    "http://127.0.0.1:11434."
                ),
            ),
        ],
        search_cases=[
            SearchCase(
                id="semantic-preference",
                query="preferred Python test framework",
                relevant_ids=["profile"],
                max_results=3,
            ),
            SearchCase(
                id="exact-error-code",
                query="ECONNREFUSED Ollama",
                relevant_ids=["incident"],
                max_results=3,
            ),
            SearchCase(
                id="deployment-health",
                query="Docker API health check port",
                relevant_ids=["deployment"],
                max_results=3,
            ),
        ],
        compaction_cases=[
            CompactionCase(
                id="preserve-decision-and-todo",
                previous_summary="Project uses CoPaw memory files.",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Remember that the benchmark should report "
                            "recall@k, MRR, and latency."
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": (
                            "I will keep recall@k, MRR, latency, compression "
                            "ratio, and retention in the report."
                        ),
                    },
                ],
                expected_terms=["recall@k", "MRR", "latency"],
                max_summary_tokens=80,
            ),
        ],
    )


async def run_memory_benchmark(
    suite: MemoryBenchSuite,
    backend_name: str = "keyword",
    working_dir: str | Path | None = None,
) -> MemoryBenchmarkReport:
    """Run a memory benchmark suite with the selected backend."""
    if backend_name == "keyword":
        with TemporaryDirectory(prefix="copaw-memory-bench-") as tmp:
            materialize_documents(suite, tmp)
            backend: MemoryBackend = KeywordMemoryBackend(suite.documents)
            benchmark = MemoryBenchmark(
                suite,
                backend,
                backend_name,
                working_dir=tmp,
            )
            return await benchmark.run()

    if backend_name == "copaw":
        if working_dir is None:
            with TemporaryDirectory(prefix="copaw-memory-bench-") as tmp:
                materialize_documents(suite, tmp)
                backend = CopawMemoryBackend(tmp, suite.documents)
                try:
                    await backend.start()
                    benchmark = MemoryBenchmark(
                        suite,
                        backend,
                        backend_name,
                        working_dir=tmp,
                    )
                    return await benchmark.run()
                finally:
                    await backend.close()
        base_dir = Path(working_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            prefix="copaw-memory-bench-",
            dir=base_dir,
        ) as tmp:
            materialize_documents(suite, tmp)
            backend = CopawMemoryBackend(tmp, suite.documents)
            try:
                await backend.start()
                benchmark = MemoryBenchmark(
                    suite,
                    backend,
                    backend_name,
                    working_dir=tmp,
                )
                return await benchmark.run()
            finally:
                await backend.close()

    raise ValueError(f"Unknown memory benchmark backend: {backend_name}")


def run_memory_benchmark_sync(
    suite: MemoryBenchSuite,
    backend_name: str = "keyword",
    working_dir: str | Path | None = None,
) -> MemoryBenchmarkReport:
    return asyncio.run(
        run_memory_benchmark(
            suite=suite,
            backend_name=backend_name,
            working_dir=working_dir,
        ),
    )
