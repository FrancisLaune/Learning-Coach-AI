"""Backward-compatible exports — implementation in completion.py (LCAI-0018B6)."""

from __future__ import annotations

from services.homework.completion import (
    HomeworkAiFallbackOrchestrator,
    HomeworkContentCompletionService,
    HomeworkRuntimeRepository,
    new_correlation_id,
)

__all__ = (
    "HomeworkAiFallbackOrchestrator",
    "HomeworkContentCompletionService",
    "HomeworkRuntimeRepository",
    "new_correlation_id",
)
