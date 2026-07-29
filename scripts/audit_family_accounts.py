"""Audit and cleanup V1/V2 family accounts (one-shot maintenance)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_database_path
from infrastructure.database.v2 import connect_v2

V1 = get_database_path()
V2 = Path("data/learning_coach_v2.duckdb")


def audit() -> None:
    print("=== V1", V1, "===")
    try:
        v1 = duckdb.connect(str(V1), read_only=True)
    except Exception as exc:
        print("V1 read_only failed:", exc)
        v1 = duckdb.connect(str(V1))
    rows = v1.execute(
        """SELECT id, name, role, active, email, learner_external_ref, auth_epoch
        FROM users ORDER BY id"""
    ).fetchall()
    for row in rows:
        print(row)
    v1.close()

    print("\n=== V2 learners + guardian links ===")
    v2 = connect_v2(V2, read_only=True)
    learners = v2.execute(
        """SELECT l.id, l.external_ref, l.display_name, l.archived_at,
        g.guardian_external_ref, g.active
        FROM learners l
        LEFT JOIN learner_guardian_links g ON g.learner_id = l.id
        ORDER BY l.id"""
    ).fetchall()
    for row in learners:
        print(row)
    v2.close()


if __name__ == "__main__":
    audit()
