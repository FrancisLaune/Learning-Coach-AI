"""Provider-independent educational content factory vocabulary."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class CanonicalContentType(StrEnum):
    LESSON = "lesson"
    WORKED_EXAMPLE = "worked_example"
    GUIDED_PRACTICE = "guided_practice"
    PRACTICE = "practice"
    ASSESSMENT = "assessment"
    DIAGNOSTIC = "diagnostic"
    REMEDIATION = "remediation"
    CHALLENGE = "challenge"
    REVISION = "revision"


class PedagogicalIntent(StrEnum):
    INTRODUCE = "introduce"
    MODEL = "model"
    SCAFFOLD = "scaffold"
    PRACTICE = "practice"
    CHECK = "check"
    DIAGNOSE = "diagnose"
    REMEDIATE = "remediate"
    CONSOLIDATE = "consolidate"
    EXTEND = "extend"


class AnswerKind(StrEnum):
    EXACT_TEXT = "exact_text"
    NUMERIC = "numeric"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    BOOLEAN = "boolean"
    STRUCTURED = "structured"
    OPEN_RESPONSE = "open_response"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class CurriculumTarget:
    program_code: str
    grade_code: str
    subject_code: str
    chapter_code: str
    primary_skill_code: str
    subskill_code: str | None = None
    secondary_skill_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DifficultyProfile:
    level: int
    label: str
    autonomy: str
    reasoning: str
    representation: str

    def __post_init__(self) -> None:
        if self.level not in (1, 2, 3):
            raise ValueError("Factory difficulty must be between 1 and 3")


DIFFICULTY_PROFILES = {
    1: DifficultyProfile(1, "foundation", "guided", "direct, one concept", "familiar"),
    2: DifficultyProfile(2, "standard", "normal", "grade-level application", "varied"),
    3: DifficultyProfile(3, "advanced", "independent", "multi-step transfer", "less familiar"),
}


@dataclass(frozen=True, slots=True)
class ContentGenerationRequest:
    target: CurriculumTarget
    content_type: CanonicalContentType
    difficulty: int
    pedagogical_intent: PedagogicalIntent
    quantity: int = 1
    variation_constraints: tuple[str, ...] = ()
    misconception_target: str | None = None
    language_code: str = "fr-FR"

    def __post_init__(self) -> None:
        if self.difficulty not in DIFFICULTY_PROFILES:
            raise ValueError("Factory difficulty must be between 1 and 3")
        if not 1 <= self.quantity <= 100:
            raise ValueError("Generation quantity must be between 1 and 100")
        if not self.target.primary_skill_code.strip():
            raise ValueError("A primary Skill is required")


@dataclass(frozen=True, slots=True)
class GenerationProvenance:
    generator_type: str
    generator_identifier: str
    specification_version: str
    template_version: str
    curriculum_version: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int | None = None
    usage: dict[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnswerSpecification:
    kind: AnswerKind
    expected: Any
    options: tuple[str, ...] = ()
    tolerance: float | None = None
    independently_computed: Any | None = None


@dataclass(frozen=True, slots=True)
class GeneratedContentCandidate:
    code: str
    title: str
    instructions: str
    prompt: str
    answer: AnswerSpecification
    explanation: str
    target: CurriculumTarget
    content_type: CanonicalContentType
    pedagogical_intent: PedagogicalIntent
    difficulty: int
    provenance: GenerationProvenance
    hints: tuple[str, ...] = ()
    feedback: dict[str, str] = field(default_factory=dict)
    family_code: str | None = None
    variant_role: str | None = None
    misconception_target: str | None = None
    language_code: str = "fr-FR"
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentGenerator(Protocol):
    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]: ...


@dataclass(frozen=True, slots=True)
class FactoryValidationIssue:
    stage: str
    code: str
    message: str
    severity: IssueSeverity


@dataclass(frozen=True, slots=True)
class FactoryValidationReport:
    issues: tuple[FactoryValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity is IssueSeverity.ERROR for issue in self.issues)

    def count(self, severity: IssueSeverity) -> int:
        return sum(issue.severity is severity for issue in self.issues)


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    dimensions: dict[str, int]
    score: int
    eligible_for_review: bool
    blocking_errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenerationReport:
    requested: int
    generated: int
    valid: int
    warnings: int
    rejected: int
    duplicates: int
    persisted_as_draft: int
    candidate_codes: tuple[str, ...] = ()
    failure_reasons: tuple[str, ...] = ()


def normalized_content_fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


LEGACY_CONTENT_TYPE_MAP = {
    "exercise": CanonicalContentType.PRACTICE,
    "quiz": CanonicalContentType.ASSESSMENT,
    "multiple_choice_question": CanonicalContentType.ASSESSMENT,
    "open_question": CanonicalContentType.ASSESSMENT,
    "problem": CanonicalContentType.CHALLENGE,
    "revision_sheet": CanonicalContentType.REVISION,
    "method_sheet": CanonicalContentType.LESSON,
    "worked_example": CanonicalContentType.WORKED_EXAMPLE,
    "diagnostic_activity": CanonicalContentType.DIAGNOSTIC,
    "remediation_activity": CanonicalContentType.REMEDIATION,
    "transition_activity": CanonicalContentType.REVISION,
    "exam_practice": CanonicalContentType.ASSESSMENT,
    "mini_assessment": CanonicalContentType.ASSESSMENT,
}
