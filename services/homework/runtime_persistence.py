"""Persist runtime homework exercises as session-playable catalog entities."""

from __future__ import annotations

import json
import logging
from typing import Protocol

from domain.content.factory import (
    AnswerKind,
    GeneratedContentCandidate,
    LEGACY_CONTENT_TYPE_MAP,
    normalized_content_fingerprint,
)
from domain.unified_experience.models import GeneratedHomeworkExerciseResult
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_factory import _candidate_payload, _legacy_answer_type

LOGGER = logging.getLogger(__name__)
HOMEWORK_RUNTIME_AUTHOR = "homework-runtime-0018b"
HOMEWORK_RUNTIME_GATE_REASON = "LCAI-0018B-homework-runtime-only"
PLAYABLE_ANSWER_KINDS = frozenset(
    {
        AnswerKind.EXACT_TEXT,
        AnswerKind.NUMERIC,
        AnswerKind.SINGLE_CHOICE,
        AnswerKind.BOOLEAN,
    }
)


class RuntimePersistenceRepository(Protocol):
    @property
    def database_path(self): ...


def _legacy_content_type(content_type: object) -> str:
    for legacy, canonical in LEGACY_CONTENT_TYPE_MAP.items():
        if canonical == content_type:
            return legacy
    return "exercise"


def _response_type(kind: AnswerKind) -> str:
    mapping = {
        AnswerKind.EXACT_TEXT: "short_text",
        AnswerKind.NUMERIC: "decimal",
        AnswerKind.SINGLE_CHOICE: "single_choice",
        AnswerKind.BOOLEAN: "true_false",
    }
    return mapping[kind]


def is_playable_candidate(candidate: GeneratedContentCandidate) -> bool:
    if candidate.answer.kind not in PLAYABLE_ANSWER_KINDS:
        return False
    if candidate.answer.kind is AnswerKind.SINGLE_CHOICE and len(candidate.answer.options) < 2:
        return False
    if not candidate.prompt.strip() or not candidate.explanation.strip():
        return False
    return candidate.answer.expected not in (None, "", [], {})


def persist_playable_homework_exercise(
    repository: RuntimePersistenceRepository,
    candidate: GeneratedContentCandidate,
    *,
    homework_id: int,
    learner_id: int,
    position: int,
    correlation_id: str,
    parent_ref: str | None = None,
) -> GeneratedHomeworkExerciseResult:
    if not is_playable_candidate(candidate):
        raise ValueError("HOMEWORK_RUNTIME_EXERCISE_NOT_PLAYABLE")

    connection = connect_v2(repository.database_path)
    try:
        connection.execute("BEGIN")
        context = connection.execute(
            """
            SELECT su.id, cc.id, s.id
            FROM curriculum_chapters cc
            JOIN subjects su ON su.id=cc.subject_id
            JOIN curriculum_skill_details csd ON csd.chapter_id=cc.id
                AND csd.grade_level_id=cc.grade_level_id AND csd.status='approved'
            JOIN skills s ON s.id=csd.skill_id
            WHERE cc.stable_code=? AND su.code=? AND s.code=?
            """,
            [
                candidate.target.chapter_code,
                candidate.target.subject_code,
                candidate.target.primary_skill_code,
            ],
        ).fetchone()
        if context is None:
            raise ValueError("HOMEWORK_CURRICULUM_TARGET_NOT_FOUND")
        subject_id, chapter_id, skill_id = int(context[0]), int(context[1]), int(context[2])
        response_type = _response_type(candidate.answer.kind)
        exercise_id = int(
            connection.execute(
                """
                INSERT INTO exercises(subject_id,code,title,objective,estimated_seconds,difficulty,
                    instructions,evaluation_strategy,language_code,content_version,status)
                VALUES (?,?,?,?,?,?,?,?,'fr-FR',1,'active') RETURNING id
                """,
                [
                    subject_id,
                    candidate.code,
                    candidate.title,
                    candidate.target.primary_skill_code,
                    max(60, candidate.metadata.get("estimated_duration", 5) * 60),
                    candidate.difficulty,
                    candidate.instructions,
                    json.dumps({"kind": "homework_runtime", "source": "ai_runtime_fallback"}),
                ],
            ).fetchone()[0]
        )
        question_id = int(
            connection.execute(
                """
                INSERT INTO content_questions(exercise_id,stable_code,sequence_order,instructions,context,
                    statement,response_type,expected_answer,tolerance,unit,points,is_evaluative)
                VALUES (?,?,1,?,?,?,?,?,?,?,?,TRUE) RETURNING id
                """,
                [
                    exercise_id,
                    f"{candidate.code}-Q1",
                    candidate.instructions,
                    None,
                    candidate.prompt,
                    response_type,
                    json.dumps(candidate.answer.expected),
                    candidate.answer.tolerance,
                    None,
                    1.0,
                ],
            ).fetchone()[0]
        )
        legacy_question_id = int(
            connection.execute(
                """
                INSERT INTO questions(code,statement,answer_type,expected_answer,explanation,hints,
                    estimated_seconds,language_code,content_version,status)
                VALUES (?,?,?,?,?,?,60,'fr-FR',1,'active') RETURNING id
                """,
                [
                    f"{candidate.code}-LEG-Q1",
                    candidate.prompt,
                    _legacy_answer_type(candidate.answer.kind.value),
                    json.dumps(candidate.answer.expected),
                    candidate.explanation,
                    json.dumps(list(candidate.hints)),
                ],
            ).fetchone()[0]
        )
        connection.execute(
            "INSERT INTO exercise_questions VALUES (?,?,1,1,TRUE)",
            [exercise_id, legacy_question_id],
        )
        connection.execute(
            "INSERT INTO question_skills VALUES (?,?,1,TRUE)",
            [legacy_question_id, skill_id],
        )
        if candidate.answer.kind is AnswerKind.SINGLE_CHOICE:
            for index, option in enumerate(candidate.answer.options, 1):
                connection.execute(
                    """
                    INSERT INTO content_answer_options(question_id,stable_code,label,is_correct,sequence_order)
                    VALUES (?,?,?,?,?)
                    """,
                    [
                        question_id,
                        f"{candidate.code}-OPT-{index}",
                        option,
                        option == candidate.answer.expected,
                        index,
                    ],
                )
        connection.execute(
            """
            INSERT INTO content_solutions(question_id,correct_answer,pedagogical_explanation,method,
                common_mistakes,advice,accepted_variants,rubric)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            [
                question_id,
                json.dumps(candidate.answer.expected),
                candidate.explanation,
                candidate.metadata.get("solving_method", "Méthode pas à pas"),
                json.dumps(list(candidate.metadata.get("common_mistakes", ()) or ())),
                candidate.feedback.get("correct", ""),
                json.dumps([]),
                json.dumps({"points": 1}),
            ],
        )
        for index, hint in enumerate(candidate.hints, 1):
            connection.execute(
                """
                INSERT INTO content_hints(question_id,sequence_order,text,penalty_weight,disclosure_level,
                    related_skill_id,reveals_answer)
                VALUES (?,?,?,?,?,?,FALSE)
                """,
                [question_id, index, hint, 0.1, min(index, 3), skill_id],
            )
        payload = _candidate_payload(candidate)
        payload["homework_runtime"] = {
            "homework_id": homework_id,
            "learner_id": learner_id,
            "source": "ai_runtime_fallback",
            "provider": candidate.provenance.generator_type,
            "model": candidate.provenance.generator_identifier,
            "correlation_id": correlation_id,
            "parent_ref": parent_ref,
            "content_fingerprint": normalized_content_fingerprint(candidate.prompt),
        }
        version_id = int(
            connection.execute(
                """
                INSERT INTO content_versions(entity_type,entity_id,version_number,payload,author,status)
                VALUES ('exercise',?,1,?,?,'approved') RETURNING id
                """,
                [exercise_id, json.dumps(payload), HOMEWORK_RUNTIME_AUTHOR],
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO learning_content_metadata(exercise_id,chapter_id,subskill_id,content_type,summary,
                author_source,license_or_origin,created_on,last_reviewed_on,min_duration_minutes,max_duration_minutes,
                difficulty_rationale,expected_attempts,allowed_hints,calculator_allowed,material_required,compatibility,
                pedagogical_strategy,cognitive_demand,expected_response_type,source_identifier,current_version)
            VALUES (?,?,NULL,?,?,?,?,current_date,current_date,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """,
            [
                exercise_id,
                chapter_id,
                _legacy_content_type(candidate.content_type),
                candidate.title,
                HOMEWORK_RUNTIME_AUTHOR,
                "ai_runtime_fallback",
                1,
                10,
                json.dumps({"level": candidate.difficulty}),
                1,
                len(candidate.hints),
                False,
                None,
                json.dumps({"homework": True, "production_catalog": False}),
                candidate.pedagogical_intent.value,
                "apply",
                response_type,
                candidate.code,
            ],
        )
        validation_id = int(
            connection.execute(
                "INSERT INTO validation_runs(source_name,is_valid,error_count,warning_count) VALUES (?,TRUE,0,0) RETURNING id",
                [candidate.code],
            ).fetchone()[0]
        )
        quality_id = int(
            connection.execute(
                """
                INSERT INTO content_quality_assessments(content_version_id,score,quality_level,passed_criteria,
                    missing_criteria,blocking_errors,warnings,assessor)
                VALUES (?,?,?,?,?,?,?,?) RETURNING id
                """,
                [version_id, 80, "publishable", "[]", "[]", "[]", "[]", HOMEWORK_RUNTIME_AUTHOR],
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO editorial_approvals(content_version_id,approver,approved,validation_run_id,
                quality_assessment_id,active)
            VALUES (?,?,TRUE,?,?,TRUE)
            """,
            [version_id, HOMEWORK_RUNTIME_AUTHOR, validation_id, quality_id],
        )
        connection.execute(
            """
            INSERT INTO content_production_gates(content_version_id,production_enabled,production_tier,reason,enabled_by)
            VALUES (?,FALSE,'BLOCKED',?,?)
            ON CONFLICT(content_version_id) DO NOTHING
            """,
            [version_id, HOMEWORK_RUNTIME_GATE_REASON, HOMEWORK_RUNTIME_AUTHOR],
        )
        fingerprint = normalized_content_fingerprint(candidate.prompt)
        stable_key = f"{homework_id}:{position}:{fingerprint}"
        runtime_row = connection.execute(
            """
            INSERT INTO homework_runtime_exercises
            (homework_id,learner_id,position,stable_key,source,publication_status,subject_id,skill_ids,
             exercise_payload,content_fingerprint,generator_model,prompt_template_version,correlation_id,
             validation_result,content_id,content_version_id,chapter_id,skill_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id
            """,
            [
                homework_id,
                learner_id,
                position,
                stable_key,
                "ai_runtime_fallback",
                "RUNTIME_ONLY",
                subject_id,
                json.dumps([skill_id]),
                json.dumps(
                    {
                        "title": candidate.title,
                        "statement": candidate.prompt,
                        "instructions": candidate.instructions,
                        "expected_answer": candidate.answer.expected,
                        "exercise_type": candidate.content_type.value,
                    }
                ),
                fingerprint,
                candidate.provenance.generator_identifier,
                candidate.provenance.template_version,
                correlation_id,
                json.dumps({"valid": True, "playable": True}),
                exercise_id,
                version_id,
                chapter_id,
                skill_id,
            ],
        ).fetchone()
        connection.execute("COMMIT")
        return GeneratedHomeworkExerciseResult(
            str(exercise_id),
            str(version_id),
            str(subject_id),
            str(chapter_id),
            str(skill_id),
            candidate.content_type.value,
            str(candidate.difficulty),
            candidate.prompt,
            candidate.answer.expected,
            candidate.explanation,
            "ai_runtime_fallback",
            candidate.provenance.generator_type,
            candidate.provenance.generator_identifier,
            {
                "correlation_id": correlation_id,
                "content_fingerprint": fingerprint,
                "runtime_record_id": int(runtime_row[0]),
                "parent_ref": parent_ref,
            },
        )
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
