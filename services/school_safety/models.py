"""School safety models for minors (LCAI-0022E)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SafetyChannel(StrEnum):
    """Where the text originates — reserved for channel-specific policy later (voice Lot 6)."""

    USER = "user"
    ASSISTANT = "assistant"
    CONTENT = "content"
    STT = "stt"


class SafetyAction(StrEnum):
    ALLOW = "ALLOW"
    REWRITE = "REWRITE"
    BLOCK = "BLOCK"


class SafetyCategory(StrEnum):
    SAFE = "SAFE"
    EMPTY = "EMPTY"
    DISTRESS = "DISTRESS"
    UNSAFE_CONTENT = "UNSAFE_CONTENT"
    PROMPT_INJECTION = "PROMPT_INJECTION"


@dataclass(frozen=True, slots=True)
class SafetyVerdict:
    action: SafetyAction
    category: SafetyCategory
    reason_codes: tuple[str, ...] = ()
    matched_pattern: str | None = None


@dataclass(frozen=True, slots=True)
class FilteredText:
    action: SafetyAction
    category: SafetyCategory
    text: str
    reason_codes: tuple[str, ...] = ()
    original_blocked: bool = False
