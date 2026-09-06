"""search_exercises API — no blocking difficulty filter (LCAI-0021 / 0032)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore


@dataclass(frozen=True, slots=True)
class ExerciseHit:
    content_id: int
    subject_id: int
    chapter_id: int | None
    title: str
    statement: str
    source_type: str
    difficulty_label: str | None
    brevet_format: str | None
    validation_status: str
    curriculum_2027_compatible: str


def search_exercises(
    *,
    subject_id: int | None = None,
    chapter_ids: list[int] | tuple[int, ...] | None = None,
    skill_ids: list[int] | tuple[int, ...] | None = None,
    formats: list[str] | tuple[str, ...] | None = None,
    source_types: list[str] | tuple[str, ...] | None = None,
    student_id: int | None = None,
    unseen_preferred: bool = True,
    runtime_playable: bool = True,
    limit: int = 50,
    store: BrevetContentStore | None = None,
) -> tuple[ExerciseHit, ...]:
    """Search playable exercises. Difficulty is never a required hard filter."""
    _ = student_id, unseen_preferred  # history hook reserved for StudentContentHistoryRepository
    store = store or BrevetContentStore()
    clauses = [
        "ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')",
        "ci.curriculum_2027_compatible IN ('TRUE', 'REVIEW')",
    ]
    params: list[Any] = []
    if runtime_playable:
        clauses.append("ci.runtime_playable = TRUE")
    if subject_id is not None:
        clauses.append("ci.subject_id = ?")
        params.append(subject_id)
    if chapter_ids:
        placeholders = ", ".join("?" for _ in chapter_ids)
        clauses.append(f"ci.chapter_id IN ({placeholders})")
        params.extend(int(x) for x in chapter_ids)
    if skill_ids:
        placeholders = ", ".join("?" for _ in skill_ids)
        clauses.append(
            f"EXISTS (SELECT 1 FROM content_skill_links csl WHERE csl.content_id = ci.content_id AND csl.skill_id IN ({placeholders}))"
        )
        params.extend(int(x) for x in skill_ids)
    if formats:
        placeholders = ", ".join("?" for _ in formats)
        clauses.append(f"ci.brevet_format IN ({placeholders})")
        params.extend(str(x) for x in formats)
    if source_types:
        placeholders = ", ".join("?" for _ in source_types)
        clauses.append(f"ci.source_type IN ({placeholders})")
        params.extend(str(x) for x in source_types)
    # Exclude incompatible-only content from normal homework pools when explicitly FALSE
    clauses.append("ci.curriculum_2027_compatible <> 'FALSE'")
    sql = f"""
        SELECT ci.content_id, ci.subject_id, ci.chapter_id, ci.title, ci.statement,
               ci.source_type, ci.difficulty_label, ci.brevet_format,
               ci.validation_status, ci.curriculum_2027_compatible
        FROM content_items ci
        WHERE {' AND '.join(clauses)}
        ORDER BY ci.content_id
        LIMIT ?
    """
    params.append(int(limit))
    rows = store.fetchall(sql, params)
    return tuple(
        ExerciseHit(
            content_id=int(row[0]),
            subject_id=int(row[1]),
            chapter_id=int(row[2]) if row[2] is not None else None,
            title=str(row[3]),
            statement=str(row[4]),
            source_type=str(row[5]),
            difficulty_label=str(row[6]) if row[6] is not None else None,
            brevet_format=str(row[7]) if row[7] is not None else None,
            validation_status=str(row[8]),
            curriculum_2027_compatible=str(row[9]),
        )
        for row in rows
    )
