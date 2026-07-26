"""DuckDB read/write adapter for the Content Factory foundation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.content.factory import (
    LEGACY_CONTENT_TYPE_MAP,
    CanonicalContentType,
    CurriculumTarget,
    GeneratedContentCandidate,
    normalized_content_fingerprint,
)
from infrastructure.database.v2 import connect_v2
from services.content.expansion import ActiveSkillCoverage, ContentSlot
from services.content.factory import CoverageRow


class DuckDBContentFactoryRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def validate_target(self, target: Any) -> tuple[str, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT s.code, ss.code
                FROM curriculum_chapters cc
                JOIN programs p ON p.id=cc.program_id
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                JOIN subjects su ON su.id=cc.subject_id
                JOIN curriculum_skill_details csd ON csd.chapter_id=cc.id
                    AND csd.grade_level_id=cc.grade_level_id AND csd.status='approved'
                JOIN skills s ON s.id=csd.skill_id
                LEFT JOIN subskills ss ON ss.skill_id=s.id AND ss.code=?
                WHERE p.code=? AND sl.code=? AND su.code=? AND cc.stable_code=?
                  AND s.code=? AND cc.status='approved'
                """,
                [
                    target.subskill_code,
                    target.program_code,
                    target.grade_code,
                    target.subject_code,
                    target.chapter_code,
                    target.primary_skill_code,
                ],
            ).fetchone()
            if row is None:
                return ("Unknown or inconsistent Program/Grade/Subject/Chapter/Skill target",)
            if target.subskill_code and row[1] is None:
                return ("Sub-skill does not belong to the primary Skill",)
            if target.secondary_skill_codes:
                found = connection.execute(
                    """
                    SELECT count(DISTINCT s.code)
                    FROM curriculum_skill_details csd JOIN skills s ON s.id=csd.skill_id
                    JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
                    WHERE cc.stable_code=? AND s.code IN (SELECT unnest(?))
                    """,
                    [target.chapter_code, list(target.secondary_skill_codes)],
                ).fetchone()[0]
                if found != len(set(target.secondary_skill_codes)):
                    return ("A secondary Skill does not belong to the target chapter",)
            return ()
        finally:
            connection.close()

    def has_candidate(self, code: str) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return connection.execute("SELECT count(*) FROM exercises WHERE code=?", [code]).fetchone()[0] > 0
        finally:
            connection.close()

    def generation_context(self, target: Any) -> dict[str, Any]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """
                SELECT cc.title, s.default_label, ss.default_label
                FROM curriculum_chapters cc
                JOIN curriculum_skill_details csd ON csd.chapter_id=cc.id
                    AND csd.grade_level_id=cc.grade_level_id
                JOIN skills s ON s.id=csd.skill_id
                LEFT JOIN subskills ss ON ss.skill_id=s.id AND ss.code=?
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                JOIN subjects su ON su.id=cc.subject_id
                JOIN programs p ON p.id=cc.program_id
                WHERE p.code=? AND sl.code=? AND su.code=? AND cc.stable_code=? AND s.code=?
                """,
                [
                    target.subskill_code,
                    target.program_code,
                    target.grade_code,
                    target.subject_code,
                    target.chapter_code,
                    target.primary_skill_code,
                ],
            ).fetchone()
            if row is None:
                raise ValueError("Unknown curriculum target")
            prerequisites = [
                {"code": code, "label": label}
                for code, label in connection.execute(
                    """
                    SELECT prerequisite.code, prerequisite.default_label
                    FROM skills target
                    JOIN curriculum_skill_relations relation ON relation.target_skill_id=target.id
                        AND relation.active
                    JOIN skills prerequisite ON prerequisite.id=relation.prerequisite_skill_id
                    WHERE target.code=?
                    UNION
                    SELECT prerequisite.code, prerequisite.default_label
                    FROM skills target
                    JOIN skill_prerequisites relation ON relation.skill_id=target.id
                    JOIN skills prerequisite ON prerequisite.id=relation.prerequisite_skill_id
                    WHERE target.code=?
                    """,
                    [target.primary_skill_code, target.primary_skill_code],
                ).fetchall()
            ]
            return {
                "chapter_label": str(row[0]),
                "skill_label": str(row[1]),
                "subskill_label": str(row[2]) if row[2] is not None else None,
                "prerequisites": prerequisites,
            }
        finally:
            connection.close()

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            approved = connection.execute(
                """
                SELECT cq.statement, lcm.source_identifier, lcm.pedagogical_strategy
                FROM approved_learning_catalog alc
                JOIN content_questions cq ON cq.exercise_id=alc.content_id
                JOIN learning_content_metadata lcm ON lcm.exercise_id=alc.content_id
                """
            ).fetchall()
            result: dict[str, tuple[str | None, str | None]] = {
                normalized_content_fingerprint(str(statement)): (str(family), str(role))
                for statement, family, role in approved
            }
            drafts = connection.execute(
                """
                SELECT q.statement, cv.payload
                FROM exercises e
                JOIN exercise_questions eq ON eq.exercise_id=e.id
                JOIN questions q ON q.id=eq.question_id
                JOIN content_versions cv ON cv.entity_type='exercise' AND cv.entity_id=e.id
                WHERE e.status='draft' AND cv.status='draft'
                """
            ).fetchall()
            for statement, raw_payload in drafts:
                payload = json.loads(raw_payload)
                result[normalized_content_fingerprint(str(statement))] = (
                    payload.get("family_code"),
                    payload.get("variant_role"),
                )
            return result
        finally:
            connection.close()

    def approved_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return {
                normalized_content_fingerprint(str(statement)): (str(family), str(role))
                for statement, family, role in connection.execute(
                    """
                    SELECT cq.statement, lcm.source_identifier, lcm.pedagogical_strategy
                    FROM approved_learning_catalog alc
                    JOIN content_questions cq ON cq.exercise_id=alc.content_id
                    JOIN learning_content_metadata lcm ON lcm.exercise_id=alc.content_id
                    """
                ).fetchall()
            }
        finally:
            connection.close()

    def persist_draft(self, candidate: GeneratedContentCandidate, author: str) -> None:
        """Persist through existing exercise/question/version tables, always as Draft."""
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            context = connection.execute(
                """
                SELECT su.id, cc.id, s.id, ss.id
                FROM curriculum_chapters cc
                JOIN subjects su ON su.id=cc.subject_id
                JOIN curriculum_skill_details csd ON csd.chapter_id=cc.id
                    AND csd.grade_level_id=cc.grade_level_id
                JOIN skills s ON s.id=csd.skill_id
                LEFT JOIN subskills ss ON ss.skill_id=s.id AND ss.code=?
                WHERE cc.stable_code=? AND su.code=? AND s.code=?
                """,
                [
                    candidate.target.subskill_code,
                    candidate.target.chapter_code,
                    candidate.target.subject_code,
                    candidate.target.primary_skill_code,
                ],
            ).fetchone()
            if context is None:
                raise ValueError("Candidate curriculum target disappeared before persistence")
            subject_id, chapter_id, skill_id, subskill_id = context
            exercise_id = connection.execute(
                """
                INSERT INTO exercises(subject_id,code,title,objective,estimated_seconds,difficulty,
                    instructions,evaluation_strategy,language_code,content_version,status)
                VALUES (?,?,?,?,300,?,?,?,'fr-FR',1,'draft') RETURNING id
                """,
                [
                    subject_id,
                    candidate.code,
                    candidate.title,
                    candidate.target.primary_skill_code,
                    candidate.difficulty,
                    candidate.instructions,
                    json.dumps({"kind": "factory_candidate"}),
                ],
            ).fetchone()[0]
            question_id = connection.execute(
                """
                INSERT INTO questions(code,statement,answer_type,expected_answer,explanation,hints,
                    estimated_seconds,language_code,content_version,status)
                VALUES (?,?,?,?,?,?,60,?,1,'draft') RETURNING id
                """,
                [
                    f"{candidate.code}-Q1",
                    candidate.prompt,
                    _legacy_answer_type(candidate.answer.kind.value),
                    json.dumps(candidate.answer.expected),
                    candidate.explanation,
                    json.dumps(list(candidate.hints)),
                    candidate.language_code,
                ],
            ).fetchone()[0]
            connection.execute("INSERT INTO exercise_questions VALUES (?,?,1,1,TRUE)", [exercise_id, question_id])
            connection.execute("INSERT INTO question_skills VALUES (?,?,1,TRUE)", [question_id, skill_id])
            if subskill_id is not None:
                connection.execute("INSERT INTO question_subskills VALUES (?,?,1,TRUE)", [question_id, subskill_id])
            for code in candidate.target.secondary_skill_codes:
                secondary = connection.execute(
                    "SELECT id FROM skills WHERE code=? ORDER BY id LIMIT 1", [code]
                ).fetchone()
                if secondary:
                    connection.execute(
                        "INSERT INTO question_skills VALUES (?,?,0.25,FALSE)", [question_id, secondary[0]]
                    )
            payload = _candidate_payload(candidate)
            version_id = connection.execute(
                """
                INSERT INTO content_versions(entity_type,entity_id,version_number,payload,author,status)
                VALUES ('exercise',?,1,?,?,'draft') RETURNING id
                """,
                [exercise_id, json.dumps(payload), author],
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO content_status_events(content_version_id,previous_status,new_status,author) VALUES (?,NULL,'draft',?)",
                [version_id, author],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def approved_coverage(self) -> tuple[CoverageRow, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT p.code, sl.code, su.code, cc.stable_code, s.code,
                       alc.content_type, alc.difficulty, count(DISTINCT alc.content_id)
                FROM curriculum_skill_details csd
                JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
                JOIN programs p ON p.id=cc.program_id
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                JOIN subjects su ON su.id=cc.subject_id
                JOIN skills s ON s.id=csd.skill_id
                LEFT JOIN approved_learning_catalog alc
                    ON alc.skill_id=s.id AND alc.chapter_id=cc.id
                WHERE csd.status='approved' AND cc.status='approved'
                GROUP BY ALL ORDER BY sl.code, su.code, cc.stable_code, s.code
                """
            ).fetchall()
        finally:
            connection.close()
        grouped: dict[tuple[str, ...], dict[str, Any]] = {}
        for program, grade, subject, chapter, skill, legacy_type, difficulty, count in rows:
            key = (program, grade, subject, chapter, skill)
            item = grouped.setdefault(key, {"count": 0, "types": {}, "difficulties": {}})
            amount = int(count)
            item["count"] += amount
            if legacy_type is not None:
                canonical = LEGACY_CONTENT_TYPE_MAP[str(legacy_type)].value
                item["types"][canonical] = item["types"].get(canonical, 0) + amount
                level = int(difficulty)
                item["difficulties"][level] = item["difficulties"].get(level, 0) + amount
        return tuple(
            CoverageRow(
                program_code=key[0],
                grade_code=key[1],
                subject_code=key[2],
                chapter_code=key[3],
                skill_code=key[4],
                approved_count=data["count"],
                by_type=data["types"],
                by_difficulty=data["difficulties"],
            )
            for key, data in grouped.items()
        )

    def draft_pilot_coverage(self) -> dict[str, int]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return {
                str(skill_code): int(count)
                for skill_code, count in connection.execute(
                    """
                    SELECT s.code, count(DISTINCT e.id)
                    FROM exercises e
                    JOIN exercise_questions eq ON eq.exercise_id=e.id
                    JOIN question_skills qs ON qs.question_id=eq.question_id AND qs.is_primary
                    JOIN skills s ON s.id=qs.skill_id
                    JOIN content_versions cv ON cv.entity_type='exercise' AND cv.entity_id=e.id
                    WHERE e.status='draft' AND cv.status='draft'
                      AND json_extract_string(cv.payload, '$.generation_provenance.template_version')
                          LIKE 'lcai-0012b-%'
                    GROUP BY s.code
                    """
                ).fetchall()
            }
        finally:
            connection.close()

    def active_skill_coverage(
        self, grade_codes: tuple[str, ...] = ("FR-4E", "FR-3E")
    ) -> tuple[ActiveSkillCoverage, ...]:
        """Return authoritative active placements with Approved and Draft slots."""
        connection = connect_v2(self.database_path, read_only=True)
        try:
            active = connection.execute(
                """
                SELECT p.code, sl.code, sl.label, su.code, su.default_label, cc.stable_code,
                       cc.title, s.id, s.code, s.default_label,
                       count(DISTINCT downstream.target_skill_id)
                FROM curriculum_skill_details csd
                JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
                JOIN programs p ON p.id=cc.program_id
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                JOIN subjects su ON su.id=cc.subject_id
                JOIN skills s ON s.id=csd.skill_id
                LEFT JOIN curriculum_skill_relations downstream
                    ON downstream.prerequisite_skill_id=s.id AND downstream.active
                WHERE csd.status='approved' AND cc.status='approved'
                  AND sl.code IN (SELECT unnest(?))
                GROUP BY ALL
                """,
                [list(grade_codes)],
            ).fetchall()
            subskills: dict[int, list[tuple[str, str]]] = {}
            for skill_id, code, label in connection.execute(
                """
                SELECT DISTINCT s.id, ss.code, ss.default_label
                FROM skills s JOIN subskills ss ON ss.skill_id=s.id
                """
            ).fetchall():
                subskills.setdefault(int(skill_id), []).append((str(code), str(label)))
            prerequisites: dict[int, set[str]] = {}
            for skill_id, code in connection.execute(
                """
                SELECT relation.target_skill_id, prerequisite.code
                FROM curriculum_skill_relations relation
                JOIN skills prerequisite ON prerequisite.id=relation.prerequisite_skill_id
                WHERE relation.active
                UNION
                SELECT relation.skill_id, prerequisite.code
                FROM skill_prerequisites relation
                JOIN skills prerequisite ON prerequisite.id=relation.prerequisite_skill_id
                """
            ).fetchall():
                prerequisites.setdefault(int(skill_id), set()).add(str(code))
            approved_rows = connection.execute(
                """
                SELECT sl.code, cc.stable_code, alc.skill_id, alc.content_type,
                       alc.difficulty, count(DISTINCT alc.content_id)
                FROM approved_learning_catalog alc
                JOIN curriculum_chapters cc ON cc.id=alc.chapter_id
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                WHERE sl.code IN (SELECT unnest(?))
                GROUP BY ALL
                """,
                [list(grade_codes)],
            ).fetchall()
            draft_rows = connection.execute(
                """
                SELECT json_extract_string(cv.payload, '$.curriculum_target.grade_code'),
                       json_extract_string(cv.payload, '$.curriculum_target.chapter_code'),
                       qs.skill_id,
                       json_extract_string(cv.payload, '$.canonical_content_type'),
                       e.difficulty,
                       count(DISTINCT e.id)
                FROM exercises e
                JOIN exercise_questions eq ON eq.exercise_id=e.id
                JOIN question_skills qs ON qs.question_id=eq.question_id AND qs.is_primary
                JOIN content_versions cv ON cv.entity_type='exercise' AND cv.entity_id=e.id
                WHERE e.status='draft' AND cv.status='draft'
                  AND json_extract_string(cv.payload, '$.curriculum_target.grade_code')
                      IN (SELECT unnest(?))
                GROUP BY ALL
                """,
                [list(grade_codes)],
            ).fetchall()
        finally:
            connection.close()
        approved = _slot_counts(approved_rows)
        drafts = _slot_counts(draft_rows)
        return tuple(
            ActiveSkillCoverage(
                target=_curriculum_target(row),
                grade_label=str(row[2]),
                subject_label=str(row[4]),
                chapter_label=str(row[6]),
                skill_label=str(row[9]),
                subskills=tuple(sorted(subskills.get(int(row[7]), ()))),
                prerequisites=tuple(sorted(prerequisites.get(int(row[7]), ()))),
                downstream_dependencies=int(row[10]),
                approved=approved.get((str(row[1]), str(row[5]), int(row[7])), {}),
                draft=drafts.get((str(row[1]), str(row[5]), int(row[7])), {}),
            )
            for row in active
        )


def _slot_counts(rows: list[tuple[Any, ...]]) -> dict[tuple[str, str, int], dict[ContentSlot, int]]:
    grouped: dict[tuple[str, str, int], dict[ContentSlot, int]] = {}
    for grade, chapter, skill_id, raw_type, difficulty, count in rows:
        if raw_type is None or difficulty is None:
            continue
        value = str(raw_type)
        content_type = (
            LEGACY_CONTENT_TYPE_MAP[value] if value in LEGACY_CONTENT_TYPE_MAP else CanonicalContentType(value)
        )
        key = (str(grade), str(chapter), int(skill_id))
        slot = ContentSlot(content_type, int(difficulty))
        grouped.setdefault(key, {})[slot] = int(count)
    return grouped


def _curriculum_target(row: tuple[Any, ...]) -> CurriculumTarget:
    return CurriculumTarget(
        program_code=str(row[0]),
        grade_code=str(row[1]),
        subject_code=str(row[3]),
        chapter_code=str(row[5]),
        primary_skill_code=str(row[8]),
    )


def _legacy_answer_type(kind: str) -> str:
    return {
        "numeric": "number",
        "single_choice": "choice",
        "multiple_choice": "choice",
        "boolean": "boolean",
        "structured": "structured",
    }.get(kind, "text")


def _candidate_payload(candidate: GeneratedContentCandidate) -> dict[str, Any]:
    provenance = candidate.provenance
    return {
        "code": candidate.code,
        "canonical_content_type": candidate.content_type.value,
        "pedagogical_intent": candidate.pedagogical_intent.value,
        "family_code": candidate.family_code,
        "variant_role": candidate.variant_role,
        "curriculum_target": {
            "program_code": candidate.target.program_code,
            "grade_code": candidate.target.grade_code,
            "subject_code": candidate.target.subject_code,
            "chapter_code": candidate.target.chapter_code,
            "primary_skill_code": candidate.target.primary_skill_code,
            "subskill_code": candidate.target.subskill_code,
            "secondary_skill_codes": candidate.target.secondary_skill_codes,
        },
        "generation_provenance": {
            "generator_type": provenance.generator_type,
            "generator_identifier": provenance.generator_identifier,
            "specification_version": provenance.specification_version,
            "template_version": provenance.template_version,
            "curriculum_version": provenance.curriculum_version,
            "generated_at": provenance.generated_at.isoformat(),
            "latency_ms": provenance.latency_ms,
            "usage": provenance.usage,
        },
        "answer": {
            "kind": candidate.answer.kind.value,
            "expected": candidate.answer.expected,
            "options": list(candidate.answer.options),
            "tolerance": candidate.answer.tolerance,
            "independently_computed": candidate.answer.independently_computed,
        },
    }
