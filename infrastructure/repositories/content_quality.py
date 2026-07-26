"""DuckDB adapter for LCAI-0012D content-quality inventory and QCM consolidation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2


class DuckDBContentQualityRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def draft_inventory(self) -> list[dict[str, Any]]:
        connection = connect_v2(self.database_path)
        try:
            rows = connection.execute(
                """
                WITH latest AS (
                    SELECT * FROM content_versions
                    WHERE entity_type='exercise'
                    QUALIFY row_number() OVER (
                        PARTITION BY entity_id ORDER BY version_number DESC,id DESC
                    )=1
                )
                SELECT e.id,cv.id,e.code,cv.version_number,cv.author,cv.status,e.difficulty,
                       q.id,q.statement,q.answer_type,q.expected_answer,q.explanation,
                       cv.payload,s.code,cc.stable_code,su.code,sl.code,p.code,
                       count(DISTINCT csd.skill_id)
                FROM exercises e
                JOIN latest cv ON cv.entity_id=e.id AND cv.status='draft'
                JOIN exercise_questions eq ON eq.exercise_id=e.id AND eq.position=1
                JOIN questions q ON q.id=eq.question_id
                JOIN question_skills qs ON qs.question_id=q.id AND qs.is_primary
                JOIN skills s ON s.id=qs.skill_id
                JOIN curriculum_skill_details csd ON csd.skill_id=s.id
                JOIN curriculum_chapters cc ON cc.id=csd.chapter_id
                JOIN subjects su ON su.id=cc.subject_id
                JOIN school_levels sl ON sl.id=cc.grade_level_id
                JOIN programs p ON p.id=cc.program_id
                WHERE json_extract_string(cv.payload,'$.curriculum_target.grade_code')
                      IN ('FR-4E','FR-3E')
                  AND cc.stable_code=json_extract_string(cv.payload,'$.curriculum_target.chapter_code')
                  AND su.code=json_extract_string(cv.payload,'$.curriculum_target.subject_code')
                  AND s.code=json_extract_string(cv.payload,'$.curriculum_target.primary_skill_code')
                GROUP BY ALL ORDER BY e.code
                """
            ).fetchall()
        finally:
            connection.close()
        return [
            {
                "content_id": int(row[0]),
                "version_id": int(row[1]),
                "code": str(row[2]),
                "version_number": int(row[3]),
                "author": str(row[4]),
                "status": str(row[5]),
                "difficulty": int(row[6]),
                "legacy_question_id": int(row[7]),
                "prompt": str(row[8]),
                "legacy_answer_type": str(row[9]),
                "stored_answer": json.loads(str(row[10])),
                "explanation": str(row[11]),
                "payload": json.loads(str(row[12])),
                "skill": str(row[13]),
                "chapter": str(row[14]),
                "subject": str(row[15]),
                "grade": str(row[16]),
                "program": str(row[17]),
                "curriculum_relation_count": int(row[18]),
            }
            for row in rows
        ]

    def persist_qcm_execution_payload(self, item: dict[str, Any], candidate: dict[str, Any]) -> int:
        """Materialize QCM choices in execution tables without approving the Draft."""
        answer = candidate["answer"]
        options = [str(value) for value in answer["options"]]
        expected_labels = (
            [str(value) for value in answer["expected"]]
            if answer["kind"] == "multiple_choice"
            else [str(answer["expected"])]
        )
        codes = [f"OPT-{index + 1}" for index in range(len(options))]
        expected_codes = [codes[options.index(label)] for label in expected_labels]
        expected: str | list[str] = expected_codes if answer["kind"] == "multiple_choice" else expected_codes[0]
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            existing = connection.execute(
                "SELECT id FROM content_questions WHERE exercise_id=?", [item["content_id"]]
            ).fetchone()
            if existing is None:
                question_id = int(
                    connection.execute(
                        """
                        INSERT INTO content_questions(
                            exercise_id,stable_code,sequence_order,instructions,context,statement,
                            response_type,expected_answer,tolerance,unit,points,is_evaluative
                        ) VALUES (?,?,1,?,NULL,?,?,?,?,NULL,1,TRUE) RETURNING id
                        """,
                        [
                            item["content_id"],
                            f"CQ-{item['code']}",
                            candidate.get("instructions", ""),
                            candidate["prompt"],
                            answer["kind"],
                            json.dumps(expected),
                            answer.get("tolerance"),
                        ],
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO content_solutions(
                        question_id,correct_answer,pedagogical_explanation,method,
                        common_mistakes,advice,accepted_variants,rubric
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    [
                        question_id,
                        json.dumps(expected),
                        candidate["explanation"],
                        "Sélectionner la ou les réponses correctes.",
                        "[]",
                        candidate.get("feedback", {}).get("incorrect", ""),
                        "[]",
                        json.dumps({"points": 1}),
                    ],
                )
            else:
                question_id = int(existing[0])
            for sequence, (code, label) in enumerate(zip(codes, options, strict=True), 1):
                connection.execute(
                    """
                    INSERT INTO content_answer_options(
                        question_id,stable_code,label,is_correct,sequence_order
                    ) VALUES (?,?,?,?,?)
                    ON CONFLICT(question_id,stable_code) DO UPDATE SET
                        label=excluded.label,is_correct=excluded.is_correct,
                        sequence_order=excluded.sequence_order
                    """,
                    [question_id, code, label, code in expected_codes, sequence],
                )
            connection.execute("COMMIT")
            return question_id
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def qcm_execution_payload(self, content_id: int) -> dict[str, Any] | None:
        connection = connect_v2(self.database_path)
        try:
            question = connection.execute(
                """
                SELECT id,response_type,expected_answer FROM content_questions
                WHERE exercise_id=?
                """,
                [content_id],
            ).fetchone()
            if question is None:
                return None
            options = connection.execute(
                """
                SELECT stable_code,label,is_correct,sequence_order
                FROM content_answer_options WHERE question_id=? ORDER BY sequence_order
                """,
                [question[0]],
            ).fetchall()
            return {
                "question_id": int(question[0]),
                "response_type": str(question[1]),
                "expected_answer": json.loads(str(question[2])),
                "options": [
                    {
                        "code": str(row[0]),
                        "label": str(row[1]),
                        "correct": bool(row[2]),
                        "sequence": int(row[3]),
                    }
                    for row in options
                ],
            }
        finally:
            connection.close()

    def correct_known_mathematics_answer(self, code: str) -> bool:
        """Create a traceable Draft v2 while preserving the original generated version."""
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                """
                SELECT e.id,q.id,cv.id,cv.payload,q.expected_answer,q.explanation
                FROM exercises e
                JOIN exercise_questions eq ON eq.exercise_id=e.id AND eq.position=1
                JOIN questions q ON q.id=eq.question_id
                JOIN content_versions cv ON cv.entity_type='exercise' AND cv.entity_id=e.id
                WHERE e.code=? ORDER BY cv.version_number DESC LIMIT 1
                """,
                [code],
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown content: {code}")
            exercise_id, question_id, previous_version_id = int(row[0]), int(row[1]), int(row[2])
            current_answer = json.loads(str(row[4]))
            if "2004" in str(current_answer):
                connection.execute("ROLLBACK")
                return False
            corrected_answer = str(current_answer).replace("2100", "2004")
            corrected_explanation = str(row[5]).replace("2100", "2004").replace("2 1 0 0", "2 0 0 4")
            payload = json.loads(str(row[3]))
            payload["quality_correction"] = {
                "ticket": "LCAI-0012D",
                "reason": "Independent enumeration proves the minimum is 2004, not 2100.",
                "previous_version_id": previous_version_id,
            }
            next_version = int(
                connection.execute(
                    """
                    SELECT coalesce(max(version_number),0)+1 FROM content_versions
                    WHERE entity_type='exercise' AND entity_id=?
                    """,
                    [exercise_id],
                ).fetchone()[0]
            )
            version_id = int(
                connection.execute(
                    """
                    INSERT INTO content_versions(
                        entity_type,entity_id,version_number,payload,author,status
                    ) VALUES ('exercise',?,?,?,'lcai-0012d-quality-correction','draft')
                    RETURNING id
                    """,
                    [exercise_id, next_version, json.dumps(payload)],
                ).fetchone()[0]
            )
            connection.execute(
                "UPDATE questions SET expected_answer=?,explanation=? WHERE id=?",
                [json.dumps(corrected_answer), corrected_explanation, question_id],
            )
            connection.execute(
                """
                INSERT INTO content_status_events(
                    content_version_id,previous_status,new_status,author
                ) VALUES (?,'draft','draft','lcai-0012d-quality-correction')
                """,
                [version_id],
            )
            connection.execute("COMMIT")
            return True
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
