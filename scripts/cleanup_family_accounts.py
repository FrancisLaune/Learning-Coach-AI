"""One-shot cleanup: keep only Parent in V1, remove orphan V2 learners."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_database_path, get_v2_database_path
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository

KEEP_PARENT_V1_ID = 1
REMOVE_V1_USER_IDS = (2, 4, 8, 10)
PARENT_REF = "1"


def cleanup_v1() -> None:
    db_path = get_database_path()
    connection = duckdb.connect(str(db_path))
    try:
        for user_id in REMOVE_V1_USER_IDS:
            connection.execute("DELETE FROM password_reset_tokens WHERE user_id=?", [user_id])
            connection.execute("DELETE FROM authentication_audit_events WHERE user_id=?", [user_id])
            connection.execute("DELETE FROM users WHERE id=?", [user_id])
        remaining = connection.execute(
            "SELECT id, name, role FROM users ORDER BY id"
        ).fetchall()
        print("V1 users after cleanup:", remaining)
    finally:
        connection.close()


def cleanup_v2() -> None:
    repository = DuckDBUnifiedExperienceRepository(get_v2_database_path())
    connection = duckdb.connect(str(get_v2_database_path()))
    try:
        learner_ids = [int(row[0]) for row in connection.execute("SELECT id FROM learners").fetchall()]
    finally:
        connection.close()
    for learner_id in learner_ids:
        if not repository.parent_authorized(PARENT_REF, learner_id):
            repository.link_parent(PARENT_REF, learner_id)
        repository.delete_learner(PARENT_REF, learner_id)
    connection = duckdb.connect(str(get_v2_database_path()), read_only=True)
    try:
        learners = connection.execute("SELECT count(*) FROM learners").fetchone()[0]
        links = connection.execute("SELECT count(*) FROM learner_guardian_links").fetchone()[0]
        print(f"V2 after cleanup: learners={learners}, guardian_links={links}")
    finally:
        connection.close()


if __name__ == "__main__":
    print("Cleaning V1…")
    cleanup_v1()
    print("Cleaning V2…")
    cleanup_v2()
    print("Done.")
