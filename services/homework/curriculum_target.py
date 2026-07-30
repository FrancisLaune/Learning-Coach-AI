"""Resolve Content Factory curriculum targets from homework requests."""

from __future__ import annotations

from domain.content.factory import CurriculumTarget
from domain.unified_experience.models import HomeworkRequest
from infrastructure.database.v2 import connect_v2


class HomeworkCurriculumTargetRepository:
    @property
    def database_path(self): ...


def resolve_curriculum_target(repository: HomeworkCurriculumTargetRepository, request: HomeworkRequest) -> CurriculumTarget:
    targets = resolve_curriculum_targets(repository, request)
    return targets[0]


def resolve_curriculum_targets(
    repository: HomeworkCurriculumTargetRepository,
    request: HomeworkRequest,
) -> tuple[CurriculumTarget, ...]:
    if request.grade_level_id is None:
        raise ValueError("HOMEWORK_GRADE_REQUIRED")
    connection = connect_v2(repository.database_path, read_only=True)
    try:
        filters: list[str] = []
        parameters: list[object] = [request.subject_id, request.grade_level_id]
        if request.chapter_ids:
            filters.append(f"cc.id IN ({','.join('?' for _ in request.chapter_ids)})")
            parameters.extend(request.chapter_ids)
        if request.skill_ids:
            filters.append(f"s.id IN ({','.join('?' for _ in request.skill_ids)})")
            parameters.extend(request.skill_ids)
        filter_sql = f" AND {' AND '.join(filters)}" if filters else ""
        rows = connection.execute(
            f"""
            SELECT DISTINCT p.code, sl.code, su.code, cc.stable_code, s.code
            FROM curriculum_chapters cc
            JOIN programs p ON p.id=cc.program_id
            JOIN school_levels sl ON sl.id=cc.grade_level_id
            JOIN subjects su ON su.id=cc.subject_id
            JOIN curriculum_skill_details csd
                ON csd.chapter_id=cc.id AND csd.grade_level_id=cc.grade_level_id AND csd.status='approved'
            JOIN skills s ON s.id=csd.skill_id
            WHERE su.id=? AND sl.id=? AND cc.status='approved'
            {filter_sql}
            ORDER BY cc.sequence_order, s.code
            """,
            parameters,
        ).fetchall()
        if not rows:
            raise ValueError("HOMEWORK_CURRICULUM_TARGET_NOT_FOUND")
        return tuple(
            CurriculumTarget(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4])) for row in rows
        )
    finally:
        connection.close()
