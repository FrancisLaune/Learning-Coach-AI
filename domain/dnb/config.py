"""LCAI-0031 — Canonical DNB 2027 product configuration (no Streamlit hard-coding)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PRIMARY_USER_GRADE_CODE: Final[str] = "FR-3E"
CURRICULUM_VERSION: Final[str] = "FR_3E_2027_V1"
DNB_SESSION_CODE: Final[str] = "DNB-2027"
DNB_ORAL: Final[str] = "ORAL"

# Subject codes aligned with V2 `subjects.code` (migrations/v2/002_seed_reference.sql).
DNB_TERMINAL_SUBJECTS: Final[frozenset[str]] = frozenset(
    {
        "FRENCH",
        "MATHEMATICS",
        "HISTORY",
        "GEOGRAPHY",
        "EMC",
        "PHYSICS_CHEMISTRY",
        "SVT",
        "TECHNOLOGY",
    }
)

# Languages: continuous assessment / history only — not default terminal Brevet paths.
CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS: Final[frozenset[str]] = frozenset(
    {
        "ENGLISH",
        "SPANISH",
    }
)

# Grades that may appear only as internal prerequisite remediation (not primary UX).
REMEDIATION_GRADE_CODES: Final[frozenset[str]] = frozenset(
    {
        "FR-CM1",
        "FR-CM2",
        "FR-6E",
        "FR-5E",
        "FR-4E",
    }
)

HISTORY_GEOGRAPHY_DOMAIN: Final[str] = "HISTORY_GEOGRAPHY"
SCIENCE_POOL_SUBJECTS: Final[frozenset[str]] = frozenset(
    {
        "PHYSICS_CHEMISTRY",
        "SVT",
        "TECHNOLOGY",
    }
)


@dataclass(frozen=True, slots=True)
class DnbProductConfig:
    """Versioned product identity for Objectif Brevet 2027."""

    session_code: str = DNB_SESSION_CODE
    curriculum_version: str = CURRICULUM_VERSION
    primary_grade_code: str = PRIMARY_USER_GRADE_CODE
    product_label: str = "Objectif Brevet 2027"
    series: str = "GENERALE"
    terminal_subjects: frozenset[str] = DNB_TERMINAL_SUBJECTS
    continuous_only_subjects: frozenset[str] = CONTINUOUS_ASSESSMENT_ONLY_SUBJECTS
    remediation_grade_codes: frozenset[str] = REMEDIATION_GRADE_CODES
    oral_code: str = DNB_ORAL
    science_pool: frozenset[str] = SCIENCE_POOL_SUBJECTS
    history_geography_domain: str = HISTORY_GEOGRAPHY_DOMAIN

    def is_user_facing_grade(self, grade_code: str) -> bool:
        return str(grade_code).upper() == self.primary_grade_code

    def is_terminal_subject(self, subject_code: str) -> bool:
        return str(subject_code).upper() in self.terminal_subjects

    def is_continuous_assessment_only(self, subject_code: str) -> bool:
        return str(subject_code).upper() in self.continuous_only_subjects

    def belongs_in_brevet_prep_path(self, subject_code: str) -> bool:
        code = str(subject_code).upper()
        return code == self.oral_code or code in self.terminal_subjects


def load_dnb_product_config() -> DnbProductConfig:
    """Return the active DNB product config (extensible later via env/file)."""
    return DnbProductConfig()
