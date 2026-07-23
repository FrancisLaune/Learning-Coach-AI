"""Repeatable local read-model benchmark for LCAI-0010 Part 05."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.experience import DuckDBExperienceReadModel
from migrations.runner import apply_migrations
from services.learning_session.experience import LearnerExperienceService


def _seed(path: Path) -> int:
    apply_migrations(path)
    connection = connect_v2(path)
    now = datetime.now(UTC)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(display_name,external_ref) VALUES ('Benchmark','benchmark') RETURNING id"
            ).fetchone()[0]
        )
        journey_id = int(
            connection.execute(
                """INSERT INTO learner_journey_versions
                (learner_id,version_number,journey_snapshot,effective_from,changed_by_role,
                 context_hash,correlation_id)
                VALUES (?,1,'{}',?,'administrator','benchmark','benchmark-journey') RETURNING id""",
                [learner_id, now],
            ).fetchone()[0]
        )
        proposal_id = int(
            connection.execute(
                """INSERT INTO personalized_session_proposals
                (stable_id,learner_id,journey_version_id,recommendation_version,scheduled_for,
                 available_minutes,objective_ref,confidence,result_snapshot,context_hash,correlation_id)
                VALUES ('benchmark-proposal',?,?,'v1',?,25,'benchmark',1,'{}','benchmark',
                        'benchmark-proposal-correlation') RETURNING id""",
                [learner_id, journey_id, now],
            ).fetchone()[0]
        )
        for _ in range(100):
            session_id = int(
                connection.execute(
                    """INSERT INTO learning_sessions(learner_id,kind,status,planned_duration_seconds)
                    VALUES (?,'practice','completed',1500) RETURNING id""",
                    [learner_id],
                ).fetchone()[0]
            )
            connection.execute(
                """INSERT INTO learning_session_details
                (session_id,journey_version_id,proposal_id,status,creation_time,start_time,end_time,
                 planned_duration_seconds,actual_duration_seconds,estimated_mastery_gain,
                 completion_rate,session_score,application_version,curriculum_version,
                 content_version,decision_engine_version,assessment_engine_version)
                VALUES (?,?,?,'COMPLETED',?,?,?,1500,1200,2,100,80,'benchmark','v1','v1','v1','v1')""",
                [session_id, journey_id, proposal_id, now, now, now],
            )
            connection.execute(
                """INSERT INTO session_summaries
                (session_id,completion_rate,average_time_ms,total_score,mastery_gain)
                VALUES (?,100,1000,80,2)""",
                [session_id],
            )
        rows = [
            (
                f"benchmark-attempt-{index}",
                learner_id,
                10001,
                now,
                json.dumps({"correctness": 0.8}),
                json.dumps({"score": 0.8}),
            )
            for index in range(1000)
        ]
        connection.executemany(
            """INSERT INTO learning_attempt_inputs
            (stable_id,learner_id,skill_id,occurred_at,input_snapshot,result_snapshot)
            VALUES (?,?,?,?,?,?)""",
            rows,
        )
        return learner_id
    finally:
        connection.close()


def measure(iterations: int = 100) -> dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="lcai-part05-") as directory:
        path = Path(directory) / "benchmark.duckdb"
        learner_id = _seed(path)
        service = LearnerExperienceService(DuckDBExperienceReadModel(path))
        durations = []
        for _ in range(iterations):
            started = perf_counter()
            dashboard = service.dashboard(learner_id)
            durations.append((perf_counter() - started) * 1000)
            assert len(dashboard.recent_sessions) == 5
        ordered = sorted(durations)
        p95 = ordered[max(0, round(len(ordered) * 0.95) - 1)]
        return {
            "iterations": float(iterations),
            "student_dashboard_average_ms": statistics.mean(durations),
            "student_dashboard_p95_ms": p95,
            "completed_sessions": 100.0,
            "attempts": 1000.0,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    arguments = parser.parse_args()
    print(json.dumps(measure(arguments.iterations), indent=2))


if __name__ == "__main__":
    main()
