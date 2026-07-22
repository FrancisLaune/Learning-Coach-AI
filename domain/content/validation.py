"""Composable validation pipeline for normalized pedagogical content."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from domain.content.models import ContentDocument


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity
    entity_type: str | None = None
    entity_code: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity is Severity.ERROR for issue in self.issues)

    def count(self, severity: Severity) -> int:
        return sum(issue.severity is severity for issue in self.issues)


class ContentRule(Protocol):
    def check(self, document: ContentDocument) -> list[ValidationIssue]: ...


def _all_codes(document: ContentDocument) -> list[tuple[str, str]]:
    groups = (
        ("program", document.programs),
        ("subject", document.subjects),
        ("domain", document.domains),
        ("skill", document.skills),
        ("subskill", document.subskills),
        ("exercise", document.exercises),
    )
    result = [(kind, item.code) for kind, items in groups for item in items]
    result.extend(("question", question.code) for exercise in document.exercises for question in exercise.questions)
    return result


class UniqueIdentifierRule:
    def check(self, document: ContentDocument) -> list[ValidationIssue]:
        keys = _all_codes(document)
        counts = Counter(keys)
        return [
            ValidationIssue("duplicate_identifier", f"Duplicate {kind} identifier: {code}", Severity.ERROR, kind, code)
            for (kind, code), count in counts.items()
            if count > 1
        ]


class ReferenceRule:
    def check(self, document: ContentDocument) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        subjects = {item.code for item in document.subjects}
        domains = {item.code for item in document.domains}
        skills = {item.code for item in document.skills}
        for domain in document.domains:
            if domain.subject_code not in subjects:
                issues.append(
                    ValidationIssue(
                        "broken_subject", "Domain references an unknown subject", Severity.ERROR, "domain", domain.code
                    )
                )
        for skill in document.skills:
            if skill.domain_code not in domains:
                issues.append(
                    ValidationIssue(
                        "broken_domain", "Skill references an unknown domain", Severity.ERROR, "skill", skill.code
                    )
                )
            for prerequisite in skill.prerequisites:
                if prerequisite.required_skill_code not in skills:
                    issues.append(
                        ValidationIssue(
                            "missing_prerequisite", "Unknown prerequisite skill", Severity.ERROR, "skill", skill.code
                        )
                    )
        for exercise in document.exercises:
            if exercise.subject_code not in subjects:
                issues.append(
                    ValidationIssue(
                        "broken_subject",
                        "Exercise references an unknown subject",
                        Severity.ERROR,
                        "exercise",
                        exercise.code,
                    )
                )
            for question in exercise.questions:
                for mapping in question.mappings:
                    if mapping.skill_code not in skills:
                        issues.append(
                            ValidationIssue(
                                "broken_skill",
                                "Question references an unknown skill",
                                Severity.ERROR,
                                "question",
                                question.code,
                            )
                        )
                for media in question.media:
                    if not media.uri.strip():
                        issues.append(
                            ValidationIssue(
                                "broken_media", "Media URI is empty", Severity.ERROR, "question", question.code
                            )
                        )
        return issues


class CompletenessRule:
    def check(self, document: ContentDocument) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for exercise in document.exercises:
            if not exercise.questions:
                issues.append(
                    ValidationIssue(
                        "exercise_without_question",
                        "Exercise has no question",
                        Severity.ERROR,
                        "exercise",
                        exercise.code,
                    )
                )
            for question in exercise.questions:
                if question.answer.value in (None, "", [], {}):
                    issues.append(
                        ValidationIssue(
                            "question_without_answer",
                            "Question has no coherent answer",
                            Severity.ERROR,
                            "question",
                            question.code,
                        )
                    )
                if not question.statement.strip() or not question.explanation.text.strip():
                    issues.append(
                        ValidationIssue(
                            "incomplete_question",
                            "Statement or explanation is missing",
                            Severity.ERROR,
                            "question",
                            question.code,
                        )
                    )
                if not question.mappings:
                    issues.append(
                        ValidationIssue(
                            "orphan_question",
                            "Question has no competency mapping",
                            Severity.ERROR,
                            "question",
                            question.code,
                        )
                    )
        used_skills = {m.skill_code for e in document.exercises for q in e.questions for m in q.mappings}
        for skill in document.skills:
            if skill.code not in used_skills:
                issues.append(
                    ValidationIssue(
                        "unused_skill", "Skill is not used by a question", Severity.WARNING, "skill", skill.code
                    )
                )
        return issues


class DuplicateContentRule:
    def check(self, document: ContentDocument) -> list[ValidationIssue]:
        statements = Counter(q.statement.strip().casefold() for e in document.exercises for q in e.questions)
        return [
            ValidationIssue("duplicate_question", "Duplicate question statement", Severity.WARNING)
            for text, count in statements.items()
            if text and count > 1
        ]


class VersionAndTagRule:
    def check(self, document: ContentDocument) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        versioned = [
            *((item.code, item.version) for item in document.programs),
            *((item.code, item.version) for item in document.exercises),
            *((item.code, item.version) for exercise in document.exercises for item in exercise.questions),
        ]
        for code, version in versioned:
            if version is not None and (version.number < 1 or version.modified_at < version.created_at):
                issues.append(
                    ValidationIssue(
                        "incoherent_version",
                        "Content version dates or number are incoherent",
                        Severity.ERROR,
                        entity_code=code,
                    )
                )
        declared_tags = {str(tag) for tag in document.metadata.get("tags", [])}
        used_tags = {tag.code for exercise in document.exercises for tag in exercise.tags}
        used_tags.update(
            tag.code for exercise in document.exercises for question in exercise.questions for tag in question.tags
        )
        for tag in sorted(declared_tags - used_tags):
            issues.append(ValidationIssue("unused_tag", "Declared tag is unused", Severity.WARNING, "tag", tag))
        return issues


class ContentValidator:
    def __init__(self, rules: tuple[ContentRule, ...] | None = None) -> None:
        self.rules = rules or (
            UniqueIdentifierRule(),
            ReferenceRule(),
            CompletenessRule(),
            DuplicateContentRule(),
            VersionAndTagRule(),
        )

    def validate(self, document: ContentDocument) -> ValidationReport:
        return ValidationReport(tuple(issue for rule in self.rules for issue in rule.check(document)))
