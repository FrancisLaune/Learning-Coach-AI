"""LCAI-0032 — Brevet content referential (objectif_brevet_2027.duckdb)."""

from __future__ import annotations

from services.brevet_referential.bootstrap import bootstrap_referential
from services.brevet_referential.coverage import (
    coverage_status_for_skill,
    ensure_content_coverage,
    measure_coverage,
)
from services.brevet_referential.search import search_exercises

__all__ = [
    "bootstrap_referential",
    "coverage_status_for_skill",
    "ensure_content_coverage",
    "measure_coverage",
    "search_exercises",
]
