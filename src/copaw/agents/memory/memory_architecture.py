# -*- coding: utf-8 -*-
"""Utilities for maintaining CoPaw's file-based memory architecture.

The helpers in this module keep long-term memory auditable:

* ``MEMORY.md`` stays a small pointer-only index.
* Topic files carry load-bearing frontmatter.
* Compact and folded memory blocks use predictable, resumable formats.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MEMORY_INDEX_MAX_LINES = 200
MEMORY_POINTER_MAX_CHARS = 150
VALID_MEMORY_TYPES = {"user", "feedback", "project", "reference"}

_FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n?", re.S)
_POINTER_RE = re.compile(r"^- \[(?P<title>[^\]]+)\]\((?P<path>[^)]+)\) - .+")


@dataclass(frozen=True)
class MemoryTopic:
    """A topic memory file with validated frontmatter."""

    path: str
    name: str
    description: str
    type: str
    body: str


@dataclass(frozen=True)
class MemoryIssue:
    """A validation issue for a file-based memory directory."""

    code: str
    path: str
    message: str


@dataclass(frozen=True)
class CompactMemory:
    """Flat compact summary for restoring a long-running session."""

    task: str
    current_state: str
    key_decisions: list[dict[str, str]] = field(default_factory=list)
    eliminated_approaches: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    relevant_tool_results: dict[str, str] = field(default_factory=dict)
    compacted_at_turn: int = 0


@dataclass(frozen=True)
class Episode:
    """Medium-detail folded memory episode."""

    episode_id: int
    turn_range: tuple[int, int]
    summary: str
    decisions: list[dict[str, str]] = field(default_factory=list)
    eliminated: list[dict[str, str]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    tool_results: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticMemory:
    """Durable folded memory facts and decisions."""

    facts: list[str] = field(default_factory=list)
    decisions: list[dict[str, str]] = field(default_factory=list)
    eliminated_approaches: list[dict[str, str]] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FoldedMemory:
    """Three-layer memory state without the raw L1 working turns."""

    semantic: SemanticMemory = field(default_factory=SemanticMemory)
    episodes: list[Episode] = field(default_factory=list)
    current_episode_id: int = 0
    total_turns_seen: int = 0


def parse_topic_file(path: str | Path, base_dir: str | Path) -> MemoryTopic:
    """Parse a topic file and return its validated metadata and body."""
    path_obj = Path(path)
    base = Path(base_dir)
    text = path_obj.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path_obj} is missing YAML frontmatter")

    metadata = _parse_simple_yaml(match.group("body"))
    missing = [
        key
        for key in ("name", "description", "type")
        if not metadata.get(key)
    ]
    if missing:
        raise ValueError(f"{path_obj} is missing frontmatter: {missing}")

    topic_type = metadata["type"]
    if topic_type not in VALID_MEMORY_TYPES:
        raise ValueError(f"{path_obj} has invalid memory type: {topic_type}")

    return MemoryTopic(
        path=_relative_posix(path_obj, base),
        name=metadata["name"],
        description=metadata["description"],
        type=topic_type,
        body=text[match.end() :].strip(),
    )


def discover_topic_files(memory_dir: str | Path) -> list[Path]:
    """Return topic files under memory_dir, excluding MEMORY.md indexes."""
    base = Path(memory_dir)
    files = [
        path
        for path in base.rglob("*.md")
        if path.name.lower() != "memory.md"
    ]
    return sorted(files, key=lambda item: item.as_posix())


def render_memory_index(topics: list[MemoryTopic]) -> str:
    """Render a pointer-only MEMORY.md from topic metadata."""
    grouped: dict[str, list[MemoryTopic]] = {
        type_name: [] for type_name in sorted(VALID_MEMORY_TYPES)
    }
    for topic in sorted(topics, key=lambda item: (item.type, item.name)):
        grouped.setdefault(topic.type, []).append(topic)

    lines = ["# MEMORY"]
    for type_name, items in grouped.items():
        if not items:
            continue
        lines.extend(["", f"## {type_name.title()}"])
        for topic in items:
            hook = _truncate(topic.description, MEMORY_POINTER_MAX_CHARS)
            lines.append(f"- [{topic.name}]({topic.path}) - {hook}")
    return "\n".join(lines).rstrip() + "\n"


def validate_memory_directory(memory_dir: str | Path) -> list[MemoryIssue]:
    """Validate topic frontmatter and pointer-only MEMORY.md shape."""
    base = Path(memory_dir)
    issues: list[MemoryIssue] = []
    topics: list[MemoryTopic] = []

    for topic_file in discover_topic_files(base):
        try:
            topics.append(parse_topic_file(topic_file, base))
        except ValueError as exc:
            issues.append(
                MemoryIssue(
                    code="invalid-topic-frontmatter",
                    path=_relative_posix(topic_file, base),
                    message=str(exc),
                ),
            )

    index_path = base / "MEMORY.md"
    if not index_path.exists():
        issues.append(
            MemoryIssue(
                code="missing-index",
                path="MEMORY.md",
                message="MEMORY.md pointer index is missing.",
            ),
        )
        return issues

    index_lines = index_path.read_text(encoding="utf-8").splitlines()
    if len(index_lines) > MEMORY_INDEX_MAX_LINES:
        issues.append(
            MemoryIssue(
                code="index-too-long",
                path="MEMORY.md",
                message=(
                    f"MEMORY.md has {len(index_lines)} lines; "
                    f"limit is {MEMORY_INDEX_MAX_LINES}."
                ),
            ),
        )

    topic_paths = {topic.path for topic in topics}
    pointer_paths: set[str] = set()
    for line_number, line in enumerate(index_lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _POINTER_RE.match(stripped)
        if not match:
            issues.append(
                MemoryIssue(
                    code="non-pointer-index-line",
                    path="MEMORY.md",
                    message=f"Line {line_number} is not a pointer entry.",
                ),
            )
            continue
        target = match.group("path")
        pointer_paths.add(target)
        if target not in topic_paths:
            issues.append(
                MemoryIssue(
                    code="dangling-pointer",
                    path="MEMORY.md",
                    message=f"Line {line_number} points to missing {target}.",
                ),
            )

    for topic_path in sorted(topic_paths - pointer_paths):
        issues.append(
            MemoryIssue(
                code="unindexed-topic",
                path=topic_path,
                message=f"{topic_path} has no MEMORY.md pointer.",
            ),
        )

    return issues


def ensure_memory_architecture(working_dir: str | Path) -> None:
    """Ensure a workspace has the topic-file memory directory layout.

    This does not overwrite existing topic files. If ``MEMORY.md`` is absent,
    it creates a pointer-only index from existing topics, or a minimal empty
    index when no topics exist yet.
    """
    base = Path(working_dir)
    memory_dir = base / "memory"
    for directory in (
        memory_dir / "user",
        memory_dir / "feedback",
        memory_dir / "project",
        memory_dir / "reference",
        memory_dir / "sessions",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    index_path = base / "MEMORY.md"
    if index_path.exists():
        return

    topics = [
        parse_topic_file(path, base)
        for path in discover_topic_files(base)
        if _has_frontmatter(path)
    ]
    index_path.write_text(render_memory_index(topics), encoding="utf-8")


def rebuild_memory_index(working_dir: str | Path) -> None:
    """Rebuild ``MEMORY.md`` from valid topic files in ``memory/``."""
    base = Path(working_dir)
    topics = [
        parse_topic_file(path, base)
        for path in discover_topic_files(base)
        if _has_frontmatter(path)
    ]
    (base / "MEMORY.md").write_text(
        render_memory_index(topics),
        encoding="utf-8",
    )


def render_compact_memory_block(memory: CompactMemory) -> str:
    """Render a flat compact summary for prompt restoration."""
    lines = [
        f"## Restored memory (compacted at turn {memory.compacted_at_turn})",
        "",
        f"**Task**: {memory.task}",
        "",
        f"**Current state**: {memory.current_state}",
    ]
    _append_dict_list(lines, "Key decisions", memory.key_decisions, "decision")
    _append_dict_list(
        lines,
        "Ruled out approaches",
        memory.eliminated_approaches,
        "approach",
    )
    _append_list(lines, "Open questions", memory.open_questions)
    _append_list(lines, "Next steps", memory.next_steps)
    if memory.relevant_tool_results:
        lines.extend(["", "**Relevant tool results**:"])
        for key, value in sorted(memory.relevant_tool_results.items()):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def render_folded_memory_block(memory: FoldedMemory) -> str:
    """Render L3 semantic and L2 episode memory for prompt restoration."""
    lines = ["## Folded memory"]
    semantic = memory.semantic
    if any(
        (
            semantic.facts,
            semantic.decisions,
            semantic.eliminated_approaches,
            semantic.patterns,
        ),
    ):
        lines.extend(["", "### Semantic memory"])
        _append_list(lines, "Facts", semantic.facts)
        _append_dict_list(lines, "Decisions", semantic.decisions, "decision")
        _append_dict_list(
            lines,
            "Ruled out",
            semantic.eliminated_approaches,
            "approach",
        )
        _append_list(lines, "Patterns", semantic.patterns)

    if memory.episodes:
        lines.extend(["", "### Episode memory"])
        for episode in memory.episodes:
            start, end = episode.turn_range
            lines.append(f"- Episode {episode.episode_id} ({start}-{end}):")
            lines.append(f"  {episode.summary}")
            for decision in episode.decisions:
                value = decision.get("decision", "")
                reason = decision.get("reason") or decision.get("why")
                suffix = f" because {reason}" if reason else ""
                lines.append(f"  Decision: {value}{suffix}")
            for question in episode.open_questions:
                lines.append(f"  Open: {question}")

    return "\n".join(lines).rstrip() + "\n"


def compact_to_json(memory: CompactMemory) -> str:
    """Serialize a compact memory object with stable formatting."""
    return json.dumps(memory.__dict__, ensure_ascii=False, indent=2)


def folded_to_json(memory: FoldedMemory) -> str:
    """Serialize folded memory with stable formatting."""
    payload = {
        "semantic": memory.semantic.__dict__,
        "episodes": [
            {
                "episode_id": episode.episode_id,
                "turn_range": list(episode.turn_range),
                "summary": episode.summary,
                "decisions": episode.decisions,
                "eliminated": episode.eliminated,
                "open_questions": episode.open_questions,
                "tool_results": episode.tool_results,
            }
            for episode in memory.episodes
        ],
        "current_episode_id": memory.current_episode_id,
        "total_turns_seen": memory.total_turns_seen,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_simple_yaml(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def _has_frontmatter(path: Path) -> bool:
    try:
        return path.read_text(encoding="utf-8").startswith("---\n")
    except OSError:
        return False


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend(["", f"**{title}**:"])
    for item in items:
        lines.append(f"- {item}")


def _append_dict_list(
    lines: list[str],
    title: str,
    items: list[dict[str, str]],
    key: str,
) -> None:
    if not items:
        return
    lines.extend(["", f"**{title}**:"])
    for item in items:
        value = item.get(key, "")
        reason = item.get("reason") or item.get("why")
        constraint = item.get("constraint")
        suffixes = []
        if reason:
            suffixes.append(f"because {reason}")
        if constraint:
            suffixes.append(f"constraint: {constraint}")
        suffix = f" ({'; '.join(suffixes)})" if suffixes else ""
        lines.append(f"- {value}{suffix}")


def _relative_posix(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _truncate(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
