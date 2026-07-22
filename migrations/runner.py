"""Transactional and checksum-verified DuckDB V2 migration runner."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb

from core.config import PROJECT_ROOT, get_v2_database_path

DEFAULT_MIGRATIONS_PATH = PROJECT_ROOT / "migrations" / "v2"
MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_(?P<name>[a-z0-9_]+)\.sql$")


class MigrationError(RuntimeError):
    """Raised when migration discovery or validation fails."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One immutable SQL migration loaded from disk."""

    version: int
    name: str
    path: Path
    sql: str
    checksum: str


def discover_migrations(directory: Path = DEFAULT_MIGRATIONS_PATH) -> list[Migration]:
    """Load migrations in version order and reject gaps or duplicates."""
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_NAME.fullmatch(path.name)
        if not match:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=int(match.group("version")),
                name=match.group("name"),
                path=path,
                sql=sql,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            )
        )
    if not migrations:
        raise MigrationError(f"No migrations found in {directory}")
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationError("Duplicate migration version")
    expected = list(range(1, len(versions) + 1))
    if versions != expected:
        raise MigrationError(f"Migration versions must be contiguous: expected {expected}, got {versions}")
    return migrations


def _applied_versions(connection: duckdb.DuckDBPyConnection) -> dict[int, str]:
    exists = connection.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main' AND table_name='schema_versions'"
    ).fetchone()
    if not exists or not exists[0]:
        return {}
    rows = connection.execute("SELECT version, checksum FROM schema_versions ORDER BY version").fetchall()
    return {int(version): str(checksum) for version, checksum in rows}


def apply_migrations(
    database_path: Path | None = None,
    migrations_path: Path = DEFAULT_MIGRATIONS_PATH,
) -> list[Migration]:
    """Apply pending migrations atomically and return those newly applied."""
    target = database_path or get_v2_database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    migrations = discover_migrations(migrations_path)
    connection = duckdb.connect(str(target))
    applied_now: list[Migration] = []
    try:
        applied = _applied_versions(connection)
        for migration in migrations:
            previous_checksum = applied.get(migration.version)
            if previous_checksum:
                if previous_checksum != migration.checksum:
                    raise MigrationError(f"Checksum mismatch for migration {migration.version:03d}_{migration.name}")
                continue
            started = time.perf_counter()
            connection.execute("BEGIN TRANSACTION")
            try:
                connection.execute(migration.sql)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                connection.execute(
                    "INSERT INTO schema_versions(version,name,checksum,execution_ms) VALUES (?,?,?,?)",
                    [migration.version, migration.name, migration.checksum, elapsed_ms],
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            applied_now.append(migration)
    finally:
        connection.close()
    return applied_now
