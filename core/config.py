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


def is_legacy_ui_enabled() -> bool:
    """Keep the former product reachable only through an explicit migration fallback."""
    return os.getenv("LCAI_ENABLE_LEGACY_UI", "false").strip().lower() in {"1", "true", "yes"}


def is_demo_credentials_enabled() -> bool:
    return os.getenv("LCAI_ENABLE_DEMO_CREDENTIALS", "true").strip().lower() in {"1", "true", "yes"}


def get_demo_parent_credentials() -> tuple[str, str]:
    return (
        os.getenv("LCAI_DEMO_PARENT_USERNAME", "Parent"),
        os.getenv("LCAI_DEMO_PARENT_PASSWORD", "1234"),
    )


def is_v2_session_execution_enabled() -> bool:
    """Require both V2 UI and an explicit session-execution opt-in."""
    return is_v2_ui_enabled() and os.getenv("LCAI_V2_SESSION_EXECUTION_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def is_v2_parent_dashboard_enabled() -> bool:
    """Gate parent analytics independently while retaining the V2 master flag."""
    return is_v2_ui_enabled() and os.getenv("LCAI_V2_PARENT_DASHBOARD_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def get_session_autosave_interval_seconds() -> int:
    return _bounded_int("LCAI_SESSION_AUTOSAVE_INTERVAL_SECONDS", 15, 5, 300)


def get_session_heartbeat_interval_seconds() -> int:
    return _bounded_int("LCAI_SESSION_HEARTBEAT_INTERVAL_SECONDS", 15, 5, 300)


def get_session_inactivity_pause_seconds() -> int:
    return _bounded_int("LCAI_SESSION_INACTIVITY_PAUSE_SECONDS", 900, 60, 86400)


def is_session_recovery_enabled() -> bool:
    return os.getenv("LCAI_SESSION_RECOVERY_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def is_learning_analytics_enabled() -> bool:
    return is_v2_ui_enabled() and os.getenv("LCAI_ANALYTICS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def is_v2_admin_enabled() -> bool:
    """Require a second explicit flag before exposing catalog administration."""
    return is_v2_ui_enabled() and os.getenv("LCAI_ENABLE_V2_ADMIN", "false").strip().lower() in {"1", "true", "yes"}


def get_log_level() -> str:
    """Return a safe standard-library logging level name."""
    level = os.getenv("LCAI_LOG_LEVEL", "INFO").strip().upper()
    return level if level in VALID_LOG_LEVELS else "INFO"


def get_auth_email_mode() -> str:
    mode = os.getenv("LCAI_AUTH_EMAIL_MODE", "console").strip().lower()
    if mode in {"console", "file", "smtp", "disabled"}:
        return mode
    return "console"


def get_auth_email_output_dir() -> Path:
    configured = os.getenv("LCAI_AUTH_EMAIL_OUTPUT_DIR")
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / "exports" / "auth_emails"


def get_auth_email_from_address() -> str:
    return os.getenv("LCAI_AUTH_EMAIL_FROM", "noreply@learning-coach.local").strip()


def get_password_reset_base_url() -> str:
    return os.getenv("LCAI_PASSWORD_RESET_BASE_URL", "http://localhost:8501").rstrip("/")


def get_smtp_settings() -> tuple[str, int, str | None, str | None, bool]:
    host = os.getenv("LCAI_SMTP_HOST", "").strip()
    port = _bounded_int("LCAI_SMTP_PORT", 587, 1, 65535)
    username = os.getenv("LCAI_SMTP_USERNAME")
    password = os.getenv("LCAI_SMTP_PASSWORD")
    use_tls = os.getenv("LCAI_SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}
    return host, port, username, password, use_tls
