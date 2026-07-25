"""DuckDB read/write adapter for the Content Factory foundation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.content.factory import LEGACY_CONTENT_TYPE_MAP, GeneratedContentCandidate, normalized_content_fingerprint
from infrastructure.database.v2 import connect_v2
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

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """
                SELECT cq.statement, lcm.source_identifier, lcm.pedagogical_strategy
                FROM approved_learning_catalog alc
                JOIN content_questions cq ON cq.exercise_id=alc.content_id
                JOIN learning_content_metadata lcm ON lcm.exercise_id=alc.content_id
                """
            ).fetchall()
            return {
                normalized_content_fingerprint(str(statement)): (str(family), str(role))
                for statement, family, role in rows
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
    }
