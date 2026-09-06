"""Readiness path definitions for LCAI-0019 / LCAI-0031."""

from __future__ import annotations

from domain.pedagogical_intelligence.models import ReadinessPathCode, ReadinessPathDefinition

READINESS_PATHS: tuple[ReadinessPathDefinition, ...] = (
    ReadinessPathDefinition(
        code="CM1_TO_CM2",
        label="Préparation CM2",
        source_grade_code="FR-CM1",
        target_grade_code="FR-CM2",
        objective_ref="transition_cm2",
    ),
    ReadinessPathDefinition(
        code="FR_4E_TO_3E",
        label="Préparation 3e",
        source_grade_code="FR-4E",
        target_grade_code="FR-3E",
        objective_ref="transition_3e",
    ),
    ReadinessPathDefinition(
        code="FR_3E_DNB_BASELINE",
        label="Diagnostic initial Brevet 3e",
        source_grade_code="FR-3E",
        target_grade_code="FR-3E",
        objective_ref="dnb_2027_baseline",
    ),
)

_PATH_BY_SOURCE: dict[str, ReadinessPathDefinition] = {path.source_grade_code: path for path in READINESS_PATHS}
_PATH_BY_CODE: dict[ReadinessPathCode, ReadinessPathDefinition] = {path.code: path for path in READINESS_PATHS}


def path_for_source_grade(grade_code: str) -> ReadinessPathDefinition | None:
    return _PATH_BY_SOURCE.get(grade_code)


def path_by_code(code: ReadinessPathCode) -> ReadinessPathDefinition:
    return _PATH_BY_CODE[code]


def brevet_baseline_path_code() -> ReadinessPathCode:
    return "FR_3E_DNB_BASELINE"
