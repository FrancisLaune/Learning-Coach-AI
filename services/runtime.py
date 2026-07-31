"""Technical startup operations preserved from the legacy entry point."""

from __future__ import annotations

from threading import Lock

from core.database import init_db
from infrastructure.logging import configure_logging
from migrations.runner import apply_migrations

_runtime_lock = Lock()
_runtime_initialized = False


def prepare_runtime() -> None:
    """Initialize databases once per application process, including Streamlit reruns."""
    global _runtime_initialized
    if _runtime_initialized:
        return
    with _runtime_lock:
        if _runtime_initialized:
            return
        configure_logging()
        init_db()
        try:
            apply_migrations()
        except Exception as exc:
            message = str(exc)
            if "already open" in message.casefold() or "utilisé par un autre processus" in message.casefold():
                raise RuntimeError(
                    "La base DuckDB est verrouillée (souvent par git.exe / git-lfs). "
                    "Ferme les processus Git qui touchent data/learning_coach_v2.duckdb, "
                    "puis redémarre Streamlit."
                ) from exc
            raise
        _runtime_initialized = True


def _reset_runtime_for_tests() -> None:
    global _runtime_initialized
    with _runtime_lock:
        _runtime_initialized = False
