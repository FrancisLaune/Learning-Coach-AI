"""Apply LCAI-0032 migrations on objectif_brevet DuckDB."""

from __future__ import annotations

import contextlib
import hashlib
import re
from pathlib import Path

import duckdb

from core.config import PROJECT_ROOT, get_database_path

MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "brevet_content"
MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_(?P<name>[a-z0-9_]+)\.sql$")


def apply_brevet_content_migrations(db_path: Path | None = None) -> list[str]:
    path = Path(db_path or get_database_path())
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS bref_schema_migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                checksum VARCHAR NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            int(row[0]): str(row[1])
            for row in con.execute("SELECT version, checksum FROM bref_schema_migrations").fetchall()
        }
        done: list[str] = []
        for sql_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            match = MIGRATION_NAME.fullmatch(sql_path.name)
            if not match:
                continue
            version = int(match.group("version"))
            name = match.group("name")
            sql = sql_path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"Checksum mismatch for migration {version}_{name}")
                continue
            statements: list[str] = []
            for raw in sql.split(";"):
                lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
                statement = "\n".join(lines).strip()
                if statement:
                    statements.append(statement)
            for statement in statements:
                con.execute(statement)
            con.execute(
                "INSERT INTO bref_schema_migrations(version, name, checksum) VALUES (?, ?, ?)",
                [version, name, checksum],
            )
            done.append(sql_path.name)
            with contextlib.suppress(Exception):
                con.execute("CHECKPOINT")
        return done
    finally:
        con.close()
