"""Central school safety filter for minors (LCAI-0022E)."""

from __future__ import annotations

import re

from services.school_safety.models import (
    FilteredText,
    SafetyAction,
    SafetyCategory,
    SafetyChannel,
    SafetyVerdict,
)
from services.school_safety.patterns import (
    DISTRESS_PATTERNS,
    INJECTION_PATTERNS,
    SAFE_MESSAGE_DISTRESS,
    SAFE_MESSAGE_INJECTION,
    SAFE_MESSAGE_UNSAFE,
    UNSAFE_PATTERNS,
)

_COMPILED_DISTRESS = tuple(re.compile(p, re.IGNORECASE) for p in DISTRESS_PATTERNS)
_COMPILED_UNSAFE = tuple(re.compile(p, re.IGNORECASE) for p in UNSAFE_PATTERNS)
_COMPILED_INJECTION = tuple(re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS)


class SchoolSafetyFilter:
    """Deterministic text classifier shared by VT, content, and (later) voice."""

    def classify(self, text: str, *, channel: SafetyChannel | str = SafetyChannel.USER) -> SafetyVerdict:
        _ = SafetyChannel(str(channel))  # validate channel early for Lot 6 STT reuse
        lowered = (text or "").strip().lower()
        if not lowered:
            return SafetyVerdict(
                action=SafetyAction.BLOCK,
                category=SafetyCategory.EMPTY,
                reason_codes=("empty_message",),
            )
        for pattern in _COMPILED_DISTRESS:
            if pattern.search(lowered):
                return SafetyVerdict(
                    action=SafetyAction.BLOCK,
                    category=SafetyCategory.DISTRESS,
                    reason_codes=("distress_signal",),
                    matched_pattern=pattern.pattern,
                )
        for pattern in _COMPILED_UNSAFE:
            if pattern.search(lowered):
                return SafetyVerdict(
                    action=SafetyAction.BLOCK,
                    category=SafetyCategory.UNSAFE_CONTENT,
                    reason_codes=("unsafe_minors_content",),
                    matched_pattern=pattern.pattern,
                )
        for pattern in _COMPILED_INJECTION:
            if pattern.search(lowered):
                return SafetyVerdict(
                    action=SafetyAction.BLOCK,
                    category=SafetyCategory.PROMPT_INJECTION,
                    reason_codes=("prompt_injection",),
                    matched_pattern=pattern.pattern,
                )
        return SafetyVerdict(action=SafetyAction.ALLOW, category=SafetyCategory.SAFE, reason_codes=())

    def filter_text(self, text: str, *, channel: SafetyChannel | str = SafetyChannel.USER) -> FilteredText:
        verdict = self.classify(text, channel=channel)
        if verdict.action is SafetyAction.ALLOW:
            return FilteredText(
                action=SafetyAction.ALLOW,
                category=verdict.category,
                text=text,
                reason_codes=verdict.reason_codes,
            )
        return FilteredText(
            action=SafetyAction.BLOCK,
            category=verdict.category,
            text=self.safe_message(verdict.category),
            reason_codes=verdict.reason_codes,
            original_blocked=True,
        )

    @staticmethod
    def safe_message(category: SafetyCategory) -> str:
        if category is SafetyCategory.DISTRESS:
            return SAFE_MESSAGE_DISTRESS
        if category is SafetyCategory.PROMPT_INJECTION:
            return SAFE_MESSAGE_INJECTION
        if category is SafetyCategory.EMPTY:
            return "Écris une question sur ta leçon pour que je puisse t'aider."
        return SAFE_MESSAGE_UNSAFE


def get_school_safety_filter() -> SchoolSafetyFilter:
    """Composition helper for factories / TTS / content paths."""
    return SchoolSafetyFilter()
