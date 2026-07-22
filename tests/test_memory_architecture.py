# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.agents.memory import (
    CompactMemory,
    Episode,
    FoldedMemory,
    SemanticMemory,
    discover_topic_files,
    ensure_memory_architecture,
    parse_topic_file,
    rebuild_memory_index,
    render_compact_memory_block,
    render_folded_memory_block,
    render_memory_index,
    validate_memory_directory,
)
from copaw.agents.memory.agent_md_manager import AgentMdManager
from copaw.agents.prompt import PromptBuilder


def test_memory_directory_validates_pointer_index(tmp_path: Path) -> None:
    memory_dir = tmp_path
    topic_dir = memory_dir / "memory" / "project"
    topic_dir.mkdir(parents=True)
    topic_file = topic_dir / "architecture.md"
    topic_file.write_text(
        "\n".join(
            [
                "---",
                "name: Memory Architecture",
                "description: MEMORY.md is a pointer index with topic files.",
                "type: project",
                "---",
                "",
                "Use a lightweight index and topic files.",
            ],
        ),
        encoding="utf-8",
    )

    topics = [
        parse_topic_file(path, memory_dir)
        for path in discover_topic_files(memory_dir)
    ]
    (memory_dir / "MEMORY.md").write_text(
        render_memory_index(topics),
        encoding="utf-8",
    )

    assert validate_memory_directory(memory_dir) == []


def test_memory_directory_reports_non_pointer_lines(
    tmp_path: Path,
) -> None:
    memory_dir = tmp_path
    (memory_dir / "MEMORY.md").write_text(
        "# MEMORY\n\nThis inline fact should move to a topic file.\n",
        encoding="utf-8",
    )

    issues = validate_memory_directory(memory_dir)

    assert [issue.code for issue in issues] == ["non-pointer-index-line"]


def test_compact_memory_block_keeps_decisions_and_next_steps() -> None:
    block = render_compact_memory_block(
        CompactMemory(
            task="Improve memory evaluation.",
            current_state="Suite runs with keyword backend.",
            key_decisions=[
                {
                    "decision": "Use keyword backend first.",
                    "reason": "It is deterministic.",
                    "constraint": "Use real backend after dependencies exist.",
                },
            ],
            eliminated_approaches=[
                {
                    "approach": "Rewrite suite before checking versions.",
                    "reason": "Old backend can mimic suite breakage.",
                },
            ],
            next_steps=["Validate topic index."],
            compacted_at_turn=7,
        ),
    )

    assert "compacted at turn 7" in block
    assert "Use keyword backend first." in block
    assert "Rewrite suite before checking versions." in block
    assert "Validate topic index." in block


def test_folded_memory_block_keeps_semantic_and_episode_layers() -> None:
    block = render_folded_memory_block(
        FoldedMemory(
            semantic=SemanticMemory(
                facts=["MEMORY.md is pointer-only."],
                decisions=[
                    {
                        "decision": "Store details in topic files.",
                        "reason": "They are reviewable.",
                    },
                ],
            ),
            episodes=[
                Episode(
                    episode_id=2,
                    turn_range=(10, 19),
                    summary="Diagnosed stale backend schema.",
                    open_questions=["Expose dream as a CLI command?"],
                ),
            ],
            current_episode_id=3,
            total_turns_seen=20,
        ),
    )

    assert "Semantic memory" in block
    assert "MEMORY.md is pointer-only." in block
    assert "Episode 2 (10-19)" in block
    assert "Expose dream as a CLI command?" in block


def test_ensure_memory_architecture_creates_layout(
    tmp_path: Path,
) -> None:
    ensure_memory_architecture(tmp_path)

    assert (tmp_path / "MEMORY.md").exists()
    assert (tmp_path / "memory" / "user").is_dir()
    assert (tmp_path / "memory" / "feedback").is_dir()
    assert (tmp_path / "memory" / "project").is_dir()
    assert (tmp_path / "memory" / "reference").is_dir()
    assert (tmp_path / "memory" / "sessions").is_dir()
    assert validate_memory_directory(tmp_path) == []


def test_memory_discovery_ignores_active_skills(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "active_skills" / "agent-memory-implementation"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: agent-memory-implementation",
                "description: Skill metadata is not memory.",
                "license: local",
                "---",
                "",
                "# Skill",
            ],
        ),
        encoding="utf-8",
    )
    topic = tmp_path / "memory" / "project" / "decision.md"
    topic.parent.mkdir(parents=True)
    topic.write_text(
        "\n".join(
            [
                "---",
                "name: Decision",
                "description: Current project decision.",
                "type: project",
                "---",
                "",
                "Keep runtime skill files out of memory validation.",
            ],
        ),
        encoding="utf-8",
    )

    topics = discover_topic_files(tmp_path)

    assert topics == [topic]


def test_rebuild_memory_index_from_topics(tmp_path: Path) -> None:
    ensure_memory_architecture(tmp_path)
    topic = tmp_path / "memory" / "feedback" / "style.md"
    topic.write_text(
        "\n".join(
            [
                "---",
                "name: Style Preference",
                "description: User wants concise answers.",
                "type: feedback",
                "---",
                "",
                "**Rule:** Keep answers concise.",
            ],
        ),
        encoding="utf-8",
    )

    rebuild_memory_index(tmp_path)

    index = (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert (
        "- [Style Preference](memory/feedback/style.md) - "
        "User wants concise answers."
    ) in index
    assert validate_memory_directory(tmp_path) == []


def test_agent_md_manager_lists_and_writes_nested_memory(
    tmp_path: Path,
) -> None:
    manager = AgentMdManager(tmp_path)

    manager.write_memory_md("project/decision", "content")
    files = manager.list_memory_mds()

    assert files[0]["filename"] == "project/decision.md"
    assert manager.read_memory_md("project/decision.md") == "content"


def test_agent_md_manager_rejects_path_escape(tmp_path: Path) -> None:
    manager = AgentMdManager(tmp_path)

    try:
        manager.write_memory_md("../escape", "nope")
    except ValueError as exc:
        assert "escapes memory directory" in str(exc)
    else:
        raise AssertionError("Expected path escape to be rejected")


def test_prompt_builder_loads_memory_index(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("agent rules", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("soul rules", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text(
        "# MEMORY\n\n## Project\n"
        "- [Decision](memory/project/decision.md) - hook\n",
        encoding="utf-8",
    )

    prompt = PromptBuilder(tmp_path).build()

    assert "# MEMORY.md" in prompt
    assert "[Decision](memory/project/decision.md)" in prompt
