from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import duckdb
import pytest

from application.experience_controllers import ParentExperienceController, PresentationError
from application.session_application import Actor, ActorRole, SessionApplicationService
from domain.learning_session.errors import SessionApplicationError, SessionErrorCode
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.session_integration import DuckDBSessionIntegrationGateway
from migrations.runner import apply_migrations
from services.learning_session.experience import LearnerExperienceService
from services.operational_health import OperationalHealthService
from services.session_integrity import SessionIntegrityService
from tests.test_learning_experience import MemoryReadModel


@pytest.fixture
def integrated_database(tmp_path: Path) -> tuple[Path, int]:
    path = tmp_path / "integration.duckdb"
    apply_migrations(path)
    connection = connect_v2(path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('student-1','Alexandre') RETURNING id"
            ).fetchone()[0]
        )
        connection.execute(
            """INSERT INTO learner_guardian_links(guardian_external_ref,learner_id)
            VALUES ('parent-1',?)""",
            [learner_id],
        )
    finally:
        connection.close()
    return path, learner_id


def test_parent_authorization_is_explicit_and_parameterized(
    integrated_database: tuple[Path, int],
) -> None:
    path, learner_id = integrated_database
    gateway = DuckDBSessionIntegrationGateway(path)
    assert gateway.parent_authorized("parent-1", learner_id)
    assert not gateway.parent_authorized("' OR TRUE --", learner_id)
    assert not gateway.parent_authorized("parent-1", learner_id + 1)


def test_parent_controller_filters_and_rejects_unauthorized_learners() -> None:
    class Authorization:
        def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
            return parent_ref == "parent-1" and learner_id == 7

    controller = ParentExperienceController(LearnerExperienceService(MemoryReadModel()), Authorization())
    assert controller.learners("parent-1") == ((7, "Alexandre"),)
    denied = controller.dashboard("parent-2", 7)
    assert isinstance(denied, PresentationError)
    assert "Alexandre" not in denied.message


def test_application_service_rejects_cross_learner_access_before_query() -> None:
    class Gateway:
        def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
            return False

        def active_session(self, learner_id: int) -> None:
            raise AssertionError("Unauthorized query must not reach persistence")

    service = SessionApplicationService(
        cast(Any, Gateway()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
    )
    with pytest.raises(SessionApplicationError) as captured:
        service.get_active_session(Actor("student-1", ActorRole.STUDENT, 1), 2)
    assert captured.value.code is SessionErrorCode.SESSION_ACCESS_DENIED


def test_command_idempotency_key_is_unique(integrated_database: tuple[Path, int]) -> None:
    path, learner_id = integrated_database
    connection = connect_v2(path)
    try:
        connection.execute(
            """INSERT INTO session_command_results
            (idempotency_key,learner_id,command_type,correlation_id,result_payload)
            VALUES ('same-key',?,'START_SESSION','corr-1','{}')""",
            [learner_id],
        )
        with pytest.raises(duckdb.ConstraintException):
            connection.execute(
                """INSERT INTO session_command_results
                (idempotency_key,learner_id,command_type,correlation_id,result_payload)
                VALUES ('same-key',?,'START_SESSION','corr-2','{}')""",
                [learner_id],
            )
    finally:
        connection.close()


def test_operational_health_is_read_only_and_reports_migration(
    integrated_database: tuple[Path, int],
) -> None:
    path, learner_id = integrated_database
    before = path.stat().st_size
    result = OperationalHealthService(path).check()
    assert result.healthy
    assert any(item.name == "migration_level" and "16" in item.detail for item in result.checks)
    assert path.stat().st_size == before
    connection = connect_v2(path, read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM learners WHERE id=?", [learner_id]).fetchone() == (1,)
    finally:
        connection.close()


def test_integrity_checks_report_no_orphans_on_reconstructed_database(
    integrated_database: tuple[Path, int],
) -> None:
    path, _ = integrated_database
    assert SessionIntegrityService(path).inspect() == ()


def test_structured_error_does_not_render_technical_message() -> None:
    error = SessionApplicationError(
        SessionErrorCode.STATE_CONFLICT,
        "Actualisez la séance.",
        "database path and SQL detail",
        True,
        True,
        "corr-1",
        "Rechargez la page.",
    )
    assert "database path" not in str(error)
    assert error.correlation_id == "corr-1"
