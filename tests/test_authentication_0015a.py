from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

import core.database as legacy_database
from services.auth.authorization import require_parent_role, require_student_role
from services.auth.password_reset import generate_reset_token, hash_reset_token
from services.auth.passwords import hash_password, needs_rehash, verify_password
from services.auth.roles import AuthRole, is_known_auth_role


@pytest.fixture()
def auth_db(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    legacy_database.reset_legacy_connections()
    db_path = tmp_path / "legacy-auth.duckdb"
    monkeypatch.setattr(legacy_database, "DB_PATH", db_path)
    monkeypatch.setenv("LCAI_ENABLE_DEMO_CREDENTIALS", "false")
    monkeypatch.setenv("LCAI_AUTH_EMAIL_MODE", "console")
    legacy_database.init_db()
    return db_path


def _create_parent() -> dict:
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
    return parent


def _create_student(parent: dict) -> dict:
    assert legacy_database.create_student_account(
        int(parent["id"]),
        "parent-child:alex",
        "Alex",
        "",
        "alex-test",
        "mot-de-passe-eleve",
        "mot-de-passe-eleve",
    )[0]
    student = legacy_database.authenticate("alex-test", "mot-de-passe-eleve", "student")
    assert student is not None
    return student


def test_password_hashing_uses_pbkdf2_and_supports_legacy(auth_db: Path) -> None:
    hashed = hash_password("secret-password")
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("secret-password", hashed)
    assert not verify_password("wrong", hashed)
    import hashlib

    legacy_hash = hashlib.sha256(b"legacy").hexdigest()
    assert verify_password("legacy", legacy_hash)
    assert needs_rehash(legacy_hash)
    assert not needs_rehash(hashed)


def test_parent_password_reset_flow(auth_db: Path) -> None:
    _create_parent()
    message = legacy_database.request_parent_password_reset("parent@example.test")
    assert "Si un compte correspond" in message
    assert legacy_database.request_parent_password_reset("unknown@example.test") == message

    connection = legacy_database.connect()
    try:
        row = connection.execute(
            "SELECT token_hash FROM password_reset_tokens WHERE purpose='parent_reset'"
        ).fetchone()
        assert row is not None
    finally:
        connection.close()

    token = generate_reset_token()
    connection = legacy_database.connect()
    try:
        connection.execute(
            "UPDATE password_reset_tokens SET token_hash=? WHERE purpose='parent_reset'",
            [hash_reset_token(token)],
        )
    finally:
        connection.close()

    ok, reset_message = legacy_database.complete_password_reset(
        token,
        "nouveau-mot-de-passe",
        "nouveau-mot-de-passe",
    )
    assert ok, reset_message
    assert legacy_database.authenticate("parent@example.test", "nouveau-mot-de-passe", "parent")
    assert legacy_database.authenticate("parent@example.test", "mot-de-passe-parent", "parent") is None
    assert legacy_database.complete_password_reset(token, "x", "x")[0] is False


def test_child_recovery_sends_neutral_response(auth_db: Path) -> None:
    parent = _create_parent()
    _create_student(parent)
    neutral = legacy_database.request_child_password_recovery("parent@example.test", "alex-test")
    assert "Si un compte correspond" in neutral
    assert legacy_database.request_child_password_recovery("parent@example.test", "missing") == neutral


def test_session_invalidated_after_password_reset(auth_db: Path) -> None:
    parent = _create_parent()
    session_user = dict(parent)
    token = generate_reset_token()
    connection = legacy_database.connect()
    try:
        connection.execute(
            """INSERT INTO password_reset_tokens
            (user_id,token_hash,purpose,expires_at,created_at)
            VALUES (?,?,?,now() + INTERVAL '1 hour', now())""",
            [parent["id"], hash_reset_token(token), "parent_reset"],
        )
    finally:
        connection.close()
    assert legacy_database.session_user_still_valid(session_user)
    legacy_database.complete_password_reset(token, "nouveau-mot-de-passe", "nouveau-mot-de-passe")
    assert not legacy_database.session_user_still_valid(session_user)


def test_student_login_rejects_parent_role(auth_db: Path) -> None:
    _create_parent()
    assert legacy_database.authenticate("parent@example.test", "mot-de-passe-parent", "student") is None


def test_weak_password_and_duplicate_email_rejected(auth_db: Path) -> None:
    assert not legacy_database.create_parent("A", "B", "bad", "user1", "abc", "abc")[0]
    assert legacy_database.create_parent(
        "Marie",
        "Martin",
        "dup@example.test",
        "user1",
        "mot-de-passe",
        "mot-de-passe",
    )[0]
    assert not legacy_database.create_parent(
        "Paul",
        "Martin",
        "dup@example.test",
        "user2",
        "mot-de-passe",
        "mot-de-passe",
    )[0]


def test_cross_family_student_management_blocked(
    auth_db: Path, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from infrastructure.database.v2 import connect_v2
    from migrations.runner import apply_migrations

    v2_path = tmp_path / "guardian-v2.duckdb"
    apply_migrations(v2_path)
    monkeypatch.setenv("LCAI_V2_DATABASE_PATH", str(v2_path))

    parent_a = _create_parent()
    assert legacy_database.create_parent(
        "Paul",
        "Martin",
        "other@example.test",
        "other-parent",
        "mot-de-passe-parent",
        "mot-de-passe-parent",
    )[0]
    parent_b = legacy_database.authenticate("other@example.test", "mot-de-passe-parent", "parent")
    assert parent_b is not None

    connection = connect_v2(v2_path)
    try:
        learner_id = int(
            connection.execute(
                "INSERT INTO learners(external_ref,display_name) VALUES ('parent-child:alex','Alex') RETURNING id"
            ).fetchone()[0]
        )
        connection.execute(
            """INSERT INTO learner_guardian_links(guardian_external_ref,learner_id,active)
            VALUES (?,?,TRUE)""",
            [str(parent_a["id"]), learner_id],
        )
    finally:
        connection.close()

    blocked, _ = legacy_database.create_student_account(
        int(parent_b["id"]),
        "parent-child:alex",
        "Alex",
        "",
        "alex-hijack",
        "mot-de-passe-eleve",
        "mot-de-passe-eleve",
    )
    assert not blocked

    allowed, _ = legacy_database.create_student_account(
        int(parent_a["id"]),
        "parent-child:alex",
        "Alex",
        "",
        "alex-test",
        "mot-de-passe-eleve",
        "mot-de-passe-eleve",
    )
    assert allowed
    assert not legacy_database.reset_student_password(
        int(parent_b["id"]),
        "parent-child:alex",
        "hacked-password",
        "hacked-password",
    )[0]


def test_unknown_role_rejected_at_authentication(auth_db: Path) -> None:
    parent = _create_parent()
    connection = legacy_database.connect()
    try:
        connection.execute("UPDATE users SET role='administrator' WHERE id=?", [parent["id"]])
    finally:
        connection.close()
    assert legacy_database.authenticate("parent@example.test", "mot-de-passe-parent", "parent") is None


def test_session_role_tampering_rejected(auth_db: Path) -> None:
    parent = _create_parent()
    student = _create_student(parent)
    assert legacy_database.session_user_still_valid(dict(parent))
    escalated = dict(student)
    escalated["role"] = AuthRole.PARENT
    assert not legacy_database.session_user_still_valid(escalated)
    tampered = dict(parent)
    tampered["role"] = "administrator"
    assert not legacy_database.session_user_still_valid(tampered)


def test_auth_role_helpers_and_service_guards(auth_db: Path) -> None:
    parent = _create_parent()
    student = _create_student(parent)
    assert is_known_auth_role(AuthRole.PARENT)
    assert not is_known_auth_role("administrator")
    assert require_parent_role(parent)["id"] == parent["id"]
    assert require_student_role(student)["id"] == student["id"]
    with pytest.raises(PermissionError):
        require_parent_role(student)
    with pytest.raises(PermissionError):
        require_student_role(parent)
