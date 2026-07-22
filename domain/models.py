"""Minimal domain entities; business rules remain in the legacy modules for now."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Learner:
    """Identity exposed to application use cases without persistence details."""

    id: int
    name: str
    role: str


@dataclass(frozen=True, slots=True)
class Subject:
    """Stable application-facing description of an existing subject."""

    code: str
    label: str


@dataclass(frozen=True, slots=True)
class Question:
    """Small immutable view of a legacy question, not the future DuckDB V2 entity."""

    chapter: str
    statement: str
    expected_answer: str
    answer_type: str = "text"
