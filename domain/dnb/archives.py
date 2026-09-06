"""LCAI-0031 — Official exam archive provenance model (no AI-as-official)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ArchiveProvenance(StrEnum):
    OFFICIAL_EXAM = "OFFICIAL_EXAM"
    OFFICIAL_ZERO_SUBJECT = "OFFICIAL_ZERO_SUBJECT"
    MOCK_EXAM = "MOCK_EXAM"
    GENERATED_MOCK_EXAM = "GENERATED_MOCK_EXAM"


class ArchiveValidationStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class ExamArchiveMeta:
    archive_code: str
    title: str
    year: int
    session: str
    zone: str
    series: str
    exam_code: str
    duration_minutes: int
    provenance: ArchiveProvenance
    source_reference: str
    validation_status: ArchiveValidationStatus = ArchiveValidationStatus.DRAFT
    curriculum_compatibility: str = "FR_3E_2027_PARTIAL"

    def is_official(self) -> bool:
        return self.provenance in {
            ArchiveProvenance.OFFICIAL_EXAM,
            ArchiveProvenance.OFFICIAL_ZERO_SUBJECT,
        }


def seed_archive_catalog() -> tuple[ExamArchiveMeta, ...]:
    """Metadata-only seeds for known official references (no question bodies)."""
    return (
        ExamArchiveMeta(
            archive_code="DNB-2026-METROPOLE-MATHS",
            title="DNB 2026 Métropole — Mathématiques",
            year=2026,
            session="normale",
            zone="metropole",
            series="generale",
            exam_code="MATHEMATICS_WRITTEN",
            duration_minutes=120,
            provenance=ArchiveProvenance.OFFICIAL_EXAM,
            source_reference="Éduscol / MEN — annales DNB",
            validation_status=ArchiveValidationStatus.REVIEW,
            curriculum_compatibility="FR_3E_2027_TRAINING",
        ),
        ExamArchiveMeta(
            archive_code="DNB-2026-METROPOLE-FRANCAIS",
            title="DNB 2026 Métropole — Français",
            year=2026,
            session="normale",
            zone="metropole",
            series="generale",
            exam_code="FRENCH_WRITTEN",
            duration_minutes=180,
            provenance=ArchiveProvenance.OFFICIAL_EXAM,
            source_reference="Éduscol / MEN — annales DNB",
            validation_status=ArchiveValidationStatus.REVIEW,
            curriculum_compatibility="FR_3E_2027_TRAINING",
        ),
        ExamArchiveMeta(
            archive_code="DNB-MATHS-SUJET-ZERO-A",
            title="Sujet zéro officiel Mathématiques A",
            year=2026,
            session="sujet_zero",
            zone="national",
            series="generale",
            exam_code="MATHEMATICS_WRITTEN",
            duration_minutes=120,
            provenance=ArchiveProvenance.OFFICIAL_ZERO_SUBJECT,
            source_reference="Éduscol — sujet zéro",
            validation_status=ArchiveValidationStatus.REVIEW,
        ),
    )


def ensure_ai_content_not_marked_official(
    *,
    is_ai_generated: bool,
    provenance: ArchiveProvenance | str,
) -> None:
    """Guardrail: AI-generated content must never be stored as official archive."""
    value = ArchiveProvenance(str(provenance))
    if is_ai_generated and value in {
        ArchiveProvenance.OFFICIAL_EXAM,
        ArchiveProvenance.OFFICIAL_ZERO_SUBJECT,
    }:
        raise ValueError("Un contenu généré par IA ne peut pas être marqué comme annale officielle.")


# Back-compat alias used by services façade.
def assert_not_official_ai(provenance: ArchiveProvenance | str, *, is_ai_generated: bool = True) -> None:
    ensure_ai_content_not_marked_official(is_ai_generated=is_ai_generated, provenance=provenance)
