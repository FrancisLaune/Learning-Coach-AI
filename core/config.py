"""Small, dependency-free runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "objectif_brevet_2027.duckdb"
DEFAULT_V2_DATABASE_PATH = PROJECT_ROOT / "data" / "learning_coach_v2.duckdb"
VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def get_database_path() -> Path:
    """Return the configured DuckDB path, resolved relative to the project root."""
    configured = os.getenv("LCAI_DATABASE_PATH")
    if not configured:
        return DEFAULT_DATABASE_PATH
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_v2_database_path() -> Path:
    """Return the V2 DuckDB path without affecting the legacy database path."""
    configured = os.getenv("LCAI_V2_DATABASE_PATH")
    if not configured:
        return DEFAULT_V2_DATABASE_PATH
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def is_v2_ui_enabled() -> bool:
    """Require explicit opt-in before exposing the isolated V2 onboarding UI."""
    return os.getenv("LCAI_ENABLE_V2_UI", "false").strip().lower() in {"1", "true", "yes"}


def get_log_level() -> str:
    """Return a safe standard-library logging level name."""
    level = os.getenv("LCAI_LOG_LEVEL", "INFO").strip().upper()
    return level if level in VALID_LOG_LEVELS else "INFO"
