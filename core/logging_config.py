"""Application logging configuration with no sensitive context."""

from __future__ import annotations

import logging

from core.config import get_log_level

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger once using an explicit or environment level."""
    selected_level = (level or get_log_level()).upper()
    if selected_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        selected_level = "INFO"
    logging.basicConfig(level=selected_level, format=LOG_FORMAT)
