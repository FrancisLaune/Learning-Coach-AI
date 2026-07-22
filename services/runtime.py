"""Technical startup operations preserved from the legacy entry point."""

from __future__ import annotations

from core.database import init_db
from infrastructure.logging import configure_logging


def prepare_runtime() -> None:
    """Configure logging and initialize the unchanged DuckDB V1 schema."""
    configure_logging()
    init_db()
