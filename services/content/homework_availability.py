"""Homework content availability for 4e subjects (LCAI-0018)."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.unified_experience.models import (
    AssignmentType,
    DifficultyMode,
    HomeworkRequest,
    SubjectHomeworkAvailability,
)
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository


def _status_labels(eligible_count: int) -> tuple[str, str]:
    if eligible_count >= 10:
        return "available", "Disponible"
    if eligible_count >= 1:
        return "limited", "Couverture limitée"
    return "unavailable", "Indisponible"


class HomeworkAvailabilityService:
    def __init__(self, repository: DuckDBUnifiedExperienceRepository) -> None:
        self.repository = repository

    def list_for_grade(
        self,
        grade_level_id: int,
        *,
        exercise_count: int = 10,
    ) -> tuple[SubjectHomeworkAvailability, ...]:
        subjects = self.repository.curriculum_subjects_for_grade(grade_level_id)
        output: list[SubjectHomeworkAvailability] = []
        for subject_id, subject_code, subject_label in subjects:
            production_count = self.repository.production_count_for_subject(grade_level_id, int(subject_id))
            chapters_total = len(self.repository.curriculum_chapters(int(subject_id), grade_level_id))
            chapters_with_content = len(self.repository.chapters(int(subject_id), grade_level_id))
            preview = self.repository.select_approved_content_detailed(
                HomeworkRequest(
                    0,
                    "SYSTEM",
                    "lcai-0018-audit",
                    AssignmentType.GLOBAL_SUBJECT,
                    int(subject_id),
                    grade_level_id,
                    (),
                    (),
                    DifficultyMode.MEDIUM,
                    max(exercise_count, 40),
                    None,
                    datetime.now(tz=UTC),
                )
            )
            eligible_count = len(preview.content_ids)
            status, label = _status_labels(eligible_count)
            output.append(
                SubjectHomeworkAvailability(
                    subject_id=int(subject_id),
                    subject_code=str(subject_code),
                    subject_label=str(subject_label),
                    production_count=production_count,
                    eligible_count=eligible_count,
                    chapters_with_content=chapters_with_content,
                    chapters_total=chapters_total,
                    availability_status=status,
                    homework_status_label=label,
                )
            )
        return tuple(output)

    def list_for_learner(
        self,
        learner_id: int,
        *,
        actor_type: str = "STUDENT",
        actor_ref: str = "student",
        exercise_count: int = 10,
    ) -> tuple[SubjectHomeworkAvailability, ...]:
        grade_id = self.repository.learner_grade_id(learner_id)
        subjects = self.repository.curriculum_subjects_for_grade(grade_id)
        output: list[SubjectHomeworkAvailability] = []
        for subject_id, subject_code, subject_label in subjects:
            production_count = self.repository.production_count_for_subject(grade_id, int(subject_id))
            chapters_total = len(self.repository.curriculum_chapters(int(subject_id), grade_id))
            chapters_with_content = len(self.repository.chapters(int(subject_id), grade_id))
            preview = self.repository.select_approved_content_detailed(
                HomeworkRequest(
                    learner_id,
                    actor_type,
                    actor_ref,
                    AssignmentType.GLOBAL_SUBJECT,
                    int(subject_id),
                    grade_id,
                    (),
                    (),
                    DifficultyMode.MEDIUM,
                    max(exercise_count, 40),
                    None,
                    datetime.now(tz=UTC),
                )
            )
            eligible_count = len(preview.content_ids)
            status, label = _status_labels(eligible_count)
            output.append(
                SubjectHomeworkAvailability(
                    subject_id=int(subject_id),
                    subject_code=str(subject_code),
                    subject_label=str(subject_label),
                    production_count=production_count,
                    eligible_count=eligible_count,
                    chapters_with_content=chapters_with_content,
                    chapters_total=chapters_total,
                    availability_status=status,
                    homework_status_label=label,
                )
            )
        return tuple(output)

    def get(
        self,
        learner_id: int,
        subject_id: int,
        *,
        actor_type: str = "STUDENT",
        actor_ref: str = "student",
        exercise_count: int = 10,
    ) -> SubjectHomeworkAvailability | None:
        for item in self.list_for_learner(
            learner_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            exercise_count=exercise_count,
        ):
            if item.subject_id == subject_id:
                return item
        return None
