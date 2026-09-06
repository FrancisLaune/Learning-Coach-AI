"""Per-subject capabilities for DNB terminal vs continuous assessment."""

from __future__ import annotations

from dataclasses import dataclass

from domain.dnb.config import (
    CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS,
    DNB_ORAL,
    DNB_TERMINAL_SUBJECTS,
    SCIENCE_POOL_SUBJECTS,
)


@dataclass(frozen=True, slots=True)
class SubjectCapabilities:
    subject_code: str
    terminal_exam: bool
    continuous_assessment: bool
    supports_brevet_exam: bool
    supports_revision: bool
    supports_ai_generation: bool
    supports_long_answer: bool
    supports_oral: bool
    in_science_pool: bool = False
    history_geography_weight: float | None = None
    emc_weight: float | None = None


_LONG_ANSWER: frozenset[str] = frozenset(
    {
        "FRENCH",
        "HISTORY",
        "GEOGRAPHY",
        "EMC",
        "MATHEMATICS",
        "PHYSICS_CHEMISTRY",
        "SVT",
        "TECHNOLOGY",
    }
)


def capabilities_for(subject_code: str) -> SubjectCapabilities:
    code = str(subject_code).upper()
    if code == DNB_ORAL:
        return SubjectCapabilities(
            subject_code=code,
            terminal_exam=True,
            continuous_assessment=False,
            supports_brevet_exam=True,
            supports_revision=True,
            supports_ai_generation=True,
            supports_long_answer=True,
            supports_oral=True,
        )
    if code in CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS:
        return SubjectCapabilities(
            subject_code=code,
            terminal_exam=False,
            continuous_assessment=True,
            supports_brevet_exam=False,
            supports_revision=False,
            supports_ai_generation=False,
            supports_long_answer=False,
            supports_oral=False,
        )
    if code not in DNB_TERMINAL_SUBJECTS:
        return SubjectCapabilities(
            subject_code=code,
            terminal_exam=False,
            continuous_assessment=True,
            supports_brevet_exam=False,
            supports_revision=False,
            supports_ai_generation=False,
            supports_long_answer=False,
            supports_oral=False,
        )
    return SubjectCapabilities(
        subject_code=code,
        terminal_exam=True,
        continuous_assessment=True,
        supports_brevet_exam=True,
        supports_revision=True,
        supports_ai_generation=True,
        supports_long_answer=code in _LONG_ANSWER,
        supports_oral=False,
        in_science_pool=code in SCIENCE_POOL_SUBJECTS,
        history_geography_weight=1.5 if code in {"HISTORY", "GEOGRAPHY"} else None,
        emc_weight=0.5 if code == "EMC" else None,
    )


def terminal_brevet_subject_codes() -> frozenset[str]:
    return frozenset(code for code in (*DNB_TERMINAL_SUBJECTS, DNB_ORAL) if capabilities_for(code).supports_brevet_exam)
