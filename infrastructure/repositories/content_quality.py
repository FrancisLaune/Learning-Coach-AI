"""DuckDB adapter for LCAI-0012D content-quality inventory and QCM consolidation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infrastructure.database.v2 import connect_v2
from services.curriculum.services import ContentApprovalService, EditorialWorkflowService


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

    def record_human_decision(
        self,
        *,
        version_id: int,
        reviewer: str,
        decision: str,
        notes: str,
    ) -> None:
        normalized = decision.upper()
        if normalized not in {"REJECT", "KEEP_FOR_REVIEW"}:
            raise ValueError("Unsupported non-approval decision")
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """
                SELECT entity_id,status,payload FROM content_versions
                WHERE id=? AND entity_type='exercise'
                """,
                [version_id],
            ).fetchone()
            if row is None:
                raise ValueError("Unknown content version")
            target = "archived" if normalized == "REJECT" else "review"
            EditorialWorkflowService().transition(str(row[1]), target, validated=True)
            existing = connection.execute(
                """
                SELECT id FROM content_versions
                WHERE entity_type='exercise' AND entity_id=? AND status=?
                  AND json_extract_string(payload,'$.review_source_version_id')=?
                """,
                [row[0], target, str(version_id)],
            ).fetchone()
            if existing:
                return
            payload = json.loads(str(row[2]))
            payload["review_source_version_id"] = version_id
            payload["review_decision"] = normalized
            next_version = int(
                connection.execute(
                    """
                    SELECT coalesce(max(version_number),0)+1 FROM content_versions
                    WHERE entity_type='exercise' AND entity_id=?
                    """,
                    [row[0]],
                ).fetchone()[0]
            )
            connection.execute("BEGIN")
            decision_version_id = int(
                connection.execute(
                    """
                    INSERT INTO content_versions(
                        entity_type,entity_id,version_number,payload,author,status
                    ) VALUES ('exercise',?,?,?,?,?) RETURNING id
                    """,
                    [row[0], next_version, json.dumps(payload), reviewer, target],
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO editorial_reviews(content_version_id,reviewer,decision,notes)
                VALUES (?,?,?,?)
                ON CONFLICT(content_version_id,reviewer) DO UPDATE SET
                    decision=excluded.decision,notes=excluded.notes,reviewed_at=now()
                """,
                [
                    decision_version_id,
                    reviewer,
                    "changes_requested",
                    notes,
                ],
            )
            connection.execute(
                """
                INSERT INTO content_status_events(
                    content_version_id,previous_status,new_status,author
                ) VALUES (?,?,?,?)
                """,
                [decision_version_id, str(row[1]), target, reviewer],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def approve_for_production(
        self,
        *,
        item: dict[str, Any],
        reviewer: str,
        approver: str,
        reason: str,
        pipeline_version: str = "lcai-0012d2-quality-v1",
    ) -> int:
        """Publish a reviewed Draft as a new active projection, preserving its source."""
        if item["recommended_decision"] != "APPROVE" or int(item["candidate_score"]) < 80:
            raise ValueError("Only high-confidence queue candidates can be approved")
        source_version_id = int(item["version_id"])
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            existing = connection.execute(
                """
                SELECT e.id FROM exercises e
                JOIN content_versions cv ON cv.entity_type='exercise' AND cv.entity_id=e.id
                WHERE json_extract_string(cv.payload,'$.publication_source_version_id')=?
                  AND cv.status='approved'
                """,
                [str(source_version_id)],
            ).fetchone()
            if existing:
                connection.execute("ROLLBACK")
                return int(existing[0])
            source = connection.execute(
                """
                SELECT e.subject_id,e.title,e.objective,e.estimated_seconds,e.difficulty,
                       e.instructions,e.evaluation_strategy,e.language_code,cv.payload,
                       qs.skill_id,q.statement,q.expected_answer,q.explanation,cv.author
                FROM content_versions cv
                JOIN exercises e ON e.id=cv.entity_id AND cv.entity_type='exercise'
                JOIN exercise_questions eq ON eq.exercise_id=e.id AND eq.position=1
                JOIN questions q ON q.id=eq.question_id
                JOIN question_skills qs ON qs.question_id=q.id AND qs.is_primary
                WHERE cv.id=?
                """,
                [source_version_id],
            ).fetchone()
            if source is None:
                raise ValueError("Approval source is unavailable")
            author = str(source[13])
            ContentApprovalService.approve(
                author=author,
                reviewer=reviewer,
                approver=approver,
                validated=bool(item["hard_gates_passed"]),
            )
            payload = json.loads(str(source[8]))
            payload["publication_source_version_id"] = source_version_id
            payload["quality_pipeline_version"] = pipeline_version
            payload["approval_reason"] = reason
            chapter_code = payload["curriculum_target"]["chapter_code"]
            content_type = str(item["content_type"])
            legacy_type = {
                "practice": "exercise",
                "guided_practice": "exercise",
                "assessment": "exam_practice",
                "diagnostic": "diagnostic_activity",
                "remediation": "remediation_activity",
                "worked_example": "worked_example",
            }.get(content_type, "exercise")
            answer_kind = str(item["answer_kind"])
            response_type = {
                "numeric": "decimal",
                "single_choice": "single_choice",
                "multiple_choice": "multiple_choice",
                "boolean": "true_false",
                "structured": "structured",
                "open_response": "long_text",
            }.get(answer_kind, "short_text")
            legacy_response_type = {
                "numeric": "number",
                "single_choice": "choice",
                "multiple_choice": "choice",
                "boolean": "boolean",
                "structured": "structured",
            }.get(answer_kind, "text")
            detailed_expected = source[11]
            if item.get("choices"):
                labels = [str(choice) for choice in item["choices"]]
                expected_labels = (
                    [str(value) for value in item["expected_answer"]]
                    if isinstance(item["expected_answer"], list)
                    else [str(item["expected_answer"])]
                )
                expected_codes = [f"OPT-{labels.index(label) + 1}" for label in expected_labels]
                detailed_expected = json.dumps(
                    expected_codes if answer_kind == "multiple_choice" else expected_codes[0]
                )
            exercise_id = int(
                connection.execute(
                    """
                    INSERT INTO exercises(
                        subject_id,code,title,objective,estimated_seconds,difficulty,instructions,
                        evaluation_strategy,language_code,content_version,status
                    ) VALUES (?,?,?,?,?,?,?,?,?,1,'active') RETURNING id
                    """,
                    [
                        source[0],
                        f"{item['code']}-PUB-{source_version_id}",
                        source[1],
                        source[2],
                        source[3],
                        source[4],
                        source[5],
                        source[6],
                        source[7],
                    ],
                ).fetchone()[0]
            )
            legacy_question_id = int(
                connection.execute(
                    """
                    INSERT INTO questions(
                        code,statement,answer_type,expected_answer,explanation,hints,
                        estimated_seconds,language_code,content_version,status
                    ) VALUES (?,?,?,?,?,'[]',60,'fr-FR',1,'active') RETURNING id
                    """,
                    [
                        f"{item['code']}-PUB-Q1-{source_version_id}",
                        source[10],
                        legacy_response_type,
                        detailed_expected,
                        source[12],
                    ],
                ).fetchone()[0]
            )
            connection.execute(
                "INSERT INTO exercise_questions VALUES (?,?,1,1,TRUE)",
                [exercise_id, legacy_question_id],
            )
            connection.execute(
                "INSERT INTO question_skills VALUES (?,?,1,TRUE)",
                [legacy_question_id, source[9]],
            )
            version_id = int(
                connection.execute(
                    """
                    INSERT INTO content_versions(
                        entity_type,entity_id,version_number,payload,author,status
                    ) VALUES ('exercise',?,1,?,?,'approved') RETURNING id
                    """,
                    [exercise_id, json.dumps(payload), author],
                ).fetchone()[0]
            )
            chapter_id = int(
                connection.execute("SELECT id FROM curriculum_chapters WHERE stable_code=?", [chapter_code]).fetchone()[
                    0
                ]
            )
            connection.execute(
                """
                INSERT INTO learning_content_metadata(
                    exercise_id,chapter_id,subskill_id,content_type,summary,author_source,
                    license_or_origin,created_on,last_reviewed_on,min_duration_minutes,
                    max_duration_minutes,difficulty_rationale,expected_attempts,allowed_hints,
                    calculator_allowed,material_required,compatibility,pedagogical_strategy,
                    cognitive_demand,expected_response_type,source_identifier,current_version
                ) VALUES (?,?,NULL,?,?,?,?,current_date,current_date,1,10,?,1,0,FALSE,NULL,?,?,?,?,?,1)
                """,
                [
                    exercise_id,
                    chapter_id,
                    legacy_type,
                    str(source[1]),
                    author,
                    "Internally generated and independently reviewed.",
                    json.dumps({"level": int(source[4])}),
                    json.dumps({"standalone": True}),
                    "validated practice",
                    "grade-level",
                    response_type,
                    f"LCAI-0012D2:{source_version_id}",
                ],
            )
            objective = connection.execute(
                """
                SELECT learning_objective_id FROM skill_learning_objectives
                WHERE skill_id=? AND is_primary LIMIT 1
                """,
                [source[9]],
            ).fetchone()
            if objective:
                connection.execute(
                    "INSERT INTO content_learning_objectives VALUES (?,?)",
                    [exercise_id, objective[0]],
                )
            detailed_question_id = int(
                connection.execute(
                    """
                    INSERT INTO content_questions(
                        exercise_id,stable_code,sequence_order,instructions,context,statement,
                        response_type,expected_answer,tolerance,unit,points,is_evaluative
                    ) VALUES (?,?,1,?,NULL,?,?,?,NULL,NULL,1,TRUE) RETURNING id
                    """,
                    [
                        exercise_id,
                        f"CQ-{item['code']}-PUB-{source_version_id}",
                        str(source[5]),
                        str(source[10]),
                        response_type,
                        detailed_expected,
                    ],
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO content_solutions(
                    question_id,correct_answer,pedagogical_explanation,method,
                    common_mistakes,advice,accepted_variants,rubric
                ) VALUES (?,?,?,?,?,'',?,?)
                """,
                [
                    detailed_question_id,
                    detailed_expected,
                    source[12],
                    "Réponse validée par revue humaine.",
                    "[]",
                    "[]",
                    json.dumps({"points": 1}),
                ],
            )
            for position, option in enumerate(item.get("choices", []), 1):
                label = str(option)
                expected = item["expected_answer"]
                correct = label in (expected if isinstance(expected, list) else [str(expected)])
                connection.execute(
                    """
                    INSERT INTO content_answer_options(
                        question_id,stable_code,label,is_correct,sequence_order
                    ) VALUES (?,?,?,?,?)
                    """,
                    [detailed_question_id, f"OPT-{position}", label, correct, position],
                )
            validation_id = int(
                connection.execute(
                    """
                    INSERT INTO validation_runs(
                        source_name,is_valid,error_count,warning_count
                    ) VALUES (?,TRUE,0,0) RETURNING id
                    """,
                    [pipeline_version],
                ).fetchone()[0]
            )
            quality_id = int(
                connection.execute(
                    """
                    INSERT INTO content_quality_assessments(
                        content_version_id,score,quality_level,passed_criteria,missing_criteria,
                        blocking_errors,warnings,assessor
                    ) VALUES (?,?,'publishable',?,'[]','[]','[]',?) RETURNING id
                    """,
                    [
                        version_id,
                        int(item["candidate_score"]),
                        json.dumps(item["automated_checks"]),
                        reviewer,
                    ],
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO editorial_reviews(content_version_id,reviewer,decision,notes)
                VALUES (?,?,'accepted',?)
                """,
                [version_id, reviewer, reason],
            )
            connection.execute(
                """
                INSERT INTO editorial_approvals(
                    content_version_id,approver,approved,validation_run_id,
                    quality_assessment_id,active
                ) VALUES (?,?,TRUE,?,?,TRUE)
                """,
                [version_id, approver, validation_id, quality_id],
            )
            connection.execute(
                """
                INSERT INTO content_production_gates(
                    content_version_id,production_enabled,production_tier,reason,enabled_by
                ) VALUES (?,TRUE,'LIMITED_PRODUCTION',?,?)
                """,
                [version_id, reason, approver],
            )
            connection.execute(
                """
                INSERT INTO content_status_events(
                    content_version_id,previous_status,new_status,author
                ) VALUES (?,'review','approved',?)
                """,
                [version_id, approver],
            )
            connection.execute("COMMIT")
            return exercise_id
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
