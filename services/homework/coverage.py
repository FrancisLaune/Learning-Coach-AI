"""CM1→3e homework coverage matrix (LCAI-0030-D)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from domain.unified_experience.models import AssignmentType, DifficultyMode, HomeworkRequest
from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository
from services.homework.config import HomeworkAiCompletionSettings
from services.homework.eligibility import completion_flags_enabled
from services.platform_runtime import FeatureFlagService, default_flags

CERTIFICATION_GRADES: tuple[str, ...] = (
    "FR-CM1",
    "FR-CM2",
    "FR-6E",
    "FR-5E",
    "FR-4E",
    "FR-3E",
)


@dataclass(frozen=True, slots=True)
class SubjectCoverageCell:
    grade_code: str
    subject_id: int
    subject_code: str
    subject_label: str
    eligible_count: int
    status: str  # available | limited | generable | gap
    status_label: str


def classify_coverage_status(eligible_count: int, *, generable: bool) -> tuple[str, str]:
    if eligible_count >= 10:
        return "available", "Disponible"
    if eligible_count >= 1:
        return "limited", "Couverture limitée"
    if generable:
        return "generable", "Générable (IA)"
    return "gap", "Manquant"


class HomeworkCoverageService:
    """Build an availability/generable/gap matrix for CM1→3e subjects."""

    def __init__(
        self,
        repository: DuckDBUnifiedExperienceRepository,
        *,
        feature_flags: FeatureFlagService | None = None,
        completion_settings: HomeworkAiCompletionSettings | None = None,
    ) -> None:
        self.repository = repository
        self.feature_flags = feature_flags or default_flags()
        self.completion_settings = completion_settings or HomeworkAiCompletionSettings.from_environment()

    def matrix(self, *, exercise_count: int = 10) -> tuple[SubjectCoverageCell, ...]:
        cells: list[SubjectCoverageCell] = []
        grade_map = {code: grade_id for grade_id, code, _label in self.repository.grade_levels()}
        ai_on = completion_flags_enabled(self.feature_flags)
        for grade_code in CERTIFICATION_GRADES:
            grade_id = grade_map.get(grade_code)
            if grade_id is None:
                continue
            subjects = self.repository.curriculum_subjects_for_grade(int(grade_id))
            for subject_id, subject_code, subject_label in subjects:
                preview = self.repository.select_approved_content_detailed(
                    HomeworkRequest(
                        0,
                        "SYSTEM",
                        "lcai-0030d-coverage",
                        AssignmentType.GLOBAL_SUBJECT,
                        int(subject_id),
                        int(grade_id),
                        (),
                        (),
                        DifficultyMode.ADAPTIVE,
                        max(exercise_count, 40),
                        None,
                        datetime.now(tz=UTC),
                    )
                )
                eligible = len(preview.content_ids)
                generable = bool(
                    ai_on
                    and self.completion_settings.grade_allowed(grade_code)
                    and self.completion_settings.subject_allowed(str(subject_code))
                )
                status, label = classify_coverage_status(eligible, generable=generable)
                cells.append(
                    SubjectCoverageCell(
                        grade_code=grade_code,
                        subject_id=int(subject_id),
                        subject_code=str(subject_code),
                        subject_label=str(subject_label),
                        eligible_count=eligible,
                        status=status,
                        status_label=label,
                    )
                )
        return tuple(cells)
