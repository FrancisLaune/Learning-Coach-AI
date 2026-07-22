"""Compatibility facade for runtime configuration."""

from core.config import DEFAULT_DATABASE_PATH, PROJECT_ROOT, get_database_path, get_log_level

__all__ = ["DEFAULT_DATABASE_PATH", "PROJECT_ROOT", "get_database_path", "get_log_level"]
