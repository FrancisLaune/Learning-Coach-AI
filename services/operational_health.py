"""Read-only operational health checks for the optional V2 session system."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.config import (
    get_v2_database_path,
    is_v2_parent_dashboard_enabled,
    is_v2_session_execution_enabled,
    is_v2_ui_enabled,
)
from infrastructure.database.v2 import connect_v2


@dataclass(frozen=True, slots=True)
class HealthCheck:
    name: str
    healthy: bool
    detail: str


@dataclass(frozen=True, slots=True)
class OperationalHealth:
    healthy: bool
    checks: tuple[HealthCheck, ...]


class OperationalHealthService:
    required_tables = (
        "learning_session_details",
        "session_activities",
        "student_answers",
        "answer_assessments",
        "session_attempt_records",
        "session_checkpoints",
        "session_command_results",
    )
    required_views = ("approved_learning_catalog", "v_active_learning_sessions", "v_session_progress")

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or get_v2_database_path()

    def check(self) -> OperationalHealth:
        checks: list[HealthCheck] = [
            HealthCheck("v1_default", not is_v2_ui_enabled(), "V1 remains default unless explicitly enabled"),
            HealthCheck("v2_ui_flag", True, f"enabled={is_v2_ui_enabled()}"),
            HealthCheck("session_execution_flag", True, f"enabled={is_v2_session_execution_enabled()}"),
            HealthCheck("parent_dashboard_flag", True, f"enabled={is_v2_parent_dashboard_enabled()}"),
        ]
        try:
            connection = connect_v2(self.database_path, read_only=True)
            try:
                names = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                    ).fetchall()
                }
                checks.append(HealthCheck("database", True, "DuckDB V2 accessible"))
                for table in self.required_tables:
                    checks.append(
                        HealthCheck(f"table:{table}", table in names, "present" if table in names else "missing")
                    )
                for view in self.required_views:
                    checks.append(HealthCheck(f"view:{view}", view in names, "present" if view in names else "missing"))
                migration = connection.execute("SELECT max(version) FROM schema_versions").fetchone()
                checks.append(
                    HealthCheck("migration_level", bool(migration and migration[0]), f"version={migration[0]}")
                )
                approved = connection.execute("SELECT count(*) FROM approved_learning_catalog").fetchone()
                checks.append(HealthCheck("approved_catalog", True, f"items={int(approved[0])}"))
            finally:
                connection.close()
        except Exception as error:
            checks.append(HealthCheck("database", False, type(error).__name__))
        return OperationalHealth(all(item.healthy for item in checks), tuple(checks))
