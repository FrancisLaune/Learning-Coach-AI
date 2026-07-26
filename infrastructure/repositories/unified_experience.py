"""DuckDB adapter for the unified V2 product experience."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from domain.unified_experience.models import (
    AssignmentStatus,
    AssignmentType,
    DifficultyMode,
    HomeworkAssignment,
    HomeworkRequest,
    LearnerManagementProfile,
    ProgrammeChange,
)
from infrastructure.database.v2 import connect_v2


class DuckDBUnifiedExperienceRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def reference_subjects(self) -> tuple[tuple[int, str, str], ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT DISTINCT s.id,s.code,s.default_label FROM subjects s
                JOIN production_learning_catalog c ON c.subject_id=s.id
                WHERE s.archived_at IS NULL ORDER BY s.default_label"""
            ).fetchall()
            return tuple((int(row[0]), str(row[1]), str(row[2])) for row in rows)
        finally:
            connection.close()

    def learner_for_external_ref(self, external_ref: str) -> int | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                "SELECT id FROM learners WHERE external_ref=? AND archived_at IS NULL", [external_ref]
            ).fetchone()
            return None if row is None else int(row[0])
        finally:
            connection.close()

    def onboarding_complete(self, learner_id: int) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                "SELECT count(*) FROM learner_experience_profiles WHERE learner_id=? AND onboarding_completed_at IS NOT NULL",
                [learner_id],
            ).fetchone()
            return bool(row and row[0])
        finally:
            connection.close()

    def grade_levels(self) -> tuple[tuple[int, str, str], ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT sl.id,sl.code,sl.label FROM school_levels sl
                WHERE sl.archived_at IS NULL
                AND sl.code IN ('FR-CM1','FR-CM2','FR-6E','FR-5E','FR-4E','FR-3E')
                ORDER BY sl.rank DESC"""
            ).fetchall()
            return tuple((int(row[0]), str(row[1]), str(row[2])) for row in rows)
        finally:
            connection.close()

    def learner_grade_id(self, learner_id: int) -> int:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT current_school_level_id FROM learner_journeys
                WHERE learner_id=?""",
                [learner_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown learner journey {learner_id}")
            return int(row[0])
        finally:
            connection.close()

    def subjects_for_grade(self, grade_level_id: int) -> tuple[tuple[int, str, str], ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT DISTINCT s.id,s.code,s.default_label
                FROM production_learning_catalog a
                JOIN subjects s ON s.id=a.subject_id
                JOIN school_levels sl ON sl.code=a.grade_code
                WHERE sl.id=?
                ORDER BY s.default_label""",
                [grade_level_id],
            ).fetchall()
            return tuple((int(row[0]), str(row[1]), str(row[2])) for row in rows)
        finally:
            connection.close()

    def chapters(self, subject_id: int, grade_level_id: int | None = None) -> tuple[tuple[int, str], ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            where = "a.subject_id=?"
            parameters: list[Any] = [subject_id]
            if grade_level_id is not None:
                where += " AND sl.id=?"
                parameters.append(grade_level_id)
            rows = connection.execute(
                f"""SELECT DISTINCT c.id,c.title,c.sequence_order
                FROM production_learning_catalog a
                JOIN curriculum_chapters c ON c.id=a.chapter_id
                JOIN school_levels sl ON sl.code=a.grade_code
                WHERE {where}
                ORDER BY c.sequence_order,c.title""",
                parameters,
            ).fetchall()
            return tuple((int(row[0]), str(row[1])) for row in rows)
        finally:
            connection.close()

    def skills(
        self,
        subject_id: int,
        chapter_ids: tuple[int, ...] = (),
        grade_level_id: int | None = None,
    ) -> tuple[tuple[int, str], ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            parameters: list[Any] = [subject_id]
            chapter_filter = ""
            if chapter_ids:
                placeholders = ",".join("?" for _ in chapter_ids)
                chapter_filter = f" AND c.chapter_id IN ({placeholders})"
                parameters.extend(chapter_ids)
            grade_filter = ""
            if grade_level_id is not None:
                grade_filter = " AND sl.id=?"
                parameters.append(grade_level_id)
            rows = connection.execute(
                f"""SELECT DISTINCT c.skill_id,s.default_label FROM production_learning_catalog c
                JOIN skills s ON s.id=c.skill_id
                JOIN school_levels sl ON sl.code=c.grade_code
                WHERE c.subject_id=? {chapter_filter} {grade_filter}
                ORDER BY s.default_label""",
                parameters,
            ).fetchall()
            return tuple((int(row[0]), str(row[1])) for row in rows)
        finally:
            connection.close()

    def select_approved_content(self, request: HomeworkRequest) -> tuple[int, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            parameters: list[Any] = [request.subject_id]
            filters = ["subject_id=?"]
            if request.grade_level_id is not None:
                filters.append("grade_code=(SELECT code FROM school_levels WHERE id=?)")
                parameters.append(request.grade_level_id)
            if request.chapter_ids:
                filters.append(f"chapter_id IN ({','.join('?' for _ in request.chapter_ids)})")
                parameters.extend(request.chapter_ids)
            if request.skill_ids:
                filters.append(f"skill_id IN ({','.join('?' for _ in request.skill_ids)})")
                parameters.extend(request.skill_ids)
            difficulty = self._difficulty(request)
            if difficulty is not None:
                filters.append("difficulty=?")
                parameters.append(difficulty)
            rows = connection.execute(
                f"""SELECT content_id,chapter_id,skill_id,difficulty FROM production_learning_catalog
                WHERE {" AND ".join(filters)}
                ORDER BY chapter_id,skill_id,difficulty,content_id""",
                parameters,
            ).fetchall()
            if request.mode is AssignmentType.GLOBAL_SUBJECT:
                rows = self._balanced(rows)
            unique: list[int] = []
            for row in rows:
                content_id = int(row[0])
                if content_id not in unique:
                    unique.append(content_id)
                if len(unique) == request.exercise_count:
                    break
            return tuple(unique)
        finally:
            connection.close()

    def _difficulty(self, request: HomeworkRequest) -> int | None:
        if request.difficulty is DifficultyMode.ADAPTIVE:
            connection = connect_v2(self.database_path, read_only=True)
            try:
                row = connection.execute(
                    """SELECT avg(m.last_difficulty) FROM longitudinal_mastery_current m
                    JOIN skills sk ON sk.id=m.skill_id JOIN domains d ON d.id=sk.domain_id
                    WHERE m.learner_id=? AND d.subject_id=?""",
                    [request.learner_id, request.subject_id],
                ).fetchone()
                return 3 if not row or row[0] is None else max(1, min(5, round(float(row[0]))))
            finally:
                connection.close()
        return {
            DifficultyMode.EASY: 2,
            DifficultyMode.MEDIUM: 3,
            DifficultyMode.HARD: 4,
        }.get(request.difficulty)

    @staticmethod
    def _balanced(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        groups: dict[int, list[tuple[Any, ...]]] = {}
        for row in rows:
            groups.setdefault(int(row[1]), []).append(row)
        balanced: list[tuple[Any, ...]] = []
        while any(groups.values()):
            for chapter_id in sorted(groups):
                if groups[chapter_id]:
                    balanced.append(groups[chapter_id].pop(0))
        return balanced

    def create_homework(self, request: HomeworkRequest, content_ids: tuple[int, ...]) -> HomeworkAssignment:
        payload = {
            "learner": request.learner_id,
            "actor": request.assigned_by_ref,
            "mode": request.mode.value,
            "subject": request.subject_id,
            "chapters": request.chapter_ids,
            "skills": request.skill_ids,
            "difficulty": request.difficulty.value,
            "count": request.exercise_count,
            "due": request.due_at.isoformat() if request.due_at else None,
        }
        stable_key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute("SELECT id FROM homework_assignments WHERE stable_key=?", [stable_key]).fetchone()
            if row is None:
                row = connection.execute(
                    """INSERT INTO homework_assignments
                    (stable_key,learner_id,assigned_by_type,assigned_by_ref,mode,status,subject_id,
                     grade_level_id,difficulty_mode,requested_exercise_count,target_duration_minutes,
                     due_at,correction_policy,selection_filters,selected_content)
                    VALUES (?,?,?,?,?,'READY',?,?,?,?,?,?,?,?,?) RETURNING id""",
                    [
                        stable_key,
                        request.learner_id,
                        request.assigned_by_type,
                        request.assigned_by_ref,
                        request.mode.value,
                        request.subject_id,
                        request.grade_level_id,
                        request.difficulty.value,
                        request.exercise_count,
                        request.target_duration_minutes,
                        request.due_at,
                        request.correction_policy,
                        json.dumps({"chapter_ids": request.chapter_ids, "skill_ids": request.skill_ids}),
                        json.dumps(content_ids),
                    ],
                ).fetchone()
            homework_id = int(row[0])
        finally:
            connection.close()
        return self.get_homework(homework_id)

    def create_homework_proposal(self, homework_id: int) -> int:
        item = self.get_homework(homework_id)
        connection = connect_v2(self.database_path)
        try:
            existing = connection.execute(
                "SELECT proposal_id FROM learning_session_details d JOIN homework_assignments h ON h.session_id=d.session_id WHERE h.id=?",
                [homework_id],
            ).fetchone()
            if existing:
                return int(existing[0])
            journey = connection.execute(
                """SELECT id FROM learner_journey_versions WHERE learner_id=?
                ORDER BY version_number DESC LIMIT 1""",
                [item.learner_id],
            ).fetchone()
            if journey is None:
                raise ValueError("Le parcours doit être finalisé avant de commencer ce devoir.")
            stable = f"homework:{homework_id}"
            proposal = connection.execute(
                """INSERT INTO personalized_session_proposals
                (stable_id,learner_id,journey_version_id,recommendation_version,scheduled_for,
                 available_minutes,objective_ref,strategy,confidence,result_snapshot,context_hash,correlation_id)
                VALUES (?,?,?,'homework-v1',current_date,?,'homework','balanced_learning',1,'{}',?,?)
                ON CONFLICT(stable_id) DO NOTHING RETURNING id""",
                [stable, item.learner_id, int(journey[0]), item.target_duration_minutes or 30, stable, stable],
            ).fetchone()
            if proposal is None:
                proposal = connection.execute(
                    "SELECT id FROM personalized_session_proposals WHERE stable_id=?", [stable]
                ).fetchone()
            proposal_id = int(proposal[0])
            contents = connection.execute(
                """SELECT content_id,content_version_id,skill_id,subject_id,estimated_minutes,difficulty
                FROM production_learning_catalog WHERE content_id IN
                (SELECT unnest(CAST(selected_content AS BIGINT[])) FROM homework_assignments WHERE id=?)
                ORDER BY content_id""",
                [homework_id],
            ).fetchall()
            for position, row in enumerate(contents, 1):
                connection.execute(
                    """INSERT INTO personalized_session_items
                    (proposal_id,candidate_stable_id,content_id,content_version_id,skill_id,subject_id,
                     position,duration_minutes,difficulty,explanation)
                    SELECT ?,?,?,?,?,?,?,?,?,'["USER_SELECTED_HOMEWORK"]'
                    WHERE NOT EXISTS (
                        SELECT 1 FROM personalized_session_items WHERE proposal_id=? AND content_id=?
                    )""",
                    [
                        proposal_id,
                        f"{stable}:content:{row[0]}",
                        int(row[0]),
                        int(row[1]),
                        int(row[2]),
                        int(row[3]),
                        position,
                        int(row[4]),
                        int(row[5]),
                        proposal_id,
                        int(row[0]),
                    ],
                )
            return proposal_id
        finally:
            connection.close()

    def link_homework_session(self, homework_id: int, session_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """UPDATE homework_assignments SET session_id=?,status='IN_PROGRESS',
                started_at=coalesce(started_at,now()),updated_at=now() WHERE id=?""",
                [session_id, homework_id],
            )
        finally:
            connection.close()

    def get_homework(self, homework_id: int) -> HomeworkAssignment:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT h.id,h.learner_id,h.mode,h.status,h.subject_id,coalesce(s.default_label,'Toutes'),
                h.difficulty_mode,h.requested_exercise_count,h.target_duration_minutes,h.due_at,
                h.selected_content,h.session_id,h.assigned_by_type,h.created_at
                FROM homework_assignments h LEFT JOIN subjects s ON s.id=h.subject_id WHERE h.id=?""",
                [homework_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown homework {homework_id}")
            return HomeworkAssignment(
                int(row[0]),
                int(row[1]),
                AssignmentType(row[2]),
                AssignmentStatus(row[3]),
                None if row[4] is None else int(row[4]),
                str(row[5]),
                DifficultyMode(row[6]),
                int(row[7]),
                None if row[8] is None else int(row[8]),
                row[9],
                tuple(int(item) for item in json.loads(str(row[10]))),
                None if row[11] is None else int(row[11]),
                str(row[12]),
                row[13],
            )
        finally:
            connection.close()

    def list_homework(self, learner_id: int) -> tuple[HomeworkAssignment, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            ids = connection.execute(
                "SELECT id FROM homework_assignments WHERE learner_id=? ORDER BY created_at DESC", [learner_id]
            ).fetchall()
        finally:
            connection.close()
        return tuple(self.get_homework(int(row[0])) for row in ids)

    def update_homework_status(
        self, homework_id: int, learner_id: int, current: AssignmentStatus, target: AssignmentStatus
    ) -> HomeworkAssignment:
        allowed = {
            AssignmentStatus.READY: {AssignmentStatus.IN_PROGRESS, AssignmentStatus.CANCELLED},
            AssignmentStatus.IN_PROGRESS: {AssignmentStatus.PAUSED, AssignmentStatus.COMPLETED},
            AssignmentStatus.PAUSED: {AssignmentStatus.IN_PROGRESS, AssignmentStatus.CANCELLED},
        }
        if target not in allowed.get(current, set()):
            raise ValueError(f"Invalid homework transition: {current.value} -> {target.value}")
        connection = connect_v2(self.database_path)
        try:
            changed = connection.execute(
                """UPDATE homework_assignments SET status=?,updated_at=now(),
                started_at=CASE WHEN ?='IN_PROGRESS' AND started_at IS NULL THEN now() ELSE started_at END,
                completed_at=CASE WHEN ?='COMPLETED' THEN now() ELSE completed_at END
                WHERE id=? AND learner_id=? AND status=? RETURNING id""",
                [target.value, target.value, target.value, homework_id, learner_id, current.value],
            ).fetchone()
            if changed is None:
                raise ValueError("Le devoir a été modifié dans une autre session.")
        finally:
            connection.close()
        return self.get_homework(homework_id)

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT count(*) FROM learner_guardian_links
                WHERE guardian_external_ref=? AND learner_id=? AND active AND revoked_at IS NULL""",
                [parent_ref, learner_id],
            ).fetchone()
            return bool(row and row[0])
        finally:
            connection.close()

    def learner_management_profile(self, learner_id: int) -> LearnerManagementProfile:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT e.learner_id,l.external_ref,e.first_name,e.last_name,e.birth_date,
                j.current_school_level_id,j.target_school_level_id,e.school_year,
                po.kind,p.preferred_subject_ids,p.daily_duration_minutes,p.weekly_schedule,
                p.difficulty_preference,e.preferred_formats,e.error_help_preference,e.diagnostic_status,e.email
                FROM learner_experience_profiles e
                JOIN learner_journeys j ON j.learner_id=e.learner_id
                JOIN learner_journey_preferences p ON p.learner_id=e.learner_id
                JOIN pedagogical_objectives po ON po.id=p.current_objective_ref
                JOIN learners l ON l.id=e.learner_id
                WHERE e.learner_id=? AND l.archived_at IS NULL""",
                [learner_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown learner profile {learner_id}")
            return LearnerManagementProfile(
                int(row[0]),
                str(row[1]),
                str(row[2]),
                None if row[3] is None else str(row[3]),
                row[4],
                int(row[5]),
                None if row[6] is None else int(row[6]),
                str(row[7]),
                str(row[8]),
                tuple(int(item) for item in json.loads(str(row[9]))),
                int(row[10]),
                tuple(
                    (int(item["weekday"]), int(item["duration_minutes"]), str(item["start_time"]))
                    for item in json.loads(str(row[11]))
                ),
                int(row[12]),
                tuple(str(item) for item in json.loads(str(row[13]))),
                str(row[14]),
                str(row[15]),
                None if row[16] is None else str(row[16]),
            )
        finally:
            connection.close()

    def link_parent(self, parent_ref: str, learner_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO learner_guardian_links(guardian_external_ref,learner_id,active)
                VALUES (?,?,TRUE) ON CONFLICT(guardian_external_ref,learner_id)
                DO UPDATE SET active=TRUE,revoked_at=NULL,granted_at=now()""",
                [parent_ref, learner_id],
            )
        finally:
            connection.close()

    def delete_learner(self, parent_ref: str, learner_id: int) -> None:
        """Hard-delete one authorized learner while preserving shared curriculum."""
        connection = connect_v2(self.database_path)
        transaction_active = False
        try:
            connection.execute("BEGIN")
            transaction_active = True
            authorized = connection.execute(
                """SELECT count(*) FROM learner_guardian_links
                WHERE guardian_external_ref=? AND learner_id=? AND active AND revoked_at IS NULL""",
                [parent_ref, learner_id],
            ).fetchone()
            if not authorized or not authorized[0]:
                raise PermissionError("PARENT_ACCESS_DENIED")
            connection.execute("COMMIT")
            transaction_active = False

            session_ids = "SELECT id FROM learning_sessions WHERE learner_id=?"
            activity_ids = f"SELECT id FROM session_activities WHERE session_id IN ({session_ids})"
            answer_ids = f"SELECT id FROM student_answers WHERE activity_id IN ({activity_ids})"
            attempt_ids = "SELECT id FROM attempts WHERE learner_id=?"
            analytics_ids = "SELECT id FROM learning_analytics_snapshots WHERE learner_id=?"
            proposal_ids = "SELECT id FROM personalized_session_proposals WHERE learner_id=?"
            candidate_ids = "SELECT id FROM content_candidate_snapshots WHERE learner_id=?"
            decision_ids = "SELECT id FROM learning_decisions WHERE learner_id=?"
            objective_ids = "SELECT id FROM objectives WHERE learner_id=?"

            statements: tuple[tuple[str, int], ...] = (
                (f"DELETE FROM learning_explanations WHERE snapshot_id IN ({analytics_ids})", 1),
                (f"DELETE FROM recurring_error_observations WHERE snapshot_id IN ({analytics_ids})", 1),
                (f"DELETE FROM parent_learning_insights WHERE snapshot_id IN ({analytics_ids})", 1),
                ("DELETE FROM learning_analytics_snapshots WHERE learner_id=?", 1),
                ("DELETE FROM analytics_calculation_runs WHERE learner_id=?", 1),
                (
                    """DELETE FROM session_mastery_updates WHERE attempt_record_id IN
                    (SELECT id FROM session_attempt_records WHERE learner_id=?)""",
                    1,
                ),
                ("DELETE FROM session_attempt_records WHERE learner_id=?", 1),
                (f"DELETE FROM session_checkpoints WHERE session_id IN ({session_ids})", 1),
                (f"DELETE FROM answer_assessments WHERE answer_id IN ({answer_ids})", 1),
                (f"DELETE FROM student_answers WHERE activity_id IN ({activity_ids})", 1),
                (f"DELETE FROM hint_usage WHERE activity_id IN ({activity_ids})", 1),
                (f"DELETE FROM session_activity_snapshots WHERE activity_id IN ({activity_ids})", 1),
                (f"DELETE FROM session_activities WHERE session_id IN ({session_ids})", 1),
                (f"DELETE FROM session_events WHERE session_id IN ({session_ids})", 1),
                (f"DELETE FROM session_summaries WHERE session_id IN ({session_ids})", 1),
                (f"DELETE FROM session_pause_intervals WHERE session_id IN ({session_ids})", 1),
                (f"DELETE FROM session_state_revisions WHERE session_id IN ({session_ids})", 1),
                ("DELETE FROM decision_refresh_queue WHERE learner_id=?", 1),
                ("DELETE FROM session_command_results WHERE learner_id=?", 1),
                (
                    "DELETE FROM homework_result_summaries WHERE homework_id IN (SELECT id FROM homework_assignments WHERE learner_id=?)",
                    1,
                ),
                ("DELETE FROM homework_assignments WHERE learner_id=?", 1),
                (f"DELETE FROM learning_session_details WHERE session_id IN ({session_ids})", 1),
                ("DELETE FROM revision_history WHERE learner_id=?", 1),
                ("DELETE FROM mastery_events WHERE learner_id=?", 1),
                (f"DELETE FROM attempt_skill_results WHERE attempt_id IN ({attempt_ids})", 1),
                ("DELETE FROM attempts WHERE learner_id=?", 1),
                (f"DELETE FROM session_exercises WHERE session_id IN ({session_ids})", 1),
                (f"DELETE FROM personalized_session_items WHERE proposal_id IN ({proposal_ids})", 1),
                (f"DELETE FROM content_candidate_filter_events WHERE candidate_snapshot_id IN ({candidate_ids})", 1),
                ("DELETE FROM content_candidate_snapshots WHERE learner_id=?", 1),
                ("DELETE FROM personalized_session_proposals WHERE learner_id=?", 1),
                (f"DELETE FROM decision_plan_items WHERE decision_id IN ({decision_ids})", 1),
                (f"DELETE FROM decision_result_snapshots WHERE decision_id IN ({decision_ids})", 1),
                ("DELETE FROM recommendations WHERE learner_id=?", 1),
                ("DELETE FROM ai_conversation_memory WHERE learner_id=?", 1),
                ("DELETE FROM learning_decisions WHERE learner_id=?", 1),
                ("DELETE FROM learning_sessions WHERE learner_id=?", 1),
                ("DELETE FROM learning_domain_events WHERE learner_id=?", 1),
                ("DELETE FROM longitudinal_mastery_events WHERE learner_id=?", 1),
                ("DELETE FROM learning_attempt_inputs WHERE learner_id=?", 1),
                ("DELETE FROM longitudinal_mastery_current WHERE learner_id=?", 1),
                ("DELETE FROM mastery_current WHERE learner_id=?", 1),
                ("DELETE FROM exam_readiness_current WHERE learner_id=?", 1),
                ("DELETE FROM transition_readiness_current WHERE learner_id=?", 1),
                ("DELETE FROM learning_metrics WHERE learner_id=?", 1),
                ("DELETE FROM recommendation_effectiveness WHERE learner_id=?", 1),
                ("DELETE FROM programme_change_proposals WHERE learner_id=?", 1),
                ("DELETE FROM progress_snapshots WHERE learner_id=?", 1),
                ("DELETE FROM study_calendar WHERE learner_id=?", 1),
                (f"DELETE FROM objective_skills WHERE objective_id IN ({objective_ids})", 1),
                ("DELETE FROM objectives WHERE learner_id=?", 1),
                ("DELETE FROM platform_audit_records WHERE learner_id=?", 1),
                ("DELETE FROM onboarding_domain_events WHERE learner_id=?", 1),
                ("DELETE FROM onboarding_sessions WHERE learner_id=?", 1),
                ("DELETE FROM learner_experience_profiles WHERE learner_id=?", 1),
                ("DELETE FROM learner_journey_preferences WHERE learner_id=?", 1),
                ("DELETE FROM learner_journeys WHERE learner_id=?", 1),
                ("DELETE FROM learner_journey_versions WHERE learner_id=?", 1),
                ("DELETE FROM pedagogical_objectives WHERE learner_id=?", 1),
                ("DELETE FROM learner_profiles WHERE learner_id=?", 1),
                ("DELETE FROM learner_functional_profiles WHERE learner_id=?", 1),
            )
            for statement, parameter_count in statements:
                connection.execute("BEGIN")
                transaction_active = True
                connection.execute(statement, [learner_id] * parameter_count)
                connection.execute("COMMIT")
                transaction_active = False
            learner_tables = connection.execute(
                """SELECT DISTINCT table_name FROM information_schema.columns
                WHERE table_schema='main' AND column_name='learner_id'
                AND table_name NOT LIKE 'v_%' AND table_name <> 'learner_guardian_links'"""
            ).fetchall()
            remaining = [
                str(row[0])
                for row in learner_tables
                if connection.execute(
                    f"SELECT count(*) FROM {row[0]} WHERE learner_id=?",
                    [learner_id],
                ).fetchone()[0]
            ]
            if remaining:
                raise RuntimeError(f"Learner cleanup incomplete: {', '.join(sorted(remaining))}")

            connection.execute("BEGIN")
            transaction_active = True
            connection.execute("DELETE FROM learner_guardian_links WHERE learner_id=?", [learner_id])
            connection.execute("COMMIT")
            transaction_active = False

            connection.execute("BEGIN")
            transaction_active = True
            deleted = connection.execute("DELETE FROM learners WHERE id=? RETURNING id", [learner_id]).fetchone()
            if deleted is None:
                raise KeyError(f"Unknown learner {learner_id}")
            connection.execute("COMMIT")
            transaction_active = False
        except Exception:
            if transaction_active:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def reset_diagnostic(self, parent_ref: str, learner_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            changed = connection.execute(
                """UPDATE learner_experience_profiles SET diagnostic_status='PLANNED',updated_at=now()
                WHERE learner_id=? AND EXISTS (
                    SELECT 1 FROM learner_guardian_links
                    WHERE guardian_external_ref=? AND learner_id=? AND active AND revoked_at IS NULL
                ) RETURNING learner_id""",
                [learner_id, parent_ref, learner_id],
            ).fetchone()
            if changed is None:
                raise PermissionError("PARENT_ACCESS_DENIED")
        finally:
            connection.close()

    def save_experience_profile(
        self,
        learner_id: int,
        first_name: str,
        last_name: str | None,
        birth_date: date | None,
        school_year: str,
        programme_code: str,
        preferred_formats: tuple[str, ...],
        error_help_preference: str,
        diagnostic_status: str,
        email: str | None = None,
    ) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO learner_experience_profiles
                (learner_id,first_name,last_name,birth_date,school_year,programme_code,
                 preferred_formats,error_help_preference,diagnostic_status,onboarding_completed_at,updated_at,email)
                VALUES (?,?,?,?,?,?,?,?,?,now(),now(),?)
                ON CONFLICT(learner_id) DO UPDATE SET first_name=excluded.first_name,last_name=excluded.last_name,
                birth_date=excluded.birth_date,school_year=excluded.school_year,
                programme_code=excluded.programme_code,preferred_formats=excluded.preferred_formats,
                error_help_preference=excluded.error_help_preference,diagnostic_status=excluded.diagnostic_status,
                onboarding_completed_at=excluded.onboarding_completed_at,updated_at=now(),email=excluded.email""",
                [
                    learner_id,
                    first_name,
                    last_name,
                    birth_date,
                    school_year,
                    programme_code,
                    json.dumps(preferred_formats),
                    error_help_preference,
                    diagnostic_status,
                    email,
                ],
            )
        finally:
            connection.close()

    def programme_changes(self, learner_id: int) -> tuple[ProgrammeChange, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT id,learner_id,level,change_type,status,current_state,proposed_state,
                reason_codes,evidence_references,expected_benefit_code,proposed_at
                FROM programme_change_proposals WHERE learner_id=? ORDER BY proposed_at DESC""",
                [learner_id],
            ).fetchall()
            return tuple(
                ProgrammeChange(
                    int(row[0]),
                    int(row[1]),
                    int(row[2]),
                    str(row[3]),
                    str(row[4]),
                    json.loads(str(row[5])),
                    json.loads(str(row[6])),
                    tuple(json.loads(str(row[7]))),
                    tuple(json.loads(str(row[8]))),
                    str(row[9]),
                    row[10],
                )
                for row in rows
            )
        finally:
            connection.close()

    def decide_programme_change(
        self, proposal_id: int, parent_ref: str, decision: str, note: str | None = None
    ) -> None:
        target = {"accept": "ACCEPTED", "modify": "MODIFIED", "reject": "REJECTED"}.get(decision)
        if target is None:
            raise ValueError("Unknown programme decision")
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                "SELECT learner_id,level,status FROM programme_change_proposals WHERE id=?", [proposal_id]
            ).fetchone()
            if row is None or int(row[1]) != 3 or str(row[2]) != "PENDING_PARENT":
                raise ValueError("This programme change cannot be decided")
            authorized = connection.execute(
                """SELECT count(*) FROM learner_guardian_links
                WHERE guardian_external_ref=? AND learner_id=? AND active AND revoked_at IS NULL""",
                [parent_ref, int(row[0])],
            ).fetchone()
            if not authorized or not authorized[0]:
                raise PermissionError("PARENT_ACCESS_DENIED")
            connection.execute(
                """UPDATE programme_change_proposals SET status=?,decided_at=now(),
                decided_by_ref=?,decision_note=? WHERE id=?""",
                [target, parent_ref, note, proposal_id],
            )
        finally:
            connection.close()
