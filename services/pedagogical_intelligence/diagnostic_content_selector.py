"""Select real diagnostic catalog content for LCAI-0019."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.pedagogical_intelligence.engine import select_next_diagnostic_skill
from infrastructure.repositories.pedagogical_intelligence import DuckDBPedagogicalIntelligenceRepository


@dataclass(frozen=True, slots=True)
class DiagnosticContentCandidate:
    exercise_id: int
    content_version_id: int
    skill_id: int
    chapter_id: int
    prompt: str
    exercise_type: str
    response_type: str
    expected_answer: Any
    payload: dict[str, Any]


class DiagnosticContentSelector:
    PREFERRED_TYPES = ("diagnostic_activity", "exercise", "exam_practice", "mini_assessment")

    def __init__(self, repository: DuckDBPedagogicalIntelligenceRepository) -> None:
        self.repository = repository

    def select(
        self,
        *,
        run_id: int,
        learner_id: int,
        grade_code: str,
        target_skill_ids: tuple[int, ...],
        confidence_by_skill: dict[int, float],
        assessed_skill_ids: tuple[int, ...],
        used_exercise_ids: tuple[int, ...],
    ) -> DiagnosticContentCandidate | None:
        skill_id = select_next_diagnostic_skill(target_skill_ids, confidence_by_skill, assessed_skill_ids)
        if skill_id is None:
            return None
        return self.repository.load_diagnostic_content(
            skill_id=skill_id,
            grade_code=grade_code,
            excluded_exercise_ids=used_exercise_ids,
            preferred_types=self.PREFERRED_TYPES,
        )
