"""Build learner pedagogical context for homework AI fallback."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Protocol

from domain.unified_experience.models import DifficultyMode, HomeworkRequest, LearnerPedagogicalContext
from infrastructure.database.v2 import connect_v2


class LearnerContextRepository(Protocol):
    @property
    def database_path(self): ...


def _difficulty_band(mode: DifficultyMode, adaptive_level: int | None) -> tuple[int, int]:
    if mode is DifficultyMode.EASY:
        return (1, 2)
    if mode is DifficultyMode.HARD:
        return (2, 3)
    if mode is DifficultyMode.ADAPTIVE and adaptive_level is not None:
        level = max(1, min(3, adaptive_level))
        return (max(1, level - 1), min(3, level))
    return (1, 3)


def _target_difficulty(mode: DifficultyMode, adaptive_level: int | None) -> int:
    if mode is DifficultyMode.EASY:
        return 1
    if mode is DifficultyMode.HARD:
        return 3
    if mode is DifficultyMode.ADAPTIVE and adaptive_level is not None:
        return max(1, min(3, adaptive_level))
    return 2


class LearnerContextService:
    def __init__(self, repository: LearnerContextRepository, *, recent_exclusion_days: int = 30) -> None:
        self.repository = repository
        self.recent_exclusion_days = recent_exclusion_days

    def build(self, request: HomeworkRequest, correlation_id: str) -> LearnerPedagogicalContext:
        connection = connect_v2(self.repository.database_path, read_only=True)
        try:
            subject_row = connection.execute(
                "SELECT code FROM subjects WHERE id=?", [request.subject_id]
            ).fetchone()
            if subject_row is None:
                raise ValueError("SUBJECT_NOT_FOUND")
            subject_code = str(subject_row[0])

            grade_code = "FR-4E"
            if request.grade_level_id is not None:
                grade_row = connection.execute(
                    "SELECT code FROM school_levels WHERE id=?", [request.grade_level_id]
                ).fetchone()
                if grade_row is not None:
                    grade_code = str(grade_row[0])

            adaptive_row = connection.execute(
                """SELECT avg(m.last_difficulty) FROM longitudinal_mastery_current m
                JOIN skills sk ON sk.id=m.skill_id JOIN domains d ON d.id=sk.domain_id
                WHERE m.learner_id=? AND d.subject_id=?""",
                [request.learner_id, request.subject_id],
            ).fetchone()
            adaptive_level = None if not adaptive_row or adaptive_row[0] is None else round(float(adaptive_row[0]))

            mastery_profile = "progressing"
            if adaptive_level is not None:
                if adaptive_level <= 2:
                    mastery_profile = "struggling"
                elif adaptive_level >= 4:
                    mastery_profile = "advanced"

            cutoff = datetime.now(tz=UTC) - timedelta(days=self.recent_exclusion_days)
            recent_ids: list[int] = []
            for row in connection.execute(
                "SELECT selected_content FROM homework_assignments WHERE learner_id=? AND created_at >= ?",
                [request.learner_id, cutoff],
            ).fetchall():
                payload = json.loads(str(row[0]))
                recent_ids.extend(int(item) for item in payload)
            recent_ids_tuple = tuple(dict.fromkeys(recent_ids))

            table_exists = connection.execute(
                """SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema='main' AND table_name='homework_runtime_exercises'"""
            ).fetchone()
            recent_fingerprints: tuple[str, ...] = ()
            if table_exists and int(table_exists[0]):
                recent_fingerprints = tuple(
                    str(row[0])
                    for row in connection.execute(
                        """SELECT DISTINCT content_fingerprint FROM homework_runtime_exercises
                        WHERE learner_id=? AND created_at >= ?""",
                        [request.learner_id, cutoff],
                    ).fetchall()
                )
        finally:
            connection.close()

        target = _target_difficulty(request.difficulty, adaptive_level)
        return LearnerPedagogicalContext(
            request.learner_id,
            grade_code,
            request.subject_id,
            subject_code,
            request.chapter_ids,
            request.skill_ids,
            mastery_profile,
            target,
            _difficulty_band(request.difficulty, adaptive_level),
            recent_fingerprints,
            recent_ids_tuple,
            correlation_id,
        )
