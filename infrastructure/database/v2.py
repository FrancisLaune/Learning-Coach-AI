"""DuckDB V2 connection factory, separate from the legacy V1 database."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from core.config import get_v2_database_path

_connections: dict[str, duckdb.DuckDBPyConnection] = {}


class _V2Connection:
    """Reuse one DuckDB handle per database file within a process (Windows-safe)."""

    __slots__ = ("_inner",)

    def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
        self._inner = inner

    def close(self) -> None:
        return  # Shared handle; call reset_v2_connections() for teardown.

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __enter__(self) -> _V2Connection:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def reset_v2_connections() -> None:
    """Close all cached V2 connections (tests and maintenance scripts)."""
    for connection in _connections.values():
        connection.close()
    _connections.clear()


def connect_v2(database_path: Path | None = None, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the V2 database selected explicitly or through central configuration."""
    from core.duckdb_wal import is_wal_replay_failure, quarantine_empty_wal, quarantine_wal

    del read_only  # DuckDB rejects mixed RO/RW handles on Windows; use one mode everywhere.
    target = (database_path or get_v2_database_path()).resolve()
    key = str(target)
    connection = _connections.get(key)
    if connection is None:
        target.parent.mkdir(parents=True, exist_ok=True)
        quarantine_empty_wal(target)
        try:
            connection = duckdb.connect(key)
        except Exception as exc:
            if not is_wal_replay_failure(exc):
                raise
            quarantine_wal(target)
            connection = duckdb.connect(key)
        _connections[key] = connection
    return _V2Connection(connection)  # type: ignore[return-value]
