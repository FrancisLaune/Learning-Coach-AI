"""Small, deterministic services for curriculum import and publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from domain.curriculum.models import CatalogImportReport, CatalogValidationReport, QualityAssessment
from domain.curriculum.repositories import CurriculumRepository
from domain.curriculum.validation import CatalogValidator, assert_acyclic


class CatalogImportConflict(ValueError):
    """Raised when a source identifier/version has conflicting content."""


class CurriculumImportService:
    def __init__(self, repository: CurriculumRepository, validator: CatalogValidator | None = None) -> None:
        self.repository = repository
        self.validator = validator or CatalogValidator()

    def import_file(self, source: Path, *, dry_run: bool = True) -> CatalogImportReport:
        raw = source.read_bytes()
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("Catalog root must be an object")
        report = self.validator.validate(document)
        if not report.valid:
            return CatalogImportReport(
                hashlib.sha256(raw).hexdigest()[:24],
                _rows(document),
                0,
                0,
                0,
                tuple(f"{issue.code}:{issue.entity_code or '-'}" for issue in report.issues if issue.blocking),
                tuple(issue.code for issue in report.issues if not issue.blocking),
                dry_run,
            )
        return self.repository.import_catalog(source, document, hashlib.sha256(raw).hexdigest(), dry_run)


class CurriculumService:
    def __init__(self, repository: CurriculumRepository) -> None:
        self.repository = repository

    def inventory(self) -> dict[str, int]:
        return self.repository.catalog_counts()

    def approved_preview(self, *, subject_code: str | None = None) -> list[dict[str, Any]]:
        return self.repository.catalog_preview(subject_code=subject_code)


class PrerequisiteGraphService:
    @staticmethod
    def validate(relations: list[dict[str, Any]]) -> None:
        assert_acyclic(relations)


class ContentValidationService:
    def __init__(self, validator: CatalogValidator | None = None) -> None:
        self.validator = validator or CatalogValidator()

    def validate(self, document: dict[str, Any]) -> CatalogValidationReport:
        return self.validator.validate(document)


class ContentQualityService:
    def __init__(self, validator: CatalogValidator | None = None) -> None:
        self.validator = validator or CatalogValidator()

    def assess(self, content: dict[str, Any], report: CatalogValidationReport) -> QualityAssessment:
        return self.validator.quality(content, report)


class EditorialWorkflowService:
    transitions = {
        "draft": {"review", "archived"},
        "review": {"draft", "approved", "archived"},
        "approved": {"archived"},
        "archived": set(),
    }

    def transition(self, current: str, target: str, *, validated: bool) -> str:
        if target not in self.transitions.get(current, set()):
            raise ValueError(f"Invalid editorial transition: {current} -> {target}")
        if target == "approved" and not validated:
            raise ValueError("Approval requires complete validation")
        return target


class ContentApprovalService:
    @staticmethod
    def approve(*, author: str, reviewer: str, approver: str, validated: bool) -> bool:
        if not validated:
            raise ValueError("Approval requires complete validation")
        if author in {reviewer, approver}:
            raise ValueError("Role separation prevents self-approval")
        return True


class ApprovedContentCatalogService(CurriculumService):
    """Named facade used by administration and recommendation integration."""


def _rows(document: dict[str, Any]) -> int:
    keys = ("programs", "chapters", "skills", "subskills", "relations", "exam_references", "contents")
    return sum(len(document.get(key, [])) for key in keys)
