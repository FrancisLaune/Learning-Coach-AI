"""Compatibility facade for runtime configuration."""

from core.config import (
    DEFAULT_DATABASE_PATH,
    DEFAULT_V2_DATABASE_PATH,
    PROJECT_ROOT,
    get_database_path,
    get_log_level,
    get_v2_database_path,
)

__all__ = [
    "DEFAULT_DATABASE_PATH",
    "DEFAULT_V2_DATABASE_PATH",
    "PROJECT_ROOT",
    "get_database_path",
    "get_log_level",
    "get_v2_database_path",
]
