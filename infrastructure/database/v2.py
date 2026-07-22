"""DuckDB V2 connection factory, separate from the legacy V1 database."""

from __future__ import annotations

from pathlib import Path

import duckdb

from core.config import get_v2_database_path


def connect_v2(database_path: Path | None = None, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the V2 database selected explicitly or through central configuration."""
    target = database_path or get_v2_database_path()
    if not read_only:
        target.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(target), read_only=read_only)
