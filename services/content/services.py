"""Use cases for import, validation, versioning and search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from domain.content.models import ContentDocument, ValidationStatus
from domain.content.repositories import (
    ContentSearchRepository,
    ContentUnitOfWork,
    ValidationRepository,
    VersionRepository,
)
from domain.content.validation import ContentValidator, ValidationReport
from services.content.importers import ImporterRegistry


class ContentImportService:
    def __init__(self, unit_of_work: ContentUnitOfWork, registry: ImporterRegistry | None = None) -> None:
        self.unit_of_work = unit_of_work
        self.registry = registry or ImporterRegistry.defaults()

    def import_file(self, source: Path, author: str) -> dict[str, int]:
        document = self.registry.for_source(source).load(source)
        return self.unit_of_work.persist(document, author)


class ContentValidationService:
    def __init__(
        self, repository: ValidationRepository | None = None, validator: ContentValidator | None = None
    ) -> None:
        self.repository = repository
        self.validator = validator or ContentValidator()

    def validate(self, document: ContentDocument, source_name: str = "memory") -> ValidationReport:
        report = self.validator.validate(document)
        if self.repository is not None:
            self.repository.save(source_name, report)
        return report


class ContentVersionService:
    _transitions = {
        ValidationStatus.DRAFT: {ValidationStatus.REVIEW, ValidationStatus.ARCHIVED},
        ValidationStatus.REVIEW: {ValidationStatus.APPROVED, ValidationStatus.DRAFT, ValidationStatus.ARCHIVED},
        ValidationStatus.APPROVED: {ValidationStatus.ARCHIVED},
        ValidationStatus.ARCHIVED: set(),
    }

    def __init__(self, repository: VersionRepository) -> None:
        self.repository = repository

    def create(self, entity_type: str, entity_id: int, payload: dict[str, Any], author: str) -> int:
        return self.repository.create(entity_type, entity_id, payload, author, ValidationStatus.DRAFT)

    def transition(self, version_id: int, current: ValidationStatus, target: ValidationStatus, author: str) -> None:
        if target not in self._transitions[current]:
            raise ValueError(f"Invalid content transition: {current.value} -> {target.value}")
        self.repository.transition(version_id, target, author)

    def history(self, entity_type: str, entity_id: int) -> list[dict[str, Any]]:
        return self.repository.history(entity_type, entity_id)


class ContentSearchService:
    def __init__(self, repository: ContentSearchRepository) -> None:
        self.repository = repository

    def search(self, **criteria: Any) -> list[dict[str, Any]]:
        return self.repository.search(**criteria)
