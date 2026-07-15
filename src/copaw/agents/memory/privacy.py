# -*- coding: utf-8 -*-
"""Privacy helpers for memory persistence and compaction."""
from __future__ import annotations

import re


REDACTION = "[REDACTED_SECRET]"

_SECRET_PATTERNS = (
    # OpenAI-style and test API keys. Keep this intentionally broad because
    # memory summaries should preserve the policy, not the credential value.
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{6,}\b"),
    re.compile(r"\bsk_test_[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bsk_live_[A-Za-z0-9_-]{8,}\b"),
    # Common assignment forms: api_key=..., token: ..., password is ...
    re.compile(
        r"(?i)\b("
        r"api[\s_-]*key|access[\s_-]*token|refresh[\s_-]*token|"
        r"private[\s_-]*token|secret|password|passwd|pwd"
        r")\b(\s*(?:is|=|:)\s*)([^\s,.;，。；]+)",
    ),
)


def sanitize_memory_text(text: str) -> str:
    """Redact sensitive values before text is persisted as memory.

    The sanitizer is deliberately conservative: it keeps surrounding context
    such as "private tokens must not be persisted", while replacing concrete
    credential values that should never survive compaction or summarization.
    """
    if not text:
        return text

    sanitized = text
    sanitized = _SECRET_PATTERNS[0].sub(REDACTION, sanitized)
    sanitized = _SECRET_PATTERNS[1].sub(REDACTION, sanitized)
    sanitized = _SECRET_PATTERNS[2].sub(REDACTION, sanitized)
    sanitized = _SECRET_PATTERNS[3].sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTION}",
        sanitized,
    )
    return sanitized
