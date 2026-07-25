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
        document = _expand_curriculum_enrichment(source, document)
        document = _expand_curriculum_packages(document)
        checksum = (
            hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            if document.get("metadata", {}).get("curriculum_enrichment")
            else hashlib.sha256(raw).hexdigest()
        )
        report = self.validator.validate(document)
        if not report.valid:
            return CatalogImportReport(
                checksum[:24],
                _rows(document),
                0,
                0,
                0,
                tuple(f"{issue.code}:{issue.entity_code or '-'}" for issue in report.issues if issue.blocking),
                tuple(issue.code for issue in report.issues if not issue.blocking),
                dry_run,
            )
        return self.repository.import_catalog(source, document, checksum, dry_run)


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

    def quality_metrics(self) -> dict[str, Any]:
        """Return deterministic curriculum granularity metrics."""
        return self.repository.curriculum_quality_metrics()


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


def _expand_curriculum_enrichment(source: Path, document: dict[str, Any]) -> dict[str, Any]:
    """Resolve a reviewable enrichment delta against validated source artifacts."""
    enrichment = document.get("curriculum_enrichment")
    if enrichment is None:
        return document
    merged: dict[str, Any] = {
        "catalog_version": document.get("catalog_version", "1.0"),
        "metadata": document.get("metadata", {}),
        "programs": [],
        "chapters": [],
        "skills": [],
        "subskills": [],
        "relations": [],
        "exam_references": [],
        "contents": [],
    }
    for relative in enrichment.get("base_datasets", []):
        base_path = (source.parent / relative).resolve()
        base = json.loads(base_path.read_text(encoding="utf-8"))
        base = _expand_curriculum_packages(base)
        for key in ("programs", "chapters", "skills", "subskills", "relations", "exam_references"):
            merged[key].extend(base.get(key, []))
    for key in ("programs", "chapters", "skills", "subskills", "relations", "exam_references"):
        merged[key] = _deduplicate(merged[key], _identity_key(key))

    competency_path = enrichment.get("chapter_competency_dataset")
    chapter_competencies: dict[str, list[str]] = {}
    if competency_path:
        chapter_competencies = json.loads((source.parent / competency_path).read_text(encoding="utf-8"))[
            "chapter_competencies"
        ]
    profiles = {item["subject_code"]: item for item in enrichment.get("subject_profiles", [])}
    overrides = {item["chapter_code"]: item for item in enrichment.get("chapter_overrides", [])}
    for chapter in merged["chapters"]:
        explicit = chapter_competencies.get(chapter["code"])
        profile = (
            overrides.get(chapter["code"])
            or (_compact_competency_profile(explicit) if explicit else None)
            or profiles.get(chapter["subject_code"])
        )
        if profile is None:
            continue
        existing_count = sum(1 for skill in merged["skills"] if skill["chapter_code"] == chapter["code"])
        for offset, blueprint in enumerate(profile.get("skills", []), 1):
            skill_code = f"SK-ENR-{chapter['code'].removeprefix('CH-')}-{blueprint['suffix']}"
            context = {"chapter": chapter["title"], "grade": chapter["grade_code"]}
            merged["skills"].append(
                {
                    "code": skill_code,
                    "chapter_code": chapter["code"],
                    "grade_code": chapter["grade_code"],
                    "title": blueprint["title"].format(**context),
                    "description": blueprint["description"].format(**context),
                    "observable_outcome": blueprint["observable_outcome"].format(**context),
                    "sequence_order": existing_count + offset,
                    "difficulty": blueprint.get("difficulty", 3),
                    "importance": blueprint.get("importance", 0.75),
                    "exam_relevant": chapter.get("exam_relevant", False),
                    "transition_relevant": chapter.get("transition_relevant", False),
                    "tags": ["core_skill"],
                }
            )
            for subskill_order, subskill in enumerate(blueprint.get("subskills", []), 1):
                merged["subskills"].append(
                    {
                        "code": f"SUB-ENR-{chapter['code'].removeprefix('CH-')}-{blueprint['suffix']}-{subskill['suffix']}",
                        "skill_code": skill_code,
                        "title": subskill["title"].format(**context),
                        "description": subskill["description"].format(**context),
                        "sequence_order": subskill_order,
                    }
                )
        for relation in profile.get("relations", []):
            source_code = f"SK-ENR-{chapter['code'].removeprefix('CH-')}-{relation['from_suffix']}"
            target_code = f"SK-ENR-{chapter['code'].removeprefix('CH-')}-{relation['to_suffix']}"
            merged["relations"].append(
                {
                    "prerequisite": source_code,
                    "target": target_code,
                    "relation_type": "recommended",
                    "progression_role": "current_level",
                    "strength": relation.get("strength", 0.6),
                    "mandatory": False,
                    "minimum_mastery_threshold": relation.get("minimum_mastery_threshold", 0.6),
                    "rationale": relation["rationale"].format(**context),
                    "source": document["metadata"]["source_label"],
                }
            )
    for key in ("skills", "subskills", "relations"):
        merged[key] = _deduplicate(merged[key], _identity_key(key))
    return merged


def _compact_competency_profile(entries: list[str]) -> dict[str, Any]:
    skills: list[dict[str, Any]] = []
    for entry in entries:
        parts = entry.split("|", 2)
        suffix, title = parts[0], parts[1]
        subskills = []
        if len(parts) == 3 and parts[2]:
            subskills = [
                {
                    "suffix": f"PART{index}",
                    "title": label,
                    "description": f"Diagnostiquer précisément : {label}.",
                }
                for index, label in enumerate(parts[2].split(";"), 1)
            ]
        skills.append(
            {
                "suffix": suffix,
                "title": title,
                "description": f"Compétence disciplinaire ciblée : {title}.",
                "observable_outcome": f"L'apprenant peut {title[0].lower() + title[1:]} dans une tâche vérifiable.",
                "subskills": subskills,
            }
        )
    return {"skills": skills, "relations": []}


def _identity_key(kind: str) -> Any:
    if kind == "relations":
        return lambda item: (item["prerequisite"], item["target"], item["relation_type"])
    return lambda item: item["code"]


def _deduplicate(items: list[dict[str, Any]], key: Any) -> list[dict[str, Any]]:
    unique: dict[Any, dict[str, Any]] = {}
    for item in items:
        unique.setdefault(key(item), item)
    return list(unique.values())
