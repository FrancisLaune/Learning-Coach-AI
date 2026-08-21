"""Anti-repetition and brevet preference for homework selection (LCAI-0030-D)."""

from __future__ import annotations

from typing import Any

CatalogRow = tuple[Any, ...]

_BREVET_CONTENT_TYPES = frozenset({"exam_practice", "mini_assessment"})


def exclude_recent_content_ids(
    rows: list[CatalogRow],
    recent_ids: set[int] | frozenset[int] | tuple[int, ...],
) -> list[CatalogRow]:
    """Drop recently served content ids; fall back to full pool if empty."""
    if not rows or not recent_ids:
        return list(rows)
    excluded = {int(item) for item in recent_ids}
    filtered = [row for row in rows if int(row[0]) not in excluded]
    return filtered if filtered else list(rows)


def prioritize_brevet_content(
    rows: list[CatalogRow],
    *,
    grade_code: str | None,
    exam_skill_ids: set[int] | frozenset[int] | None = None,
) -> list[CatalogRow]:
    """For FR-3E, prefer exam_practice / exam-linked skills without dropping others."""
    if not rows or (grade_code or "").upper() not in {"FR-3E", "3E"}:
        return list(rows)
    exam_skills = {int(item) for item in (exam_skill_ids or ())}

    def sort_key(row: CatalogRow) -> tuple[int, int, int, int, int]:
        content_type = str(row[4]).casefold() if len(row) > 4 and row[4] is not None else ""
        skill_id = int(row[2])
        brevet_rank = 0 if content_type in _BREVET_CONTENT_TYPES else 1
        exam_skill_rank = 0 if skill_id in exam_skills else 1
        return (brevet_rank, exam_skill_rank, int(row[1]), skill_id, int(row[0]))

    return sorted(rows, key=sort_key)
