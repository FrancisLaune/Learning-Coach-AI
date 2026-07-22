"""Ports used by content services; adapters live in infrastructure."""

from __future__ import annotations

from typing import Any, Protocol

from domain.content.models import ContentDocument, ValidationStatus
from domain.content.validation import ValidationReport


class EntityRepository(Protocol):
    def upsert(self, payload: dict[str, Any]) -> int: ...
    def get(self, code: str) -> dict[str, Any] | None: ...


class ProgramRepository(EntityRepository, Protocol): ...


class SubjectRepository(EntityRepository, Protocol): ...


class SkillRepository(EntityRepository, Protocol): ...


class ExerciseRepository(EntityRepository, Protocol): ...


class QuestionRepository(EntityRepository, Protocol): ...


class MediaRepository(EntityRepository, Protocol): ...


class VersionRepository(Protocol):
    def create(
        self, entity_type: str, entity_id: int, payload: dict[str, Any], author: str, status: ValidationStatus
    ) -> int: ...
    def history(self, entity_type: str, entity_id: int) -> list[dict[str, Any]]: ...
    def transition(self, version_id: int, status: ValidationStatus, author: str) -> None: ...


class ValidationRepository(Protocol):
    def save(self, source_name: str, report: ValidationReport) -> int: ...


class ContentUnitOfWork(Protocol):
    def persist(self, document: ContentDocument, author: str) -> dict[str, int]: ...


class ContentSearchRepository(Protocol):
    def search(
        self,
        *,
        subject: str | None = None,
        skill: str | None = None,
        level: str | None = None,
        keyword: str | None = None,
        tags: tuple[str, ...] = (),
        difficulty: int | None = None,
    ) -> list[dict[str, Any]]: ...
