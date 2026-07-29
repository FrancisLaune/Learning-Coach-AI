"""Homework AI fallback configuration (LCAI-0018B)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw)


@dataclass(frozen=True, slots=True)
class HomeworkAiFallbackSettings:
    max_retry: int = 1
    timeout_seconds: int = 30
    recent_exclusion_days: int = 30
    max_generated_per_request: int = 10
    allow_degraded_result: bool = True

    @classmethod
    def from_environment(cls) -> HomeworkAiFallbackSettings:
        return cls(
            max_retry=_env_int("HOMEWORK_AI_FALLBACK_MAX_RETRY", 1),
            timeout_seconds=_env_int("HOMEWORK_AI_FALLBACK_TIMEOUT_SECONDS", 30),
            recent_exclusion_days=_env_int("HOMEWORK_RECENT_EXCLUSION_DAYS", 30),
            max_generated_per_request=_env_int("HOMEWORK_AI_MAX_GENERATED_PER_REQUEST", 10),
            allow_degraded_result=_env_bool("HOMEWORK_AI_ALLOW_DEGRADED_RESULT", True),
        )

    def generation_cap(self, deficit: int) -> int:
        return max(0, min(deficit, self.max_generated_per_request))
