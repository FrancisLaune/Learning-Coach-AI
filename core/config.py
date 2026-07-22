"""Small, dependency-free runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "objectif_brevet_2027.duckdb"
VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def get_database_path() -> Path:
    """Return the configured DuckDB path, resolved relative to the project root."""
    configured = os.getenv("LCAI_DATABASE_PATH")
    if not configured:
        return DEFAULT_DATABASE_PATH
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_log_level() -> str:
    """Return a safe standard-library logging level name."""
    level = os.getenv("LCAI_LOG_LEVEL", "INFO").strip().upper()
    return level if level in VALID_LOG_LEVELS else "INFO"
