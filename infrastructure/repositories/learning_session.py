"""Transactional DuckDB persistence for the Learning Session bounded context."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from domain.learning_session.models import (
    ActivityStatus,
    Assessment,
    Attempt,
    HintUsage,
    LearningSession,
    SessionActivity,
    SessionCheckpoint,
    SessionEvent,
    SessionStatus,
    SessionSummary,
    StudentAnswer,
)
from infrastructure.database.v2 import connect_v2


class DuckDBLearningSessionRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def create(self, session: LearningSession) -> LearningSession:
        con = connect_v2(self.database_path)
        try:
            con.execute("BEGIN")
            row = con.execute(
                """INSERT INTO learning_sessions(learner_id,kind,status,planned_duration_seconds,engine_version)
                VALUES (?,'practice','planned',?,?) RETURNING id""",
                [session.learner_id, session.planned_duration_seconds, session.application_version],
            ).fetchone()
            session_id = int(row[0])
            con.execute(
                """INSERT INTO learning_session_details(session_id,journey_version_id,proposal_id,status,creation_time,
                start_time,end_time,planned_duration_seconds,actual_duration_seconds,estimated_mastery_gain,
                completion_rate,session_score,session_version,application_version,curriculum_version,content_version,
                decision_engine_version,assessment_engine_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    session_id,
                    session.journey_version_id,
                    session.recommendation_id,
                    session.status.value,
                    session.creation_time,
                    session.start_time,
                    session.end_time,
                    session.planned_duration_seconds,
                    session.actual_duration_seconds,
                    session.estimated_mastery_gain,
                    session.completion_rate,
                    session.session_score,
                    session.session_version,
                    session.application_version,
                    session.curriculum_version,
                    session.content_version,
                    session.decision_engine_version,
                    session.assessment_engine_version,
                ],
            )
            con.execute("COMMIT")
            return replace(session, session_id=session_id)
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def get(self, session_id: int) -> LearningSession | None:
        con = connect_v2(self.database_path, read_only=True)
        try:
            row = con.execute(
                """SELECT ls.id,ls.learner_id,d.journey_version_id,d.proposal_id,d.status,d.creation_time,
                d.planned_duration_seconds,d.application_version,d.curriculum_version,d.content_version,
                d.decision_engine_version,d.assessment_engine_version,d.start_time,d.end_time,
                d.actual_duration_seconds,d.estimated_mastery_gain,d.completion_rate,d.session_score,d.session_version
                FROM learning_sessions ls JOIN learning_session_details d ON d.session_id=ls.id WHERE ls.id=?""",
                [session_id],
            ).fetchone()
            if row is None:
                return None
            return LearningSession(
                int(row[0]),
                int(row[1]),
                int(row[2]),
                int(row[3]),
                SessionStatus(row[4]),
                row[5],
                int(row[6]),
                str(row[7]),
                str(row[8]),
                str(row[9]),
                str(row[10]),
                str(row[11]),
                row[12],
                row[13],
                int(row[14]),
                float(row[15]),
                float(row[16]),
                float(row[17]),
                int(row[18]),
            )
        finally:
            con.close()

    def transition(
        self,
        session_id: int,
        expected: SessionStatus,
        target: SessionStatus,
        at: datetime,
    ) -> None:
        current = self.get(session_id)
        if current is None:
            raise KeyError(f"Unknown learning session {session_id}")
        if current.status is not expected:
            raise ValueError(f"Expected {expected.value}, found {current.status.value}")
        changed = current.transition(target, at)
        con = connect_v2(self.database_path)
        try:
            con.execute("BEGIN")
            updated = con.execute(
                """UPDATE learning_session_details SET status=?,start_time=?,end_time=?
                WHERE session_id=? AND status=? RETURNING session_id""",
                [target.value, changed.start_time, changed.end_time, session_id, expected.value],
            ).fetchone()
            if updated is None:
                raise RuntimeError("Concurrent session transition rejected")
            # DuckDB rejects updates of a referenced parent row even when its
            # primary key is unchanged. The execution status therefore lives
            # exclusively in the additive detail table.
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def add_activity(self, activity: SessionActivity) -> SessionActivity:
        con = connect_v2(self.database_path)
        try:
            row = con.execute(
                """INSERT INTO session_activities(session_id,content_id,content_version_id,activity_order,
                activity_type,difficulty,estimated_duration_seconds,status,score,mastery_delta)
                VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                [
                    activity.session_id,
                    activity.content_id,
                    activity.content_version_id,
                    activity.activity_order,
                    activity.activity_type,
                    activity.difficulty,
                    activity.estimated_duration_seconds,
                    activity.status.value,
                    activity.score,
                    activity.mastery_delta,
                ],
            ).fetchone()
            return replace(activity, activity_id=int(row[0]))
        finally:
            con.close()

    def list_activities(self, session_id: int) -> tuple[SessionActivity, ...]:
        con = connect_v2(self.database_path, read_only=True)
        try:
            rows = con.execute(
                """SELECT id,session_id,content_id,content_version_id,activity_order,activity_type,difficulty,
                estimated_duration_seconds,status,score,mastery_delta FROM session_activities
                WHERE session_id=? AND archived_at IS NULL ORDER BY activity_order""",
                [session_id],
            ).fetchall()
            return tuple(
                SessionActivity(
                    int(row[0]),
                    int(row[1]),
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                    str(row[5]),
                    int(row[6]),
                    int(row[7]),
                    ActivityStatus(row[8]),
                    float(row[9]),
                    float(row[10]),
                )
                for row in rows
            )
        finally:
            con.close()

    def update_activity(self, activity: SessionActivity) -> None:
        con = connect_v2(self.database_path)
        try:
            con.execute(
                """UPDATE session_activities SET status=?,score=?,mastery_delta=? WHERE id=? AND session_id=?""",
                [
                    activity.status.value,
                    activity.score,
                    activity.mastery_delta,
                    activity.activity_id,
                    activity.session_id,
                ],
            )
        finally:
            con.close()

    def find_resumable(self, learner_id: int) -> LearningSession | None:
        con = connect_v2(self.database_path, read_only=True)
        try:
            row = con.execute(
                """SELECT d.session_id FROM learning_session_details d JOIN learning_sessions s ON s.id=d.session_id
                WHERE s.learner_id=? AND d.status='PAUSED' AND d.archived_at IS NULL
                ORDER BY d.creation_time DESC LIMIT 1""",
                [learner_id],
            ).fetchone()
        finally:
            con.close()
        return None if row is None else self.get(int(row[0]))

    def save(self, answer: StudentAnswer) -> StudentAnswer:
        con = connect_v2(self.database_path)
        try:
            existing = con.execute(
                "SELECT id FROM student_answers WHERE idempotency_key=?", [answer.idempotency_key]
            ).fetchone()
            if existing:
                return replace(answer, answer_id=int(existing[0]))
            row = self._insert_answer(con, answer)
            return replace(answer, answer_id=int(row[0]))
        finally:
            con.close()

    @staticmethod
    def _insert_answer(con: Any, answer: StudentAnswer) -> tuple[Any, ...]:
        row = con.execute(
            """INSERT INTO student_answers(activity_id,question_id,attempt_number,answer_type,raw_answer,
            normalized_answer,submission_time,time_spent_ms,draft,validated,idempotency_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            [
                answer.activity_id,
                answer.question_id,
                answer.attempt_number,
                answer.answer_type.value,
                json.dumps(answer.raw_answer),
                json.dumps(answer.normalized_answer),
                answer.submission_time,
                answer.time_spent_ms,
                answer.draft,
                answer.validated,
                answer.idempotency_key,
            ],
        ).fetchone()
        if row is None:
            raise RuntimeError("DuckDB did not return an answer identifier")
        return row

    def save_cycle(
        self,
        answer: StudentAnswer,
        assessment: Assessment,
        attempt: Attempt,
        mastery_payload: dict[str, object],
    ) -> Attempt:
        con = connect_v2(self.database_path)
        try:
            con.execute("BEGIN")
            existing = con.execute(
                """SELECT r.id,r.legacy_attempt_id,r.answer_id,r.assessment_id
                FROM session_attempt_records r JOIN student_answers a ON a.id=r.answer_id
                WHERE a.idempotency_key=?""",
                [answer.idempotency_key],
            ).fetchone()
            if existing:
                con.execute("ROLLBACK")
                return replace(
                    attempt,
                    attempt_id=int(existing[0]),
                    answer_id=int(existing[2]),
                    assessment_id=int(existing[3]),
                )
            answer_id = int(self._insert_answer(con, replace(answer, draft=False, validated=True))[0])
            assessment_row = con.execute(
                """INSERT INTO answer_assessments(answer_id,correct,score,penalty,hint_penalty,time_penalty,
                assessment_method,feedback_generated,assessment_engine_version)
                VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
                [
                    answer_id,
                    assessment.correct,
                    assessment.score,
                    assessment.penalty,
                    assessment.hint_penalty,
                    assessment.time_penalty,
                    assessment.assessment_method.value,
                    json.dumps(assessment.feedback_generated),
                    assessment.assessment_engine_version,
                ],
            ).fetchone()
            assessment_id = int(assessment_row[0])
            question = con.execute(
                """SELECT q.id,cq.statement,cq.expected_answer,sa.difficulty
                FROM content_questions cq JOIN session_activities sa ON sa.id=?
                JOIN exercise_questions eq ON eq.exercise_id=cq.exercise_id
                JOIN questions q ON q.id=eq.question_id
                WHERE cq.id=? ORDER BY eq.position LIMIT 1""",
                [answer.activity_id, answer.question_id],
            ).fetchone()
            if question is None:
                raise KeyError("No legacy question mapping for the submitted content question")
            legacy_attempt = con.execute(
                """INSERT INTO attempts(learner_id,question_id,attempt_number,submitted_at,answer,is_correct,
                score,elapsed_ms,difficulty_at_attempt,prompt_snapshot,expected_answer_snapshot)
                VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                [
                    attempt.learner_id,
                    int(question[0]),
                    answer.attempt_number,
                    answer.submission_time,
                    json.dumps(answer.normalized_answer),
                    assessment.correct,
                    assessment.score / 100,
                    attempt.duration_ms,
                    int(question[3]),
                    str(question[1]),
                    str(question[2]),
                ],
            ).fetchone()
            legacy_attempt_id = int(legacy_attempt[0])
            record = con.execute(
                """INSERT INTO session_attempt_records(legacy_attempt_id,learner_id,activity_id,answer_id,
                assessment_id,success,mastery_before,mastery_after,duration_ms,hint_count)
                VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                [
                    legacy_attempt_id,
                    attempt.learner_id,
                    attempt.activity_id,
                    answer_id,
                    assessment_id,
                    attempt.success,
                    attempt.mastery_before,
                    attempt.mastery_after,
                    attempt.duration_ms,
                    attempt.hint_count,
                ],
            ).fetchone()
            record_id = int(record[0])
            con.execute(
                """INSERT INTO session_mastery_updates(attempt_record_id,mastery_before,mastery_after,
                update_payload,learning_engine_version) VALUES (?,?,?,?,?)""",
                [
                    record_id,
                    attempt.mastery_before,
                    attempt.mastery_after,
                    json.dumps(mastery_payload),
                    str(mastery_payload.get("learning_engine_version", "unknown")),
                ],
            )
            con.execute("COMMIT")
            return replace(attempt, attempt_id=record_id, answer_id=answer_id, assessment_id=assessment_id)
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def save_hint(self, usage: HintUsage) -> HintUsage:
        con = connect_v2(self.database_path)
        try:
            row = con.execute(
                """INSERT INTO hint_usage(activity_id,hint_id,hint_number,display_time,penalty)
                VALUES (?,?,?,?,?) ON CONFLICT(activity_id,hint_id) DO NOTHING RETURNING id""",
                [usage.activity_id, usage.hint_id, usage.hint_number, usage.display_time, usage.penalty],
            ).fetchone()
            if row is None:
                row = con.execute(
                    "SELECT id FROM hint_usage WHERE activity_id=? AND hint_id=?",
                    [usage.activity_id, usage.hint_id],
                ).fetchone()
            return replace(usage, hint_usage_id=int(row[0]))
        finally:
            con.close()

    def save_event(self, event: SessionEvent) -> SessionEvent:
        key = f"{event.correlation_id}:{event.event_type}:{event.timestamp.isoformat()}"
        con = connect_v2(self.database_path)
        try:
            row = con.execute(
                """INSERT INTO session_events(session_id,event_type,event_timestamp,payload,correlation_id,idempotency_key)
                VALUES (?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING RETURNING id""",
                [
                    event.session_id,
                    event.event_type,
                    event.timestamp,
                    json.dumps(event.payload),
                    event.correlation_id,
                    key,
                ],
            ).fetchone()
            if row is None:
                row = con.execute("SELECT id FROM session_events WHERE idempotency_key=?", [key]).fetchone()
            return replace(event, event_id=int(row[0]))
        finally:
            con.close()

    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> SessionCheckpoint:
        con = connect_v2(self.database_path)
        try:
            version = int(
                con.execute(
                    "SELECT coalesce(max(checkpoint_version),0)+1 FROM session_checkpoints WHERE session_id=?",
                    [checkpoint.session_id],
                ).fetchone()[0]
            )
            row = con.execute(
                """INSERT INTO session_checkpoints(session_id,activity_id,current_question_id,
                remaining_time_seconds,last_answer_id,autosave_timestamp,checkpoint_version)
                VALUES (?,?,?,?,?,?,?) RETURNING id""",
                [
                    checkpoint.session_id,
                    checkpoint.activity_id,
                    checkpoint.current_question_id,
                    checkpoint.remaining_time_seconds,
                    checkpoint.last_answer_id,
                    checkpoint.autosave_timestamp,
                    version,
                ],
            ).fetchone()
            return replace(checkpoint, checkpoint_id=int(row[0]))
        finally:
            con.close()

    def latest_checkpoint(self, session_id: int) -> SessionCheckpoint | None:
        con = connect_v2(self.database_path, read_only=True)
        try:
            row = con.execute(
                """SELECT id,session_id,activity_id,current_question_id,remaining_time_seconds,last_answer_id,
                autosave_timestamp FROM session_checkpoints WHERE session_id=?
                ORDER BY checkpoint_version DESC LIMIT 1""",
                [session_id],
            ).fetchone()
            return (
                None
                if row is None
                else SessionCheckpoint(
                    int(row[0]),
                    int(row[1]),
                    None if row[2] is None else int(row[2]),
                    None if row[3] is None else int(row[3]),
                    int(row[4]),
                    None if row[5] is None else int(row[5]),
                    row[6],
                )
            )
        finally:
            con.close()

    def autosave(
        self,
        answer: StudentAnswer,
        checkpoint: SessionCheckpoint,
        event: SessionEvent,
    ) -> StudentAnswer:
        key = f"{event.correlation_id}:{event.event_type}:{event.timestamp.isoformat()}"
        con = connect_v2(self.database_path)
        try:
            con.execute("BEGIN")
            existing = con.execute(
                "SELECT id FROM student_answers WHERE idempotency_key=?", [answer.idempotency_key]
            ).fetchone()
            if existing:
                answer_id = int(existing[0])
                con.execute(
                    """UPDATE student_answers SET raw_answer=?,normalized_answer=?,submission_time=?,
                    time_spent_ms=?,draft=TRUE,validated=FALSE WHERE id=?""",
                    [
                        json.dumps(answer.raw_answer),
                        json.dumps(answer.normalized_answer),
                        answer.submission_time,
                        answer.time_spent_ms,
                        answer_id,
                    ],
                )
            else:
                answer_id = int(self._insert_answer(con, replace(answer, draft=True, validated=False))[0])
            version = int(
                con.execute(
                    "SELECT coalesce(max(checkpoint_version),0)+1 FROM session_checkpoints WHERE session_id=?",
                    [checkpoint.session_id],
                ).fetchone()[0]
            )
            con.execute(
                """INSERT INTO session_checkpoints(session_id,activity_id,current_question_id,
                remaining_time_seconds,last_answer_id,autosave_timestamp,checkpoint_version)
                VALUES (?,?,?,?,?,?,?)""",
                [
                    checkpoint.session_id,
                    checkpoint.activity_id,
                    checkpoint.current_question_id,
                    checkpoint.remaining_time_seconds,
                    answer_id,
                    checkpoint.autosave_timestamp,
                    version,
                ],
            )
            con.execute(
                """INSERT INTO session_events(session_id,event_type,event_timestamp,payload,correlation_id,idempotency_key)
                VALUES (?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                [
                    event.session_id,
                    event.event_type,
                    event.timestamp,
                    json.dumps(event.payload),
                    event.correlation_id,
                    key,
                ],
            )
            con.execute("COMMIT")
            return replace(answer, answer_id=answer_id, draft=True, validated=False)
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def save_summary(self, summary: SessionSummary) -> SessionSummary:
        con = connect_v2(self.database_path)
        try:
            row = con.execute(
                """INSERT INTO session_summaries(session_id,completion_rate,average_time_ms,total_score,
                mastery_gain,strengths,weaknesses,recommended_next_session)
                VALUES (?,?,?,?,?,?,?,?) RETURNING id""",
                [
                    summary.session_id,
                    summary.completion_rate,
                    summary.average_time_ms,
                    summary.total_score,
                    summary.mastery_gain,
                    json.dumps(summary.strengths),
                    json.dumps(summary.weaknesses),
                    summary.recommended_next_session,
                ],
            ).fetchone()
            return replace(summary, summary_id=int(row[0]))
        finally:
            con.close()


DuckDBAnswerRepository = DuckDBLearningSessionRepository
DuckDBAssessmentRepository = DuckDBLearningSessionRepository
DuckDBAttemptRepository = DuckDBLearningSessionRepository
DuckDBHintRepository = DuckDBLearningSessionRepository
DuckDBSessionAuditRepository = DuckDBLearningSessionRepository
