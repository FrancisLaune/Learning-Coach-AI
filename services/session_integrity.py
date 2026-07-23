"""Read-only database integrity checks for Learning Session records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from infrastructure.database.v2 import connect_v2


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    code: str
    count: int


class SessionIntegrityService:
    checks = {
        "ORPHAN_ACTIVITY": """SELECT count(*) FROM session_activities a
            LEFT JOIN learning_session_details s ON s.session_id=a.session_id
            WHERE s.session_id IS NULL""",
        "ORPHAN_ANSWER": """SELECT count(*) FROM student_answers a
            LEFT JOIN session_activities x ON x.id=a.activity_id WHERE x.id IS NULL""",
        "ORPHAN_ASSESSMENT": """SELECT count(*) FROM answer_assessments a
            LEFT JOIN student_answers x ON x.id=a.answer_id WHERE x.id IS NULL""",
        "ORPHAN_ATTEMPT": """SELECT count(*) FROM session_attempt_records a
            LEFT JOIN answer_assessments x ON x.id=a.assessment_id WHERE x.id IS NULL""",
        "ORPHAN_HINT": """SELECT count(*) FROM hint_usage h
            LEFT JOIN session_activities x ON x.id=h.activity_id WHERE x.id IS NULL""",
        "DUPLICATE_ACTIVITY_ORDER": """SELECT count(*) FROM (
            SELECT session_id,activity_order,count(*) n FROM session_activities
            GROUP BY session_id,activity_order HAVING n>1)""",
        "MASTERY_WITHOUT_ATTEMPT": """SELECT count(*) FROM session_mastery_updates m
            LEFT JOIN session_attempt_records a ON a.id=m.attempt_record_id WHERE a.id IS NULL""",
        "COMPLETED_SESSION_WITHOUT_SUMMARY": """SELECT count(*) FROM learning_session_details d
            LEFT JOIN session_summaries s ON s.session_id=d.session_id
            WHERE d.status='COMPLETED' AND s.id IS NULL""",
        "COMPLETED_ACTIVITY_WITHOUT_ASSESSMENT": """SELECT count(*) FROM session_activities a
            LEFT JOIN session_attempt_records r ON r.activity_id=a.id
            WHERE a.status='COMPLETED' GROUP BY a.id HAVING count(r.id)=0""",
        "INVALID_APPROVED_CONTENT_VERSION": """SELECT count(*) FROM session_activity_snapshots x
            JOIN session_activities a ON a.id=x.activity_id
            LEFT JOIN content_versions v ON v.id=a.content_version_id
            WHERE v.id IS NULL""",
    }

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def inspect(self) -> tuple[IntegrityIssue, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            issues = []
            for code, query in self.checks.items():
                rows = connection.execute(query).fetchall()
                count = sum(int(row[0]) for row in rows)
                if count:
                    issues.append(IntegrityIssue(code, count))
            return tuple(issues)
        finally:
            connection.close()
