"""Framework-independent content-management vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any


class ValidationStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class Difficulty(IntEnum):
    VERY_EASY = 1
    EASY = 2
    MEDIUM = 3
    HARD = 4
    VERY_HARD = 5


@dataclass(frozen=True, slots=True)
class Version:
    number: int
    author: str
    status: ValidationStatus = ValidationStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    modified_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class Program:
    code: str
    label: str
    country_code: str
    version: Version


@dataclass(frozen=True, slots=True)
class Subject:
    code: str
    label: str


@dataclass(frozen=True, slots=True)
class Domain:
    code: str
    label: str
    subject_code: str


@dataclass(frozen=True, slots=True)
class Prerequisite:
    skill_code: str
    required_skill_code: str


@dataclass(frozen=True, slots=True)
class Skill:
    code: str
    label: str
    domain_code: str
    prerequisites: tuple[Prerequisite, ...] = ()


@dataclass(frozen=True, slots=True)
class SubSkill:
    code: str
    label: str
    skill_code: str


@dataclass(frozen=True, slots=True)
class Objective:
    code: str
    title: str
    skill_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Answer:
    value: Any
    kind: str = "text"


@dataclass(frozen=True, slots=True)
class Explanation:
    text: str


@dataclass(frozen=True, slots=True)
class Hint:
    text: str
    position: int = 1


@dataclass(frozen=True, slots=True)
class Tag:
    code: str
    label: str


@dataclass(frozen=True, slots=True)
class Media:
    code: str
    kind: str
    uri: str
    title: str = ""
    mime_type: str | None = None


@dataclass(frozen=True, slots=True)
class CompetencyMapping:
    skill_code: str
    weight: float = 1.0
    primary: bool = False


@dataclass(frozen=True, slots=True)
class Question:
    code: str
    statement: str
    answer: Answer
    explanation: Explanation
    difficulty: Difficulty
    mappings: tuple[CompetencyMapping, ...]
    hints: tuple[Hint, ...] = ()
    tags: tuple[Tag, ...] = ()
    media: tuple[Media, ...] = ()
    version: Version | None = None


@dataclass(frozen=True, slots=True)
class Exercise:
    code: str
    title: str
    objective: str
    subject_code: str
    difficulty: Difficulty
    questions: tuple[Question, ...]
    tags: tuple[Tag, ...] = ()
    media: tuple[Media, ...] = ()
    version: Version | None = None


@dataclass(frozen=True, slots=True)
class ContentDocument:
    programs: tuple[Program, ...] = ()
    subjects: tuple[Subject, ...] = ()
    domains: tuple[Domain, ...] = ()
    skills: tuple[Skill, ...] = ()
    subskills: tuple[SubSkill, ...] = ()
    exercises: tuple[Exercise, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
