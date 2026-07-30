from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime, timedelta
from time import sleep
from typing import Any

import duckdb
import pandas as pd

from core.config import (
    get_database_path,
    get_demo_parent_credentials,
    get_password_reset_base_url,
    is_demo_credentials_enabled,
)
from services.auth.email_delivery import deliver_auth_email
from services.auth.email_templates import (
    child_password_recovery_requested_email,
    parent_password_reset_email,
    password_changed_notification_email,
)
from services.auth.password_reset import (
    DEFAULT_EXPIRY_MINUTES,
    RESET_PURPOSE_CHILD,
    RESET_PURPOSE_PARENT,
    generate_reset_token,
    hash_reset_token,
    neutral_recovery_message,
)
from services.auth.passwords import hash_password, needs_rehash, verify_password
from services.auth.roles import is_known_auth_role

DB_PATH = get_database_path()

LOCK_RETRY_ATTEMPTS = 6
LOCK_RETRY_DELAY_SECONDS = 0.3

_connections: dict[str, duckdb.DuckDBPyConnection] = {}


class _LegacyConnection:
    """Reuse one DuckDB handle per database file within a process (Windows-safe)."""

    __slots__ = ("_inner",)

    def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
        self._inner = inner

    def close(self) -> None:
        return  # Shared handle; call reset_legacy_connections() for teardown.

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __enter__(self) -> _LegacyConnection:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def reset_legacy_connections() -> None:
    """Close all cached legacy connections (tests and maintenance scripts)."""
    for connection in _connections.values():
        connection.close()
    _connections.clear()


def _open_legacy_connection() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = str(DB_PATH.resolve())
    cached = _connections.get(key)
    if cached is not None:
        return _LegacyConnection(cached)  # type: ignore[return-value]

    last_error: duckdb.IOException | None = None
    for attempt in range(LOCK_RETRY_ATTEMPTS):
        try:
            connection = duckdb.connect(key)
            _connections[key] = connection
            return _LegacyConnection(connection)  # type: ignore[return-value]
        except duckdb.IOException as exc:
            last_error = exc
            if attempt >= LOCK_RETRY_ATTEMPTS - 1:
                raise
            sleep(LOCK_RETRY_DELAY_SECONDS * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to open legacy database at {key}")


def connect() -> duckdb.DuckDBPyConnection:
    return _open_legacy_connection()


def connect_readonly() -> duckdb.DuckDBPyConnection:
    """Prefer ``connect()`` in the Streamlit runtime: DuckDB rejects mixed RO/RW handles."""
    return _open_legacy_connection()


def _parent_owns_learner(parent_user_id: int, learner_external_ref: str) -> bool:
    from services.auth.authorization import parent_owns_learner

    return parent_owns_learner(parent_user_id, learner_external_ref)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def pin_hash(pin: str) -> str:
    return hash_password(pin)


def init_db() -> None:
    con = connect()
    con.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_users START 1;
        CREATE SEQUENCE IF NOT EXISTS seq_exam START 1;
        CREATE SEQUENCE IF NOT EXISTS seq_exam_question START 1;
        CREATE SEQUENCE IF NOT EXISTS seq_practice START 1;
        CREATE SEQUENCE IF NOT EXISTS seq_session START 1;

        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_users'),
            name VARCHAR UNIQUE NOT NULL,
            pin_hash VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL
        );
        ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS learner_external_ref VARCHAR;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_epoch BIGINT DEFAULT 0;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_learner_external_ref
            ON users(learner_external_ref);

        CREATE SEQUENCE IF NOT EXISTS seq_auth_event START 1;

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_auth_event'),
            user_id BIGINT NOT NULL,
            token_hash VARCHAR NOT NULL,
            purpose VARCHAR NOT NULL,
            learner_external_ref VARCHAR,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash
            ON password_reset_tokens(token_hash);

        CREATE TABLE IF NOT EXISTS authentication_audit_events (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_auth_event'),
            event_type VARCHAR NOT NULL,
            user_id BIGINT,
            learner_external_ref VARCHAR,
            detail VARCHAR,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS exams (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_exam'),
            user_id BIGINT NOT NULL,
            subject VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            mode VARCHAR NOT NULL,
            duration_minutes INTEGER,
            status VARCHAR NOT NULL,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            score DOUBLE,
            percentage DOUBLE,
            correct_count INTEGER DEFAULT 0,
            question_count INTEGER DEFAULT 0,
            difficulty VARCHAR DEFAULT 'Moyen',
            target_seconds_per_question INTEGER DEFAULT 90,
            elapsed_seconds DOUBLE DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS exam_questions (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_exam_question'),
            exam_id BIGINT NOT NULL,
            position INTEGER NOT NULL,
            chapter VARCHAR NOT NULL,
            question VARCHAR NOT NULL,
            answer_type VARCHAR NOT NULL,
            expected_answer VARCHAR NOT NULL,
            accepted_answers VARCHAR,
            unit VARCHAR,
            explanation VARCHAR NOT NULL,
            student_answer VARCHAR,
            is_correct BOOLEAN DEFAULT FALSE,
            difficulty VARCHAR DEFAULT 'Moyen',
            target_seconds INTEGER DEFAULT 90,
            elapsed_seconds DOUBLE DEFAULT 0,
            error_type VARCHAR
        );

        CREATE TABLE IF NOT EXISTS practice_attempts (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_practice'),
            user_id BIGINT NOT NULL,
            subject VARCHAR NOT NULL,
            chapter VARCHAR NOT NULL,
            question VARCHAR NOT NULL,
            expected_answer VARCHAR NOT NULL,
            student_answer VARCHAR,
            is_correct BOOLEAN NOT NULL,
            difficulty VARCHAR DEFAULT 'Moyen',
            created_at TIMESTAMP NOT NULL,
            elapsed_seconds DOUBLE DEFAULT 0,
            target_seconds INTEGER DEFAULT 90,
            error_type VARCHAR
        );

        CREATE TABLE IF NOT EXISTS learning_sessions (
            id BIGINT PRIMARY KEY DEFAULT nextval('seq_session'),
            user_id BIGINT NOT NULL, subject VARCHAR NOT NULL, session_type VARCHAR NOT NULL,
            difficulty VARCHAR, started_at TIMESTAMP NOT NULL, finished_at TIMESTAMP,
            elapsed_seconds DOUBLE DEFAULT 0, question_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0, percentage DOUBLE DEFAULT 0
        );
        ALTER TABLE exams ADD COLUMN IF NOT EXISTS difficulty VARCHAR DEFAULT 'Moyen';
        ALTER TABLE exams ADD COLUMN IF NOT EXISTS target_seconds_per_question INTEGER DEFAULT 90;
        ALTER TABLE exams ADD COLUMN IF NOT EXISTS elapsed_seconds DOUBLE DEFAULT 0;
        ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS difficulty VARCHAR DEFAULT 'Moyen';
        ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS target_seconds INTEGER DEFAULT 90;
        ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS elapsed_seconds DOUBLE DEFAULT 0;
        ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS error_type VARCHAR;
        ALTER TABLE practice_attempts ADD COLUMN IF NOT EXISTS elapsed_seconds DOUBLE DEFAULT 0;
        ALTER TABLE practice_attempts ADD COLUMN IF NOT EXISTS target_seconds INTEGER DEFAULT 90;
        ALTER TABLE practice_attempts ADD COLUMN IF NOT EXISTS error_type VARCHAR;
        ALTER TABLE practice_attempts ADD COLUMN IF NOT EXISTS difficulty VARCHAR DEFAULT 'Moyen';
    """)
    demo_name, demo_password = get_demo_parent_credentials()
    exists = con.execute("SELECT COUNT(*) FROM users WHERE name=?", [demo_name]).fetchone()[0]
    if is_demo_credentials_enabled() and not exists:
        con.execute(
            """INSERT INTO users(name,pin_hash,role,created_at,first_name,last_name)
            VALUES (?,?,?,?,?,?)""",
            [demo_name, pin_hash(demo_password), "parent", datetime.now(), "Parent", "Démo"],
        )
    con.close()


def create_user(name: str, pin: str) -> tuple[bool, str]:
    name = name.strip()
    if len(name) < 2:
        return False, "Le prénom doit contenir au moins deux caractères."
    if len(pin) < 4:
        return False, "Le code PIN doit contenir au moins quatre caractères."
    con = connect()
    try:
        con.execute(
            "INSERT INTO users(name,pin_hash,role,created_at) VALUES (?,?,?,?)",
            [name, pin_hash(pin), "student", datetime.now()],
        )
        return True, "Compte enfant créé."
    except Exception:
        return False, "Ce nom existe déjà."
    finally:
        con.close()


def create_parent(
    first_name: str,
    last_name: str,
    email: str,
    username: str,
    password: str,
    password_confirmation: str,
) -> tuple[bool, str]:
    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()
    username = username.strip()
    if not first_name or not last_name:
        return False, "Le prénom et le nom sont obligatoires."
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return False, "L'adresse e-mail n'est pas valide."
    if len(username) < 3:
        return False, "L'identifiant doit contenir au moins trois caractères."
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins huit caractères."
    if password != password_confirmation:
        return False, "La confirmation du mot de passe ne correspond pas."
    con = connect()
    try:
        con.execute(
            """INSERT INTO users(name,pin_hash,role,created_at,first_name,last_name,email)
            VALUES (?,?,?,now(),?,?,?)""",
            [username, pin_hash(password), "parent", first_name, last_name, email],
        )
        return True, "Compte parent créé. Vous pouvez maintenant vous connecter."
    except duckdb.ConstraintException:
        return False, "Cet identifiant ou cette adresse e-mail existe déjà."
    finally:
        con.close()


def create_student_account(
    parent_user_id: int,
    learner_external_ref: str,
    first_name: str,
    email: str,
    username: str,
    password: str,
    password_confirmation: str,
) -> tuple[bool, str]:
    learner_external_ref = learner_external_ref.strip()
    first_name = first_name.strip()
    email = email.strip().lower()
    username = username.strip()
    if not learner_external_ref or not first_name:
        return False, "L'identité de l'élève est incomplète."
    if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
        return False, "L'adresse e-mail de l'élève n'est pas valide."
    if len(username) < 3:
        return False, "L'identifiant élève doit contenir au moins trois caractères."
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins huit caractères."
    if password != password_confirmation:
        return False, "La confirmation du mot de passe ne correspond pas."
    con = connect()
    try:
        parent = con.execute(
            "SELECT id FROM users WHERE id=? AND role='parent' AND active",
            [parent_user_id],
        ).fetchone()
        if parent is None:
            return False, "Seul un parent authentifié peut créer un compte élève."
        if not _parent_owns_learner(parent_user_id, learner_external_ref):
            return False, "Ce profil élève n'appartient pas à votre espace familial."
        con.execute("BEGIN TRANSACTION")
        con.execute(
            """INSERT INTO users
            (name,pin_hash,role,created_at,first_name,email,learner_external_ref,active)
            VALUES (?,?,?,now(),?,?,?,TRUE)""",
            [username, pin_hash(password), "student", first_name, email or None, learner_external_ref],
        )
        linked = con.execute(
            """SELECT count(*) FROM users
            WHERE learner_external_ref=? AND role='student' AND active""",
            [learner_external_ref],
        ).fetchone()
        if linked != (1,):
            raise RuntimeError("STUDENT_ACCOUNT_LINK_VERIFICATION_FAILED")
        con.execute("COMMIT")
        return True, "Compte élève créé."
    except duckdb.ConstraintException:
        with suppress(duckdb.TransactionException):
            con.execute("ROLLBACK")
        return False, "Cet identifiant, cette adresse e-mail ou ce profil élève existe déjà."
    except Exception:
        with suppress(duckdb.TransactionException):
            con.execute("ROLLBACK")
        return False, "Le compte élève n'a pas pu être vérifié. Aucun compte partiel n'a été conservé."
    finally:
        con.close()


def student_account_for_learner(learner_external_ref: str) -> dict[str, Any] | None:
    con = connect()
    try:
        row = con.execute(
            """SELECT id,name,email,active FROM users
            WHERE learner_external_ref=? AND role='student'""",
            [learner_external_ref],
        ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "username": str(row[1]),
            "email": None if row[2] is None else str(row[2]),
            "active": bool(row[3]),
        }
    finally:
        con.close()


def has_active_student_account(learner_external_ref: str) -> bool:
    account = student_account_for_learner(learner_external_ref)
    return bool(account and account["active"])


def reset_student_password(
    parent_user_id: int,
    learner_external_ref: str,
    password: str,
    password_confirmation: str,
) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins huit caractères."
    if password != password_confirmation:
        return False, "La confirmation du mot de passe ne correspond pas."
    con = connect()
    try:
        parent = con.execute(
            "SELECT id FROM users WHERE id=? AND role='parent' AND active",
            [parent_user_id],
        ).fetchone()
        if parent is None:
            return False, "Seul un parent authentifié peut réinitialiser ce mot de passe."
        if not _parent_owns_learner(parent_user_id, learner_external_ref):
            return False, "Ce profil élève n'appartient pas à votre espace familial."
        changed = con.execute(
            """UPDATE users SET pin_hash=?, auth_epoch=COALESCE(auth_epoch,0)+1
            WHERE learner_external_ref=? AND role='student' AND active
            RETURNING id""",
            [pin_hash(password), learner_external_ref],
        ).fetchone()
        if changed is None:
            return False, "Aucun compte élève actif n'est associé à ce profil."
        return True, "Le mot de passe de l'élève a été réinitialisé."
    finally:
        con.close()


def deactivate_student_account(parent_user_id: int, learner_external_ref: str) -> None:
    con = connect()
    try:
        parent = con.execute(
            "SELECT id FROM users WHERE id=? AND role='parent' AND active",
            [parent_user_id],
        ).fetchone()
        if parent is None:
            raise PermissionError("PARENT_ACCESS_DENIED")
        if not _parent_owns_learner(parent_user_id, learner_external_ref):
            raise PermissionError("PARENT_ACCESS_DENIED")
        con.execute(
            """UPDATE users SET active=FALSE
            WHERE learner_external_ref=? AND role='student'""",
            [learner_external_ref],
        )
    finally:
        con.close()


def delete_student_account(parent_user_id: int, learner_external_ref: str) -> None:
    """Permanently remove a student's login after its learner profile is deleted."""
    con = connect()
    try:
        parent = con.execute(
            "SELECT id FROM users WHERE id=? AND role='parent' AND active",
            [parent_user_id],
        ).fetchone()
        if parent is None:
            raise PermissionError("PARENT_ACCESS_DENIED")
        if not _parent_owns_learner(parent_user_id, learner_external_ref):
            raise PermissionError("PARENT_ACCESS_DENIED")
        con.execute(
            """DELETE FROM users
            WHERE learner_external_ref=? AND role='student' AND active=FALSE""",
            [learner_external_ref],
        )
    finally:
        con.close()


def reactivate_student_account(parent_user_id: int, learner_external_ref: str) -> None:
    con = connect()
    try:
        parent = con.execute(
            "SELECT id FROM users WHERE id=? AND role='parent' AND active",
            [parent_user_id],
        ).fetchone()
        if parent is None:
            raise PermissionError("PARENT_ACCESS_DENIED")
        if not _parent_owns_learner(parent_user_id, learner_external_ref):
            raise PermissionError("PARENT_ACCESS_DENIED")
        con.execute(
            """UPDATE users SET active=TRUE
            WHERE learner_external_ref=? AND role='student'""",
            [learner_external_ref],
        )
    finally:
        con.close()


def _record_auth_event(
    event_type: str,
    *,
    user_id: int | None = None,
    learner_external_ref: str | None = None,
    detail: str | None = None,
) -> None:
    con = connect()
    try:
        con.execute(
            """INSERT INTO authentication_audit_events(event_type,user_id,learner_external_ref,detail,created_at)
            VALUES (?,?,?,?,?)""",
            [event_type, user_id, learner_external_ref, detail, datetime.now(UTC)],
        )
    finally:
        con.close()


def _store_reset_token(
    *,
    user_id: int,
    purpose: str,
    learner_external_ref: str | None = None,
) -> str:
    token = generate_reset_token()
    expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=DEFAULT_EXPIRY_MINUTES)
    con = connect()
    try:
        con.execute(
            """INSERT INTO password_reset_tokens
            (user_id,token_hash,purpose,learner_external_ref,expires_at,created_at)
            VALUES (?,?,?,?,?,?)""",
            [user_id, hash_reset_token(token), purpose, learner_external_ref, expires_at, datetime.now(UTC)],
        )
    finally:
        con.close()
    _record_auth_event("PASSWORD_RESET_REQUESTED", user_id=user_id, learner_external_ref=learner_external_ref)
    return token


def _resolve_reset_token(token: str) -> dict[str, Any] | None:
    con = connect()
    try:
        row = con.execute(
            """SELECT id,user_id,purpose,learner_external_ref,expires_at,used_at
            FROM password_reset_tokens WHERE token_hash=?""",
            [hash_reset_token(token)],
        ).fetchone()
        if row is None:
            return None
        expires_at = row[4]
        if row[5] is not None:
            return None
        if _as_utc_aware(expires_at) < _utc_now():
            return None
        return {
            "token_id": int(row[0]),
            "user_id": int(row[1]),
            "purpose": str(row[2]),
            "learner_external_ref": row[3],
        }
    finally:
        con.close()


def request_parent_password_reset(email: str) -> str:
    email = email.strip().lower()
    con = connect()
    try:
        row = con.execute(
            "SELECT id,email FROM users WHERE lower(email)=lower(?) AND role='parent' AND active",
            [email],
        ).fetchone()
    finally:
        con.close()
    if row is not None:
        token = _store_reset_token(user_id=int(row[0]), purpose=RESET_PURPOSE_PARENT)
        reset_link = f"{get_password_reset_base_url()}/?reset_token={token}&purpose=parent"
        subject, body = parent_password_reset_email(reset_link=reset_link, expires_minutes=DEFAULT_EXPIRY_MINUTES)
        deliver_auth_email(recipient=str(row[1]), subject=subject, body=body)
    return neutral_recovery_message()


def request_child_password_recovery(parent_email: str, child_username: str) -> str:
    parent_email = parent_email.strip().lower()
    child_username = child_username.strip()
    con = connect()
    try:
        parent = con.execute(
            "SELECT id,email FROM users WHERE lower(email)=lower(?) AND role='parent' AND active",
            [parent_email],
        ).fetchone()
        if parent is None:
            return neutral_recovery_message()
        student = con.execute(
            """SELECT id,first_name,learner_external_ref FROM users
            WHERE lower(name)=lower(?) AND role='student' AND active""",
            [child_username],
        ).fetchone()
        if student is None or student[2] is None:
            return neutral_recovery_message()
        if not _parent_owns_learner(int(parent[0]), str(student[2])):
            return neutral_recovery_message()
    finally:
        con.close()
    token = _store_reset_token(
        user_id=int(parent[0]),
        purpose=RESET_PURPOSE_CHILD,
        learner_external_ref=str(student[2]),
    )
    reset_link = f"{get_password_reset_base_url()}/?reset_token={token}&purpose=child"
    subject, body = child_password_recovery_requested_email(
        child_display=str(student[1]),
        reset_link=reset_link,
        expires_minutes=DEFAULT_EXPIRY_MINUTES,
    )
    deliver_auth_email(recipient=str(parent[1]), subject=subject, body=body)
    return neutral_recovery_message()


def complete_password_reset(token: str, password: str, password_confirmation: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins huit caractères."
    if password != password_confirmation:
        return False, "La confirmation du mot de passe ne correspond pas."
    resolved = _resolve_reset_token(token)
    if resolved is None:
        return False, "Ce lien de réinitialisation est invalide ou expiré."
    con = connect()
    try:
        if resolved["purpose"] == RESET_PURPOSE_PARENT:
            updated = con.execute(
                """UPDATE users SET pin_hash=?, auth_epoch=COALESCE(auth_epoch,0)+1
                WHERE id=? AND role='parent' AND active RETURNING email,name""",
                [pin_hash(password), resolved["user_id"]],
            ).fetchone()
            account_label = str(updated[1]) if updated else "parent"
        elif resolved["purpose"] == RESET_PURPOSE_CHILD:
            learner_external_ref = str(resolved["learner_external_ref"] or "")
            updated = con.execute(
                """UPDATE users SET pin_hash=?, auth_epoch=COALESCE(auth_epoch,0)+1
                WHERE learner_external_ref=? AND role='student' AND active RETURNING first_name""",
                [pin_hash(password), learner_external_ref],
            ).fetchone()
            account_label = str(updated[0]) if updated else "élève"
        else:
            return False, "Ce lien de réinitialisation est invalide ou expiré."
        if updated is None:
            return False, "Ce lien de réinitialisation est invalide ou expiré."
        con.execute(
            "UPDATE password_reset_tokens SET used_at=? WHERE id=? AND used_at IS NULL",
            [datetime.now(UTC), resolved["token_id"]],
        )
    finally:
        con.close()
    subject, body = password_changed_notification_email(account_label=account_label)
    if resolved["purpose"] == RESET_PURPOSE_PARENT and updated:
        deliver_auth_email(recipient=str(updated[0]), subject=subject, body=body)
    _record_auth_event("PASSWORD_RESET_COMPLETED", user_id=resolved["user_id"])
    return True, "Le mot de passe a été réinitialisé. Vous pouvez vous connecter."


def session_user_still_valid(user: dict[str, Any]) -> bool:
    session_role = user.get("role")
    if not is_known_auth_role(session_role):
        return False
    con = connect()
    try:
        row = con.execute(
            "SELECT auth_epoch, active, role FROM users WHERE id=?",
            [int(user["id"])],
        ).fetchone()
    finally:
        con.close()
    if row is None or not bool(row[1]):
        return False
    if str(row[2]) != str(session_role):
        return False
    if not is_known_auth_role(row[2]):
        return False
    return int(row[0] or 0) == int(user.get("auth_epoch") or 0)


def authenticate(name: str, pin: str, expected_role: str | None = None) -> dict[str, Any] | None:
    login = name.strip()
    password = pin.strip()
    if not login or not password:
        return None
    con = connect()
    row = con.execute(
        """SELECT id,name,pin_hash,role,learner_external_ref,email,auth_epoch
        FROM users
        WHERE (lower(name)=lower(?) OR lower(email)=lower(?)) AND active""",
        [login, login],
    ).fetchone()
    con.close()
    if not row or not verify_password(password, str(row[2])):
        return None
    if not is_known_auth_role(row[3]):
        return None
    if expected_role is not None and row[3] != expected_role:
        return None
    stored_hash = str(row[2])
    if needs_rehash(stored_hash):
        con = connect()
        try:
            con.execute("UPDATE users SET pin_hash=? WHERE id=?", [pin_hash(password), row[0]])
        finally:
            con.close()
    return {
        "id": row[0],
        "name": row[1],
        "role": row[3],
        "learner_external_ref": row[4],
        "email": row[5],
        "auth_epoch": int(row[6] or 0),
    }


def student_list() -> list[dict[str, Any]]:
    con = connect()
    rows = con.execute("SELECT id,name FROM users WHERE role='student' ORDER BY name").fetchall()
    con.close()
    return [{"id": r[0], "name": r[1]} for r in rows]


def create_exam(
    user_id: int,
    subject: str,
    title: str,
    mode: str,
    duration_minutes: int | None,
    questions: list[dict[str, Any]],
    difficulty: str = "Moyen",
) -> int:
    con = connect()
    exam_id = con.execute("SELECT nextval('seq_exam')").fetchone()[0]
    con.execute(
        """
        INSERT INTO exams(
            id,user_id,subject,title,mode,duration_minutes,status,
            started_at,question_count,difficulty,target_seconds_per_question
        ) VALUES (?,?,?,?,?,?,'started',?,?,?,?)
        """,
        [exam_id, user_id, subject, title, mode, duration_minutes, datetime.now(), len(questions), difficulty, 90],
    )
    for pos, q in enumerate(questions, start=1):
        qid = con.execute("SELECT nextval('seq_exam_question')").fetchone()[0]
        con.execute(
            """
            INSERT INTO exam_questions(
                id,exam_id,position,chapter,question,answer_type,
                expected_answer,accepted_answers,unit,explanation,difficulty,target_seconds
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                qid,
                exam_id,
                pos,
                q["chapter"],
                q["question"],
                q["answer_type"],
                str(q["expected_answer"]),
                "||".join(q.get("accepted_answers", [])),
                q.get("unit", ""),
                q["explanation"],
                q.get("difficulty", difficulty),
                int(q.get("target_seconds", 90)),
            ],
        )
    con.close()
    return int(exam_id)


def get_exam(exam_id: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    con = connect()
    exam = con.execute("SELECT * FROM exams WHERE id=?", [exam_id]).df()
    questions = con.execute(
        "SELECT * FROM exam_questions WHERE exam_id=? ORDER BY position",
        [exam_id],
    ).df()
    con.close()
    if exam.empty:
        return None, []
    return exam.iloc[0].to_dict(), questions.to_dict("records")


def save_exam_answers(exam_id: int, answers: dict[int, tuple]) -> None:
    con = connect()
    for question_id, payload in answers.items():
        answer, correct = payload[0], payload[1]
        elapsed = float(payload[2]) if len(payload) > 2 else 0.0
        error_type = None if correct else ("Inattention ou méthode" if str(answer).strip() else "Réponse absente")
        con.execute(
            """UPDATE exam_questions SET student_answer=?, is_correct=?, elapsed_seconds=?, error_type=? WHERE id=? AND exam_id=?""",
            [answer, bool(correct), elapsed, error_type, int(question_id), int(exam_id)],
        )
    con.close()


def finish_exam(exam_id: int, elapsed_seconds: float | None = None) -> tuple[float, float, int, int]:
    con = connect()
    row = con.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS good
        FROM exam_questions WHERE exam_id=?
        """,
        [exam_id],
    ).fetchone()
    total = int(row[0] or 0)
    good = int(row[1] or 0)
    percentage = (good / total * 100.0) if total else 0.0
    score = percentage / 5.0
    con.execute(
        """
        UPDATE exams SET status='completed', finished_at=?, score=?,
        percentage=?, correct_count=? WHERE id=?
        """,
        [datetime.now(), score, percentage, good, exam_id],
    )
    if elapsed_seconds is not None:
        con.execute("UPDATE exams SET elapsed_seconds=? WHERE id=?", [float(elapsed_seconds), exam_id])
    con.close()
    return score, percentage, good, total


def list_exams(user_id: int, status: str | None = None) -> pd.DataFrame:
    con = connect()
    if status:
        df = con.execute(
            "SELECT * FROM exams WHERE user_id=? AND status=? ORDER BY started_at DESC",
            [user_id, status],
        ).df()
    else:
        df = con.execute(
            "SELECT * FROM exams WHERE user_id=? ORDER BY started_at DESC",
            [user_id],
        ).df()
    con.close()
    return df


def save_practice_attempt(
    user_id: int,
    subject: str,
    chapter: str,
    question: str,
    expected: str,
    answer: str,
    correct: bool,
    difficulty: str = "Moyen",
    elapsed_seconds: float = 0.0,
    target_seconds: int = 90,
) -> None:
    con = connect()
    attempt_id = con.execute("SELECT nextval('seq_practice')").fetchone()[0]
    con.execute(
        """
        INSERT INTO practice_attempts(
            id,user_id,subject,chapter,question,expected_answer,
            student_answer,is_correct,difficulty,created_at,elapsed_seconds,target_seconds,error_type
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            attempt_id,
            user_id,
            subject,
            chapter,
            question,
            expected,
            answer,
            bool(correct),
            difficulty,
            datetime.now(),
            float(elapsed_seconds),
            int(target_seconds),
            None if correct else ("Inattention ou méthode" if str(answer).strip() else "Réponse absente"),
        ],
    )
    con.close()


def dashboard_metrics(user_id: int) -> dict[str, Any]:
    con = connect()
    exam = con.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE status='completed') AS completed_exams,
            AVG(score) FILTER (WHERE status='completed') AS avg_score,
            MAX(score) FILTER (WHERE status='completed') AS best_score
        FROM exams WHERE user_id=?
        """,
        [user_id],
    ).fetchone()
    practice = con.execute(
        """
        SELECT COUNT(*) AS total,
               AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) * 100 AS success
        FROM practice_attempts WHERE user_id=?
        """,
        [user_id],
    ).fetchone()
    con.close()
    return {
        "completed_exams": int(exam[0] or 0),
        "avg_score": float(exam[1] or 0),
        "best_score": float(exam[2] or 0),
        "practice_total": int(practice[0] or 0),
        "practice_success": float(practice[1] or 0),
    }


def subject_averages(user_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
        SELECT subject,
               ROUND(AVG(score),2) AS moyenne,
               COUNT(*) AS devoirs
        FROM exams
        WHERE user_id=? AND status='completed'
        GROUP BY subject
        ORDER BY subject
        """,
        [user_id],
    ).df()
    con.close()
    return df


def note_history(user_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
        SELECT started_at,subject,title,score,percentage
        FROM exams
        WHERE user_id=? AND status='completed'
        ORDER BY started_at
        """,
        [user_id],
    ).df()
    con.close()
    return df


def chapter_performance(user_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
        SELECT e.subject,q.chapter,
               COUNT(*) AS questions,
               ROUND(AVG(CASE WHEN q.is_correct THEN 1.0 ELSE 0.0 END)*100,1) AS reussite
        FROM exam_questions q
        JOIN exams e ON e.id=q.exam_id
        WHERE e.user_id=? AND e.status='completed'
        GROUP BY e.subject,q.chapter
        ORDER BY e.subject,q.chapter
        """,
        [user_id],
    ).df()
    con.close()
    return df


def practice_chapter_stats(user_id: int, subject: str | None = None) -> pd.DataFrame:
    con = connect()
    if subject:
        df = con.execute(
            """
            SELECT subject, chapter, COUNT(*) AS tentatives,
                   ROUND(AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END)*100,1) AS reussite
            FROM practice_attempts
            WHERE user_id=? AND subject=?
            GROUP BY subject, chapter
            ORDER BY reussite ASC, tentatives DESC
            """,
            [user_id, subject],
        ).df()
    else:
        df = con.execute(
            """
            SELECT subject, chapter, COUNT(*) AS tentatives,
                   ROUND(AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END)*100,1) AS reussite
            FROM practice_attempts
            WHERE user_id=?
            GROUP BY subject, chapter
            ORDER BY reussite ASC, tentatives DESC
            """,
            [user_id],
        ).df()
    con.close()
    return df


def weakest_chapters(user_id: int, subject: str, available: list[str], limit: int = 5) -> list[str]:
    stats = practice_chapter_stats(user_id, subject)
    if stats.empty:
        return available[:limit]
    known = [str(x) for x in stats["chapter"].tolist() if str(x) in available]
    unseen = [x for x in available if x not in known]
    return (known + unseen)[:limit]


def learning_overview(user_id: int, subject: str | None = None) -> pd.DataFrame:
    """Résultats consolidés des devoirs et entraînements, par matière et chapitre."""
    con = connect()
    params: list[Any] = [user_id, user_id]
    subject_filter_exam = ""
    subject_filter_practice = ""
    if subject:
        subject_filter_exam = " AND e.subject=?"
        subject_filter_practice = " AND p.subject=?"
        params = [user_id, subject, user_id, subject]
    df = con.execute(
        f"""
        WITH results AS (
            SELECT e.subject, q.chapter, 'Devoir' AS source,
                   CASE WHEN q.is_correct THEN 1.0 ELSE 0.0 END AS success,
                   e.finished_at AS activity_date
            FROM exam_questions q
            JOIN exams e ON e.id=q.exam_id
            WHERE e.user_id=? AND e.status='completed'{subject_filter_exam}
            UNION ALL
            SELECT p.subject, p.chapter, 'Entraînement' AS source,
                   CASE WHEN p.is_correct THEN 1.0 ELSE 0.0 END AS success,
                   p.created_at AS activity_date
            FROM practice_attempts p
            WHERE p.user_id=?{subject_filter_practice}
        )
        SELECT subject, chapter,
               COUNT(*) AS questions,
               SUM(CASE WHEN source='Devoir' THEN 1 ELSE 0 END) AS questions_devoirs,
               SUM(CASE WHEN source='Entraînement' THEN 1 ELSE 0 END) AS questions_entrainements,
               ROUND(AVG(success)*100,1) AS reussite,
               MAX(activity_date) AS derniere_activite
        FROM results
        GROUP BY subject, chapter
        ORDER BY subject, reussite ASC, questions DESC
        """,
        params,
    ).df()
    con.close()
    return df


def activity_progression(user_id: int) -> pd.DataFrame:
    """Historique commun des devoirs et des séances d'entraînement."""
    con = connect()
    df = con.execute(
        """
        WITH practice_sessions AS (
            SELECT CAST(created_at AS DATE) AS activity_date, subject,
                   'Entraînement' AS activity_type,
                   ROUND(AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END)*100,1) AS percentage,
                   COUNT(*) AS questions
            FROM practice_attempts
            WHERE user_id=?
            GROUP BY CAST(created_at AS DATE), subject
        ), exam_sessions AS (
            SELECT CAST(finished_at AS DATE) AS activity_date, subject,
                   'Devoir' AS activity_type,
                   ROUND(percentage,1) AS percentage,
                   question_count AS questions
            FROM exams
            WHERE user_id=? AND status='completed'
        )
        SELECT * FROM practice_sessions
        UNION ALL
        SELECT * FROM exam_sessions
        ORDER BY activity_date
        """,
        [user_id, user_id],
    ).df()
    con.close()
    return df


def exam_chapter_analysis(exam_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
        SELECT chapter, COUNT(*) AS questions,
               SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correctes,
               ROUND(AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END)*100,1) AS reussite
        FROM exam_questions
        WHERE exam_id=?
        GROUP BY chapter
        ORDER BY reussite ASC, chapter
        """,
        [exam_id],
    ).df()
    con.close()
    return df


def practice_difficulty_stats(user_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
        SELECT subject, difficulty, COUNT(*) AS questions,
               ROUND(AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END)*100,1) AS reussite
        FROM practice_attempts
        WHERE user_id=?
        GROUP BY subject, difficulty
        ORDER BY subject, difficulty
        """,
        [user_id],
    ).df()
    con.close()
    return df


def advanced_learning_overview(user_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
    WITH all_results AS (
      SELECT
          e.subject AS subject,
          q.chapter AS chapter,
          q.difficulty AS difficulty,
          CASE WHEN q.is_correct THEN 1.0 ELSE 0.0 END AS ok,
          q.elapsed_seconds AS elapsed_value,
          q.target_seconds AS target_value
      FROM exam_questions q
      JOIN exams e ON e.id = q.exam_id
      WHERE e.user_id = ? AND e.status = 'completed'

      UNION ALL

      SELECT
          subject,
          chapter,
          difficulty,
          CASE WHEN is_correct THEN 1.0 ELSE 0.0 END AS ok,
          elapsed_seconds AS elapsed_value,
          target_seconds AS target_value
      FROM practice_attempts
      WHERE user_id = ?
    )
    SELECT
        subject,
        chapter,
        difficulty,
        COUNT(*) AS attempts,
        ROUND(AVG(ok) * 100, 1) AS accuracy,
        ROUND(AVG(NULLIF(elapsed_value, 0)), 1) AS avg_seconds,
        ROUND(AVG(target_value), 1) AS target_seconds,
        ROUND(AVG(CASE WHEN elapsed_value > 0 THEN target_value / elapsed_value ELSE 1 END), 2) AS speed_index
    FROM all_results
    GROUP BY subject, chapter, difficulty
    ORDER BY subject, chapter, difficulty
    """,
        [user_id, user_id],
    ).df()
    con.close()
    return df


def time_progression(user_id: int) -> pd.DataFrame:
    con = connect()
    df = con.execute(
        """
      SELECT CAST(finished_at AS DATE) activity_date,subject,'Devoir' activity_type,
             elapsed_seconds,question_count,ROUND(elapsed_seconds/NULLIF(question_count,0),1) seconds_per_question,percentage
      FROM exams WHERE user_id=? AND status='completed'
      UNION ALL
      SELECT CAST(created_at AS DATE),subject,'Entraînement',SUM(elapsed_seconds),COUNT(*),
             ROUND(AVG(NULLIF(elapsed_seconds,0)),1),ROUND(AVG(CASE WHEN is_correct THEN 100.0 ELSE 0 END),1)
      FROM practice_attempts WHERE user_id=? GROUP BY CAST(created_at AS DATE),subject
      ORDER BY activity_date
    """,
        [user_id, user_id],
    ).df()
    con.close()
    return df
