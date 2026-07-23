"""Stable business types for curriculum publication."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ContentType(StrEnum):
    EXERCISE = "exercise"
    QUIZ = "quiz"
    MULTIPLE_CHOICE_QUESTION = "multiple_choice_question"
    OPEN_QUESTION = "open_question"
    PROBLEM = "problem"
    REVISION_SHEET = "revision_sheet"
    METHOD_SHEET = "method_sheet"
    WORKED_EXAMPLE = "worked_example"
    DIAGNOSTIC_ACTIVITY = "diagnostic_activity"
    REMEDIATION_ACTIVITY = "remediation_activity"
    TRANSITION_ACTIVITY = "transition_activity"
    EXAM_PRACTICE = "exam_practice"
    MINI_ASSESSMENT = "mini_assessment"


class CurriculumRelationType(StrEnum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    REMEDIATION = "remediation"
    TRANSITION = "transition"
    EXAM_DEPENDENCY = "exam_dependency"


class ProgressionRole(StrEnum):
    CURRENT_LEVEL = "current_level"
    PRIOR_GRADE_REMEDIATION = "prior_grade_remediation"
    NEXT_GRADE_PREPARATION = "next_grade_preparation"
    EXAM_PREPARATION = "exam_preparation"
    LONG_TERM_FOUNDATION = "long_term_foundation"


class EditorialRole(StrEnum):
    AUTHOR = "ContentAuthor"
    REVIEWER = "ContentReviewer"
    APPROVER = "ContentApprover"
    ADMINISTRATOR = "ContentAdministrator"


@dataclass(frozen=True, slots=True)
class CatalogValidationIssue:
    code: str
    message: str
    entity_code: str | None = None
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class CatalogValidationReport:
    issues: tuple[CatalogValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.blocking for issue in self.issues)


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    score: int
    level: str
    passed: tuple[str, ...]
    missing: tuple[str, ...]
    blocking_errors: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CatalogImportReport:
    import_identifier: str
    rows_read: int
    created: int
    updated: int
    ignored: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    dry_run: bool
