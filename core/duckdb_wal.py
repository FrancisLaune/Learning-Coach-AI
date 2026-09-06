"""Recover from corrupt or empty DuckDB WAL files on Windows."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def is_wal_replay_failure(exc: BaseException) -> bool:
    message = str(exc).casefold()
    return "replaying wal" in message or (".wal" in message and "failure" in message)


def quarantine_wal(database_path: Path | str) -> Path | None:
    """Move a sidecar ``.wal`` aside so DuckDB can open the main file again."""
    wal = Path(f"{database_path}.wal")
    if not wal.exists():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup = wal.with_name(f"{wal.name}.corrupt_backup_{stamp}")
    wal.replace(backup)
    return backup


def quarantine_empty_wal(database_path: Path | str) -> Path | None:
    """Remove a zero-byte WAL that can crash DuckDB 1.5.x on Windows."""
    wal = Path(f"{database_path}.wal")
    if not wal.exists():
        return None
    try:
        if wal.stat().st_size > 0:
            return None
    except OSError:
        return None
    return quarantine_wal(database_path)
