from __future__ import annotations

from datetime import date
from pathlib import Path

from pytest import MonkeyPatch

import core.database as legacy_database
from services.academic_year import academic_year_options, default_academic_year, parse_academic_year


def test_parent_account_requires_email_and_authenticates(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_database, "DB_PATH", tmp_path / "legacy.duckdb")
    monkeypatch.setenv("LCAI_ENABLE_DEMO_CREDENTIALS", "false")
    legacy_database.init_db()

    ok, message = legacy_database.create_parent(
        "Marie",
        "Martin",
        "marie.martin@example.test",
        "marie-martin",
        "mot-de-passe",
        "mot-de-passe",
    )

    assert ok, message
    parent = legacy_database.authenticate("marie-martin", "mot-de-passe")
    assert parent is not None
    assert parent["role"] == "parent"


def test_parent_account_rejects_invalid_or_duplicate_email(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_database, "DB_PATH", tmp_path / "legacy.duckdb")
    monkeypatch.setenv("LCAI_ENABLE_DEMO_CREDENTIALS", "false")
    legacy_database.init_db()

    ok, _ = legacy_database.create_parent("Marie", "Martin", "invalide", "marie", "mot-de-passe", "mot-de-passe")
    assert not ok
    assert legacy_database.create_parent(
        "Marie",
        "Martin",
        "famille@example.test",
        "marie",
        "mot-de-passe",
        "mot-de-passe",
    )[0]
    ok, message = legacy_database.create_parent(
        "Paul",
        "Martin",
        "famille@example.test",
        "paul",
        "mot-de-passe",
        "mot-de-passe",
    )
    assert not ok
    assert "adresse e-mail" in message


def test_parent_manages_secure_student_credentials(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_database, "DB_PATH", tmp_path / "legacy.duckdb")
    monkeypatch.setenv("LCAI_ENABLE_DEMO_CREDENTIALS", "false")
    legacy_database.init_db()
    assert legacy_database.create_parent(
        "Marie",
        "Martin",
        "parent@example.test",
        "parent-test",
        "mot-de-passe-parent",
        "mot-de-passe-parent",
    )[0]
    parent = legacy_database.authenticate("parent@example.test", "mot-de-passe-parent", "parent")
    assert parent is not None

    ok, message = legacy_database.create_student_account(
        int(parent["id"]),
        "parent-child:alexandre",
        "Alexandre",
        "alexandre@example.test",
        "alexandre-test",
        "mot-de-passe-eleve",
        "mot-de-passe-eleve",
    )
    assert ok, message
    student = legacy_database.authenticate("alexandre@example.test", "mot-de-passe-eleve", "student")
    assert student is not None
    assert student["learner_external_ref"] == "parent-child:alexandre"
    assert legacy_database.authenticate("alexandre-test", "mot-de-passe-eleve", "parent") is None
    account = legacy_database.student_account_for_learner("parent-child:alexandre")
    assert account == {
        "id": student["id"],
        "username": "alexandre-test",
        "email": "alexandre@example.test",
        "active": True,
    }
    assert legacy_database.has_active_student_account("parent-child:alexandre")

    connection = legacy_database.connect()
    try:
        stored_hash = connection.execute(
            "SELECT pin_hash FROM users WHERE learner_external_ref='parent-child:alexandre'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert stored_hash != "mot-de-passe-eleve"
    assert stored_hash == legacy_database.pin_hash("mot-de-passe-eleve")

    assert legacy_database.reset_student_password(
        int(parent["id"]),
        "parent-child:alexandre",
        "nouveau-mot-de-passe",
        "nouveau-mot-de-passe",
    )[0]
    assert legacy_database.authenticate("alexandre-test", "mot-de-passe-eleve", "student") is None
    assert legacy_database.authenticate("alexandre-test", "nouveau-mot-de-passe", "student") is not None

    legacy_database.deactivate_student_account(int(parent["id"]), "parent-child:alexandre")
    assert legacy_database.authenticate("alexandre-test", "nouveau-mot-de-passe", "student") is None
    assert not legacy_database.has_active_student_account("parent-child:alexandre")
    legacy_database.delete_student_account(int(parent["id"]), "parent-child:alexandre")
    assert legacy_database.student_account_for_learner("parent-child:alexandre") is None


def test_student_or_unknown_actor_cannot_create_student_account(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_database, "DB_PATH", tmp_path / "legacy.duckdb")
    monkeypatch.setenv("LCAI_ENABLE_DEMO_CREDENTIALS", "false")
    legacy_database.init_db()

    ok, message = legacy_database.create_student_account(
        999,
        "learner:unauthorized",
        "Intrus",
        "intrus@example.test",
        "intrus",
        "mot-de-passe",
        "mot-de-passe",
    )
    assert not ok
    assert "parent authentifié" in message


def test_orphan_detection_repair_and_one_account_per_learner(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_database, "DB_PATH", tmp_path / "legacy.duckdb")
    monkeypatch.setenv("LCAI_ENABLE_DEMO_CREDENTIALS", "false")
    legacy_database.init_db()
    assert legacy_database.create_parent(
        "Parent",
        "Orphelin",
        "parent.orphelin@example.test",
        "parent-orphelin",
        "mot-de-passe-parent",
        "mot-de-passe-parent",
    )[0]
    parent = legacy_database.authenticate("parent-orphelin", "mot-de-passe-parent", "parent")
    assert parent is not None
    orphan_ref = "parent-child:orphan"
    other_ref = "parent-child:other"

    assert legacy_database.student_account_for_learner(orphan_ref) is None
    assert not legacy_database.has_active_student_account(orphan_ref)
    assert legacy_database.create_student_account(
        int(parent["id"]),
        orphan_ref,
        "KID1",
        "kid1@example.test",
        "kid1",
        "mot-de-passe-kid1",
        "mot-de-passe-kid1",
    )[0]
    assert legacy_database.has_active_student_account(orphan_ref)
    assert legacy_database.student_account_for_learner(other_ref) is None

    duplicate_ok, _ = legacy_database.create_student_account(
        int(parent["id"]),
        orphan_ref,
        "KID1",
        "kid1.duplicate@example.test",
        "kid1-duplicate",
        "mot-de-passe-kid1",
        "mot-de-passe-kid1",
    )
    assert not duplicate_ok
    connection = legacy_database.connect()
    try:
        assert connection.execute(
            """SELECT count(*) FROM users
            WHERE learner_external_ref=? AND role='student' AND active""",
            [orphan_ref],
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM users WHERE role='parent' AND learner_external_ref IS NOT NULL"
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_school_year_options_switch_in_july_and_are_consecutive() -> None:
    assert default_academic_year(date(2026, 6, 30)) == "2025-2026"
    assert default_academic_year(date(2026, 7, 1)) == "2026-2027"
    assert "2026-2027" in academic_year_options(date(2026, 7, 1))
    parsed = parse_academic_year("2026-2027")
    assert parsed.start_year == 2026
    assert parsed.end_year == 2027
