"""LCAI-0040 curriculum closure package."""

from __future__ import annotations

from services.brevet_referential.curriculum_closure.factory import CurriculumClosureFactory
from services.brevet_referential.curriculum_closure.scoring import score_coverage_v40

__all__ = ["CurriculumClosureFactory", "score_coverage_v40"]
