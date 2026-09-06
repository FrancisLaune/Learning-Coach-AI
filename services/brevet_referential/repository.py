"""Canonical pedagogical content access for 3e/DNB (LCAI-0034)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore


@dataclass(frozen=True, slots=True)
class ContentFilters:
    subject_code: str | None = None
    skill_code: str | None = None
    source_types: tuple[str, ...] | None = None
    playable_only: bool = True
    max_per_family: int = 1
    limit: int = 50


class PedagogicalContentRepository:
    """Single access point for objectif_brevet canonical 3e/DNB content."""

    def __init__(self, store: BrevetContentStore | None = None, db_path: Path | None = None) -> None:
        self.store = store or BrevetContentStore(db_path)

    def get_content(self, content_id: int) -> dict[str, Any] | None:
        row = self.store.fetchone(
            """
            SELECT c.content_id, c.source_type, c.title, c.statement, c.expected_answer, c.correction,
                   c.difficulty_label, c.brevet_format, c.curriculum_2027_compatible, c.runtime_playable,
                   c.family_id, c.canonical_content_id, s.code, sk.code
            FROM content_items c
            JOIN subjects s ON s.subject_id = c.subject_id
            LEFT JOIN content_skill_links l ON l.content_id=c.content_id AND l.relation_type='PRIMARY'
            LEFT JOIN skills sk ON sk.skill_id=l.skill_id
            WHERE c.content_id=?
            """,
            [content_id],
        )
        if not row:
            return None
        return {
            "content_id": row[0],
            "source_type": row[1],
            "title": row[2],
            "statement": row[3],
            "expected_answer": row[4],
            "correction": row[5],
            "difficulty": row[6],
            "brevet_format": row[7],
            "curriculum_2027_compatible": row[8],
            "runtime_playable": row[9],
            "family_id": row[10],
            "canonical_content_id": row[11],
            "subject": row[12],
            "skill_code": row[13],
        }

    def find_for_skill(self, skill_code: str, filters: ContentFilters | None = None) -> list[dict[str, Any]]:
        filters = filters or ContentFilters(skill_code=skill_code)
        return self._search(filters=ContentFilters(
            subject_code=filters.subject_code,
            skill_code=skill_code,
            source_types=filters.source_types,
            playable_only=filters.playable_only,
            max_per_family=filters.max_per_family,
            limit=filters.limit,
        ))

    def find_for_homework(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        return self._search(
            filters=ContentFilters(
                subject_code=request.get("subject_code"),
                skill_code=request.get("skill_code"),
                source_types=tuple(request["source_types"]) if request.get("source_types") else None,
                playable_only=True,
                max_per_family=int(request.get("max_per_family", 1)),
                limit=int(request.get("limit", 50)),
            )
        )

    def find_archive_questions(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        params: list[Any] = []
        clauses = ["c.source_type='OFFICIAL_ARCHIVE'"]
        if request.get("year") is not None:
            clauses.append("a.year=?")
            params.append(request["year"])
        if request.get("subject_code"):
            clauses.append("s.code=?")
            params.append(request["subject_code"])
        sql = f"""
            SELECT c.content_id, c.statement, a.year, a.session, a.zone, a.source_provider,
                   a.official_source_url, q.archive_question_id
            FROM content_items c
            JOIN exam_archive_questions_ref q ON q.content_id=c.content_id
            JOIN exam_archive_sections_ref sec ON sec.section_id=q.section_id
            JOIN exam_archives_ref a ON a.archive_id=sec.archive_id
            JOIN subjects s ON s.subject_id=c.subject_id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.year, q.archive_question_id
            LIMIT ?
        """
        params.append(int(request.get("limit", 50)))
        rows = self.store.fetchall(sql, params)
        return [
            {
                "content_id": r[0],
                "statement": r[1],
                "year": r[2],
                "session": r[3],
                "zone": r[4],
                "source_provider": r[5],
                "source_url": r[6],
                "archive_question_id": r[7],
            }
            for r in rows
        ]

    def find_revision_content(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        return self.find_for_homework({**request, "source_types": request.get("source_types")})

    def find_derived_of_archive(self, *, subject_code: str = "MATHEMATICS") -> dict[str, Any] | None:
        """DoD helper: return one ARCHIVE_DERIVED with full provenance chain."""
        row = self.store.fetchone(
            """
            SELECT c.content_id, c.source_type, d.parent_question_id, d.parent_archive_id,
                   a.year, a.session, a.zone, COALESCE(a.source_provider, 'EDUSCOL'), a.official_source_url,
                   sk.code, c.curriculum_2027_compatible
            FROM v_content_items_effective c
            JOIN content_derivations d ON d.derived_content_id = c.content_id
            JOIN exam_archives_ref a ON a.archive_id = d.parent_archive_id
            JOIN subjects s ON s.subject_id = c.subject_id
            LEFT JOIN content_skill_links l ON l.content_id=c.content_id AND l.relation_type='PRIMARY'
            LEFT JOIN skills sk ON sk.skill_id=l.skill_id
            WHERE c.source_type='ARCHIVE_DERIVED' AND s.code=? AND d.parent_question_id IS NOT NULL
            ORDER BY c.content_id
            LIMIT 1
            """,
            [subject_code],
        )
        if not row:
            return None
        return {
            "exercice_id": row[0],
            "source_type": row[1],
            "parent_question_id": row[2],
            "parent_archive_id": row[3],
            "year": row[4],
            "session": row[5],
            "zone": row[6],
            "source_provider": row[7],
            "eduscol_url": row[8],
            "skill_code": row[9],
            "curriculum_2027_compatible": row[10],
        }

    def get_validated_official_questions(
        self,
        *,
        subject_code: str | None = None,
        skill_code: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = ["e.pedagogical_validation_status = 'VALIDATED'", "e.source_type = 'OFFICIAL_ARCHIVE'"]
        params: list[Any] = []
        if subject_code:
            clauses.append("s.code = ?")
            params.append(subject_code)
        if skill_code:
            clauses.append("e.primary_skill_code = ?")
            params.append(skill_code)
        sql = f"""
            SELECT e.content_id, e.statement, e.subject_group, e.primary_skill_code,
                   e.curriculum_2027_compatible, e.pedagogical_reliability_score, e.reliability_class
            FROM v_official_pedagogical_effective e
            JOIN subjects s ON s.subject_id = e.subject_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.pedagogical_reliability_score DESC NULLS LAST, e.content_id
            LIMIT ?
        """
        params.append(limit)
        return [
            {
                "content_id": r[0],
                "statement": r[1],
                "subject_group": r[2],
                "skill_code": r[3],
                "curriculum_2027_compatible": r[4],
                "reliability_score": r[5],
                "reliability_class": r[6],
            }
            for r in self.store.fetchall(sql, params)
        ]

    def get_2027_compatible_questions(
        self,
        *,
        subject_code: str | None = None,
        certified_only: bool = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = [
            "e.source_type = 'OFFICIAL_ARCHIVE'",
            "e.curriculum_2027_compatible = 'TRUE'",
            "e.runtime_playable = TRUE",
        ]
        params: list[Any] = []
        if certified_only:
            clauses.append("e.pedagogical_validation_status = 'VALIDATED'")
        if subject_code:
            clauses.append("s.code = ?")
            params.append(subject_code)
        sql = f"""
            SELECT e.content_id, e.statement, e.primary_skill_code, e.compatibility_reason,
                   e.pedagogical_reliability_score
            FROM v_official_pedagogical_effective e
            JOIN subjects s ON s.subject_id = e.subject_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.pedagogical_reliability_score DESC NULLS LAST
            LIMIT ?
        """
        params.append(limit)
        return [
            {
                "content_id": r[0],
                "statement": r[1],
                "skill_code": r[2],
                "compatibility_reason": r[3],
                "reliability_score": r[4],
            }
            for r in self.store.fetchall(sql, params)
        ]

    def get_questions_requiring_review(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            """
            SELECT question_id, subject, year, skill, issue_type, priority,
                   mapping_confidence, compatibility_confidence, reliability_score, warnings
            FROM v_pedagogical_review_queue
            ORDER BY priority DESC NULLS LAST, question_id
            LIMIT ?
            """,
            [limit],
        )
        return [
            {
                "question_id": r[0],
                "subject": r[1],
                "year": r[2],
                "skill": r[3],
                "issue_type": r[4],
                "priority": r[5],
                "mapping_confidence": r[6],
                "compatibility_confidence": r[7],
                "reliability_score": r[8],
                "warnings": r[9],
            }
            for r in rows
        ]

    def get_reliability_score(self, content_id: int) -> dict[str, Any] | None:
        row = self.store.fetchone(
            """
            SELECT content_id, pedagogical_reliability_score, reliability_class,
                   pedagogical_validation_status, curriculum_2027_compatible
            FROM v_official_pedagogical_effective
            WHERE content_id = ?
            """,
            [content_id],
        )
        if not row:
            return None
        return {
            "content_id": row[0],
            "reliability_score": row[1],
            "reliability_class": row[2],
            "validation_status": row[3],
            "curriculum_2027_compatible": row[4],
        }

    def get_archive_frequency(self, skill_code: str) -> dict[str, Any]:
        row = self.store.fetchone(
            """
            SELECT COUNT(DISTINCT e.content_id), COUNT(DISTINCT ar.year)
            FROM v_official_pedagogical_effective e
            LEFT JOIN exam_archives_ref ar ON ar.archive_id = e.archive_id
            WHERE e.primary_skill_code = ?
            """,
            [skill_code],
        )
        return {
            "skill_code": skill_code,
            "official_question_count": int(row[0]) if row else 0,
            "years_present": int(row[1]) if row else 0,
        }

    def catalog_rows_for_selection(
        self,
        *,
        subject_code: str | None = None,
        limit: int = 500,
        max_per_family: int = 1,
    ) -> list[tuple[Any, ...]]:
        """Shape compatible with homework selection: id, chapter, skill, difficulty, type, minutes, family."""
        items = self._search(
            ContentFilters(
                subject_code=subject_code,
                playable_only=True,
                max_per_family=max_per_family,
                limit=limit,
            )
        )
        rows: list[tuple[Any, ...]] = []
        for item in items:
            diff = {"Facile": 2, "Moyen": 3, "Difficile": 4}.get(str(item.get("difficulty") or "Moyen"), 3)
            rows.append(
                (
                    int(item["content_id"]),
                    int(item.get("chapter_id") or 0),
                    int(item.get("skill_id") or 0),
                    diff,
                    item.get("content_type") or "EXERCISE",
                    int(item.get("estimated_seconds") or 90) // 60 or 1,
                    item.get("family_id"),
                )
            )
        return rows

    def _search(self, filters: ContentFilters) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if filters.playable_only:
            clauses.append("c.runtime_playable")
            clauses.append("c.usage_policy <> 'DUPLICATE_CONSOLIDATED'")
        if filters.subject_code:
            clauses.append("s.code=?")
            params.append(filters.subject_code)
        if filters.skill_code:
            clauses.append("sk.code=?")
            params.append(filters.skill_code)
        if filters.source_types:
            placeholders = ",".join("?" for _ in filters.source_types)
            clauses.append(f"c.source_type IN ({placeholders})")
            params.extend(filters.source_types)
        # Prefer archive-grounded then curated then style
        sql = f"""
            SELECT c.content_id, c.chapter_id, l.skill_id, c.difficulty_label, c.content_type,
                   c.estimated_seconds, f.family_id, c.source_type, c.statement, s.code, sk.code
            FROM v_content_items_effective c
            JOIN subjects s ON s.subject_id=c.subject_id
            LEFT JOIN content_skill_links l ON l.content_id=c.content_id AND l.relation_type='PRIMARY'
            LEFT JOIN skills sk ON sk.skill_id=l.skill_id
            LEFT JOIN content_family_links f ON f.content_id=c.content_id
            WHERE {' AND '.join(clauses)}
            ORDER BY CASE c.source_type
                WHEN 'OFFICIAL_ARCHIVE' THEN 0
                WHEN 'ARCHIVE_DERIVED' THEN 1
                WHEN 'CURATED' THEN 2
                WHEN 'BREVET_STYLE' THEN 3
                ELSE 4 END,
                c.content_id
            LIMIT ?
        """
        params.append(max(filters.limit * 5, filters.limit))
        raw = self.store.fetchall(sql, params)
        selected: list[dict[str, Any]] = []
        seen_families: set[Any] = set()
        for r in raw:
            family_id = r[6]
            if filters.max_per_family > 0 and family_id is not None:
                # count per family
                count = sum(1 for x in selected if x.get("family_id") == family_id)
                if count >= filters.max_per_family:
                    continue
                seen_families.add(family_id)
            selected.append(
                {
                    "content_id": r[0],
                    "chapter_id": r[1],
                    "skill_id": r[2],
                    "difficulty": r[3],
                    "content_type": r[4],
                    "estimated_seconds": r[5],
                    "family_id": family_id,
                    "source_type": r[7],
                    "statement": r[8],
                    "subject": r[9],
                    "skill_code": r[10],
                }
            )
            if len(selected) >= filters.limit:
                break
        return selected
