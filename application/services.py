"""Application dependency container for gradual use-case extraction."""

from __future__ import annotations

from dataclasses import dataclass

from application.ports import ProgressReader, UserReader


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    """Repositories consumed by application orchestration."""

    users: UserReader
    progress: ProgressReader
