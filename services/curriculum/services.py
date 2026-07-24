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
        document = _expand_curriculum_packages(document)
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

    def coverage(self, *, grade_code: str | None = None, subject_code: str | None = None) -> list[dict[str, Any]]:
        """Return curriculum nodes even when they have no Approved content."""
        return self.repository.curriculum_coverage(grade_code=grade_code, subject_code=subject_code)


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


def _expand_curriculum_packages(document: dict[str, Any]) -> dict[str, Any]:
    """Expand the compact, reviewable Phase 2 hierarchy into the existing import contract."""
    packages = document.get("curriculum_packages")
    if packages is None:
        return document
    expanded: dict[str, Any] = {
        "catalog_version": document.get("catalog_version", "1.0"),
        "metadata": document.get("metadata", {}),
        "programs": [],
        "chapters": [],
        "skills": [],
        "subskills": [],
        "relations": [],
        "exam_references": document.get("exam_references", []),
        "contents": document.get("contents", []),
    }
    for package in packages:
        program = dict(package["program"])
        subjects = package.get("subjects", [])
        program["subjects"] = [item["code"] for item in subjects]
        expanded["programs"].append(program)
        for subject in subjects:
            for chapter_order, chapter in enumerate(subject.get("chapters", []), 1):
                expanded["chapters"].append(
                    {
                        "code": chapter["code"],
                        "program_code": program["code"],
                        "subject_code": subject["code"],
                        "domain_code": chapter["domain_code"],
                        "grade_code": program["grade_code"],
                        "title": chapter["title"],
                        "description": chapter.get(
                            "description",
                            f"Référence curriculaire validée : {chapter['title']}.",
                        ),
                        "sequence_order": chapter_order,
                        "expected_duration_minutes": chapter.get("expected_duration_minutes", 180),
                        "difficulty_min": chapter.get("difficulty_min", 1),
                        "difficulty_max": chapter.get("difficulty_max", 5),
                        "exam_relevant": chapter.get("exam_relevant", False),
                        "transition_relevant": chapter.get("transition_relevant", False),
                        "effective_from": program["valid_from"],
                    }
                )
                for skill_order, skill in enumerate(chapter.get("skills", []), 1):
                    expanded["skills"].append(
                        {
                            "code": skill["code"],
                            "chapter_code": chapter["code"],
                            "grade_code": program["grade_code"],
                            "title": skill["title"],
                            "description": skill.get(
                                "description",
                                f"Mobiliser les connaissances et méthodes relatives à {chapter['title']}.",
                            ),
                            "observable_outcome": skill.get(
                                "observable_outcome",
                                f"L'apprenant réalise une tâche vérifiable relative à {chapter['title']}.",
                            ),
                            "sequence_order": skill_order,
                            "difficulty": skill.get("difficulty", 3),
                            "importance": skill.get("importance", 0.8),
                            "exam_relevant": chapter.get("exam_relevant", False),
                            "transition_relevant": chapter.get("transition_relevant", False),
                            "tags": skill.get("tags", ["core_skill"]),
                        }
                    )
                    for subskill_order, subskill in enumerate(skill.get("subskills", []), 1):
                        expanded["subskills"].append(
                            {
                                "code": subskill["code"],
                                "skill_code": skill["code"],
                                "title": subskill["title"],
                                "description": subskill.get("description", subskill["title"]),
                                "sequence_order": subskill_order,
                            }
                        )
                    for prerequisite in skill.get("prerequisites", []):
                        prerequisite_code = (
                            prerequisite if isinstance(prerequisite, str) else prerequisite["skill_code"]
                        )
                        details = prerequisite if isinstance(prerequisite, dict) else {}
                        expanded["relations"].append(
                            {
                                "prerequisite": prerequisite_code,
                                "target": skill["code"],
                                "relation_type": details.get("relation_type", "required"),
                                "progression_role": details.get("progression_role", "long_term_foundation"),
                                "strength": details.get("strength", 0.8),
                                "mandatory": details.get("mandatory", True),
                                "minimum_mastery_threshold": details.get("minimum_mastery_threshold", 0.7),
                                "rationale": details.get(
                                    "rationale",
                                    "Progression curriculaire issue du référentiel documenté.",
                                ),
                                "source": details.get(
                                    "source",
                                    document.get("metadata", {}).get("source_label", "official-curriculum"),
                                ),
                            }
                        )
    return expanded
