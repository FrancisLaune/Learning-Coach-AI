"""Reset family accounts: keep only V1 Parent/1234, remove all learners and homework."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_database_path, get_v2_database_path
from infrastructure.database.v2 import connect_v2, reset_v2_connections
from services.auth.passwords import hash_password

KEEP_PARENT_NAME = "Parent"
KEEP_PARENT_PASSWORD = "1234"


def cleanup_v1() -> list[tuple[int, str, str]]:
    db_path = get_database_path()
    connection = duckdb.connect(str(db_path))
    try:
        rows = connection.execute("SELECT id, name, role FROM users ORDER BY id").fetchall()
        keep_id = None
        for user_id, name, role in rows:
            if str(name) == KEEP_PARENT_NAME and str(role) == "parent":
                keep_id = int(user_id)
                break
        if keep_id is None:
            raise RuntimeError(f"Aucun compte parent '{KEEP_PARENT_NAME}' trouvé en V1.")

        remove_ids = [int(row[0]) for row in rows if int(row[0]) != keep_id]
        for user_id in remove_ids:
            connection.execute("DELETE FROM password_reset_tokens WHERE user_id=?", [user_id])
            connection.execute("DELETE FROM authentication_audit_events WHERE user_id=?", [user_id])
            connection.execute("DELETE FROM users WHERE id=?", [user_id])

        connection.execute(
            "UPDATE users SET pin_hash=?, active=TRUE WHERE id=?",
            [hash_password(KEEP_PARENT_PASSWORD), keep_id],
        )
        remaining = connection.execute("SELECT id, name, role FROM users ORDER BY id").fetchall()
        return [(int(r[0]), str(r[1]), str(r[2])) for r in remaining]
    finally:
        connection.close()


def _delete_learner_direct(connection: duckdb.DuckDBPyConnection, learner_id: int) -> None:
    """Maintenance purge — same cascade as delete_learner without guardian authorization."""
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
        (
            "DELETE FROM virtual_teacher_messages WHERE session_id IN (SELECT id FROM virtual_teacher_sessions WHERE learner_id=?)",
            1,
        ),
        (
            "DELETE FROM virtual_teacher_summaries WHERE session_id IN (SELECT id FROM virtual_teacher_sessions WHERE learner_id=?)",
            1,
        ),
        ("DELETE FROM virtual_teacher_sessions WHERE learner_id=?", 1),
        ("DELETE FROM virtual_teacher_events WHERE learner_id=?", 1),
        ("DELETE FROM virtual_teacher_preferences WHERE learner_id=?", 1),
        ("DELETE FROM learner_guardian_links WHERE learner_id=?", 1),
        ("DELETE FROM learners WHERE id=?", 1),
    )
    for statement, parameter_count in statements:
        connection.execute(statement, [learner_id] * parameter_count)


def cleanup_v2() -> dict[str, int]:
    reset_v2_connections()
    db_path = get_v2_database_path()
    connection = connect_v2(db_path)
    try:
        learner_ids = [int(row[0]) for row in connection.execute("SELECT id FROM learners ORDER BY id").fetchall()]
        for learner_id in learner_ids:
            _delete_learner_direct(connection, learner_id)
    finally:
        connection.close()
        reset_v2_connections()

    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        return {
            "learners": int(connection.execute("SELECT count(*) FROM learners").fetchone()[0]),
            "homework": int(connection.execute("SELECT count(*) FROM homework_assignments").fetchone()[0]),
            "guardian_links": int(connection.execute("SELECT count(*) FROM learner_guardian_links").fetchone()[0]),
            "deleted_learners": len(learner_ids),
        }
    finally:
        connection.close()


def main() -> None:
    print("Nettoyage V1…")
    v1_users = cleanup_v1()
    print("V1 restant:", v1_users)

    print("Nettoyage V2 (élèves + devoirs)…")
    try:
        stats = cleanup_v2()
    except duckdb.IOException as exc:
        raise SystemExit(
            "Impossible d'ouvrir learning_coach_v2.duckdb (fichier verrouillé). "
            "Fermez Streamlit et tout processus utilisant la base, puis relancez."
        ) from exc
    print("V2 après nettoyage:", stats)

    if stats["learners"] != 0 or stats["homework"] != 0:
        raise SystemExit("Nettoyage incomplet : élèves ou devoirs restants.")
    if len(v1_users) != 1 or v1_users[0][1] != KEEP_PARENT_NAME:
        raise SystemExit("Nettoyage V1 incomplet.")
    print("OK — seul Parent/1234 conservé, aucun élève ni devoir.")


if __name__ == "__main__":
    main()
