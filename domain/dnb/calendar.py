"""Versioned DNB exam calendar — never hard-code dates in Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

CALENDAR_VERSION: Final[str] = "DNB-2027-METROPOLE-V1"
SOURCE_REFERENCE: Final[str] = "Calendrier prévisionnel session normale DNB 2027 — métropole (écrits)"
TIMEZONE: Final[str] = "Europe/Paris"


@dataclass(frozen=True, slots=True)
class DnbExamDate:
    exam_code: str
    label: str
    exam_date: date
    subject_codes: tuple[str, ...]
    duration_minutes: int | None = None
    coefficient: float | None = None


@dataclass(frozen=True, slots=True)
class DnbExamCalendar:
    version: str
    session_code: str
    timezone: str
    source_reference: str
    effective_from: date
    written_exams: tuple[DnbExamDate, ...]

    def countdown_days(self, *, today: date | None = None) -> int | None:
        """Days until the first written exam (inclusive of exam day as 0)."""
        if not self.written_exams:
            return None
        pivot = today or date.today()
        first = min(item.exam_date for item in self.written_exams)
        return (first - pivot).days

    def exam_for_code(self, exam_code: str) -> DnbExamDate | None:
        needle = exam_code.upper()
        for item in self.written_exams:
            if item.exam_code.upper() == needle:
                return item
        return None


def load_dnb_exam_calendar() -> DnbExamCalendar:
    """Métropole 2027 — dates from product ticket §31 (versioned config)."""
    return DnbExamCalendar(
        version=CALENDAR_VERSION,
        session_code="DNB-2027",
        timezone=TIMEZONE,
        source_reference=SOURCE_REFERENCE,
        effective_from=date(2026, 9, 1),
        written_exams=(
            DnbExamDate(
                exam_code="FRENCH_WRITTEN",
                label="Français — écrit",
                exam_date=date(2027, 6, 24),
                subject_codes=("FRENCH",),
                duration_minutes=180,
                coefficient=2.0,
            ),
            DnbExamDate(
                exam_code="HISTORY_GEOGRAPHY_EMC_WRITTEN",
                label="Histoire-Géographie-EMC — écrit",
                exam_date=date(2027, 6, 25),
                subject_codes=("HISTORY", "GEOGRAPHY", "EMC"),
                duration_minutes=120,
                coefficient=2.0,  # HG 1.5 + EMC 0.5
            ),
            DnbExamDate(
                exam_code="SCIENCES_WRITTEN",
                label="Sciences — écrit",
                exam_date=date(2027, 6, 28),
                subject_codes=("PHYSICS_CHEMISTRY", "SVT", "TECHNOLOGY"),
                duration_minutes=60,
                coefficient=2.0,
            ),
            DnbExamDate(
                exam_code="MATHEMATICS_WRITTEN",
                label="Mathématiques — écrit",
                exam_date=date(2027, 6, 28),
                subject_codes=("MATHEMATICS",),
                duration_minutes=120,
                coefficient=2.0,
            ),
        ),
    )
