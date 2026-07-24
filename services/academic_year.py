"""Deterministic school-year presentation helpers."""

from __future__ import annotations

import re
from datetime import date

from domain.learning.models import AcademicYear

SCHOOL_YEAR_PATTERN = re.compile(r"^(?P<start>\d{4})-(?P<end>\d{4})$")


def current_school_year_start(today: date) -> int:
    """July starts preparation for the school year beginning that calendar year."""
    return today.year if today.month >= 7 else today.year - 1


def academic_year_options(today: date) -> tuple[str, ...]:
    start = current_school_year_start(today)
    return tuple(f"{year}-{year + 1}" for year in range(start - 1, start + 3))


def default_academic_year(today: date) -> str:
    start = current_school_year_start(today)
    return f"{start}-{start + 1}"


def parse_academic_year(value: str) -> AcademicYear:
    match = SCHOOL_YEAR_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError("L'année scolaire sélectionnée n'est pas valide. Merci de la sélectionner à nouveau.")
    start = int(match.group("start"))
    end = int(match.group("end"))
    if end != start + 1:
        raise ValueError("L'année scolaire sélectionnée n'est pas valide. Merci de la sélectionner à nouveau.")
    return AcademicYear(start, end)
