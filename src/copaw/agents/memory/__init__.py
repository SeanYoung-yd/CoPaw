# -*- coding: utf-8 -*-
"""Memory management module for CoPaw agents."""

from typing import TYPE_CHECKING

from .agent_md_manager import AgentMdManager
from .memory_architecture import (
    CompactMemory,
    Episode,
    FoldedMemory,
    MemoryIssue,
    MemoryTopic,
    SemanticMemory,
    compact_to_json,
    discover_topic_files,
    ensure_memory_architecture,
    folded_to_json,
    parse_topic_file,
    rebuild_memory_index,
    render_compact_memory_block,
    render_folded_memory_block,
    render_memory_index,
    validate_memory_directory,
)
from .privacy import REDACTION, sanitize_memory_text

if TYPE_CHECKING:
    from .memory_manager import MemoryManager

__all__ = [
    "AgentMdManager",
    "CompactMemory",
    "Episode",
    "FoldedMemory",
    "MemoryManager",
    "MemoryIssue",
    "MemoryTopic",
    "SemanticMemory",
    "compact_to_json",
    "discover_topic_files",
    "ensure_memory_architecture",
    "folded_to_json",
    "parse_topic_file",
    "rebuild_memory_index",
    "render_compact_memory_block",
    "render_folded_memory_block",
    "render_memory_index",
    "REDACTION",
    "sanitize_memory_text",
    "validate_memory_directory",
]


def __getattr__(name: str):
    if name == "MemoryManager":
        from .memory_manager import MemoryManager

        return MemoryManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
