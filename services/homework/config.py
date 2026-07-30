"""Homework AI fallback and completion configuration (LCAI-0018B / LCAI-0018B6)."""

from __future__ import annotations

import os
from dataclasses import dataclass

_GRADE_ALIASES: dict[str, str] = {
    "CM1": "FR-CM1",
    "CM2": "FR-CM2",
    "6E": "FR-6E",
    "5E": "FR-5E",
    "4E": "FR-4E",
    "3E": "FR-3E",
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw)


def _parse_grade_codes(raw: str | None) -> frozenset[str]:
    if raw is None or not raw.strip():
        return frozenset(_GRADE_ALIASES.values())
    codes: set[str] = set()
    for item in raw.split(","):
        token = item.strip().upper()
        if not token:
            continue
        codes.add(_GRADE_ALIASES.get(token, token if token.startswith("FR-") else f"FR-{token}"))
    return frozenset(codes)


def _parse_subject_codes(raw: str | None) -> frozenset[str] | None:
    if raw is None or not raw.strip() or raw.strip().upper() == "ALL":
        return None
    return frozenset(item.strip().upper() for item in raw.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class HomeworkAiFallbackSettings:
    max_retry: int = 1
    timeout_seconds: int = 30
    recent_exclusion_days: int = 30
    max_generated_per_request: int = 10
    allow_degraded_result: bool = True

    @classmethod
    def from_environment(cls) -> HomeworkAiFallbackSettings:
        max_per_homework = _env_int("HOMEWORK_AI_MAX_GENERATED_PER_HOMEWORK", 0)
        max_per_request = _env_int("HOMEWORK_AI_MAX_GENERATED_PER_REQUEST", 10)
        if max_per_homework > 0:
            max_per_request = max_per_homework
        return cls(
            max_retry=_env_int("HOMEWORK_AI_MAX_REPAIR_ATTEMPTS", _env_int("HOMEWORK_AI_FALLBACK_MAX_RETRY", 1)),
            timeout_seconds=_env_int("HOMEWORK_AI_FALLBACK_TIMEOUT_SECONDS", 30),
            recent_exclusion_days=_env_int("HOMEWORK_RECENT_EXCLUSION_DAYS", 30),
            max_generated_per_request=max_per_request,
            allow_degraded_result=_env_bool("HOMEWORK_AI_ALLOW_DEGRADED_RESULT", True),
        )

    def generation_cap(self, deficit: int) -> int:
        return max(0, min(deficit, self.max_generated_per_request))


@dataclass(frozen=True, slots=True)
class HomeworkAiCompletionSettings:
    allowed_grades: frozenset[str]
    allowed_subjects: frozenset[str] | None

    @classmethod
    def from_environment(cls) -> HomeworkAiCompletionSettings:
        return cls(
            allowed_grades=_parse_grade_codes(os.environ.get("HOMEWORK_AI_COMPLETION_GRADES")),
            allowed_subjects=_parse_subject_codes(os.environ.get("HOMEWORK_AI_COMPLETION_SUBJECTS")),
        )

    def grade_allowed(self, grade_code: str | None) -> bool:
        return grade_code is not None and grade_code in self.allowed_grades

    def subject_allowed(self, subject_code: str | None) -> bool:
        if self.allowed_subjects is None:
            return subject_code is not None
        return subject_code is not None and subject_code.upper() in self.allowed_subjects

