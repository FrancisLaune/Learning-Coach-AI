"""Ports for curriculum persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from domain.curriculum.models import CatalogImportReport


class CurriculumRepository(Protocol):
    def import_catalog(
        self, source: Path, document: dict[str, Any], checksum: str, dry_run: bool
    ) -> CatalogImportReport: ...

    def catalog_counts(self) -> dict[str, int]: ...
    def catalog_preview(self, *, subject_code: str | None = None) -> list[dict[str, Any]]: ...


ChapterRepository = CurriculumRepository
SkillRepository = CurriculumRepository
PrerequisiteGraphRepository = CurriculumRepository
ExamReferenceRepository = CurriculumRepository
LearningContentRepository = CurriculumRepository
ContentQuestionRepository = CurriculumRepository
ContentSolutionRepository = CurriculumRepository
ContentValidationRepository = CurriculumRepository
EditorialWorkflowRepository = CurriculumRepository
ContentImportRepository = CurriculumRepository
