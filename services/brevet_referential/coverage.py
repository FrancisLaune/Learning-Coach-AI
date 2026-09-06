"""Coverage measurement and ensure_content_coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.materialize import materialize_bank_coverage
from services.brevet_referential.models import coverage_threshold


@dataclass(frozen=True, slots=True)
class SkillCoverage:
    subject: str
    chapter: str
    skill: str
    brevet_importance: str
    total_validated: int
    official_archive_count: int
    archive_derived_count: int
    ai_generated_count: int
    curated_count: int
    unique_formats: int
    coverage_status: str


def measure_coverage(store: BrevetContentStore | None = None) -> tuple[SkillCoverage, ...]:
    store = store or BrevetContentStore()
    rows = store.fetchall(
        """
        SELECT subject, chapter, skill, brevet_importance, total_validated,
               official_archive_count, archive_derived_count, ai_generated_count,
               curated_count, unique_formats, coverage_status
        FROM v_content_coverage
        ORDER BY subject, chapter, skill
        """
    )
    result: list[SkillCoverage] = []
    for row in rows:
        result.append(
            SkillCoverage(
                subject=str(row[0]),
                chapter=str(row[1]),
                skill=str(row[2]),
                brevet_importance=str(row[3]),
                total_validated=int(row[4] or 0),
                official_archive_count=int(row[5] or 0),
                archive_derived_count=int(row[6] or 0),
                ai_generated_count=int(row[7] or 0),
                curated_count=int(row[8] or 0),
                unique_formats=int(row[9] or 0),
                coverage_status=str(row[10]),
            )
        )
    return tuple(result)


def coverage_status_for_skill(skill_code: str, store: BrevetContentStore | None = None) -> SkillCoverage | None:
    for row in measure_coverage(store):
        if row.skill == skill_code:
            return row
    return None


def ensure_content_coverage(skill_id: int, store: BrevetContentStore | None = None) -> dict[str, Any]:
    """Fill deficit for one skill via bank materialization (no live web scrape)."""
    store = store or BrevetContentStore()
    row = store.fetchone(
        """
        SELECT sk.brevet_importance,
               COUNT(DISTINCT ci.content_id) FILTER (
                 WHERE ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
               )
        FROM skills sk
        LEFT JOIN content_skill_links csl ON csl.skill_id = sk.skill_id
        LEFT JOIN content_items ci ON ci.content_id = csl.content_id
        WHERE sk.skill_id = ?
        GROUP BY sk.brevet_importance
        """,
        [skill_id],
    )
    if row is None:
        return {"skill_id": skill_id, "status": "MISSING"}
    importance = str(row[0])
    total = int(row[1] or 0)
    needed, _ = coverage_threshold(importance)
    if total >= needed:
        return {"skill_id": skill_id, "status": "OK", "total": total, "needed": needed}
    stats = materialize_bank_coverage(store)
    after = store.fetchone(
        """
        SELECT COUNT(DISTINCT ci.content_id)
        FROM content_skill_links csl
        JOIN content_items ci ON ci.content_id = csl.content_id
        WHERE csl.skill_id = ? AND ci.validation_status IN ('AUTO_VALIDATED', 'APPROVED')
        """,
        [skill_id],
    )
    return {
        "skill_id": skill_id,
        "status": "FILLED",
        "before": total,
        "after": int(after[0] if after else 0),
        "needed": needed,
        "materialize": stats,
    }
