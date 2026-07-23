from datetime import date

from domain.decision.enums import ObjectiveKind
from domain.onboarding.enums import CompatibilityStatus, ValidationSeverity
from domain.onboarding.models import OnboardingRequest, OnboardingValidationResult, ValidationIssue
from domain.onboarding.policies import OnboardingConfiguration

NEXT_GRADE = {"FR-4E": "FR-3E", "FR-3E": "FR-2NDE", "FR-2NDE": "FR-1ERE", "FR-1ERE": "FR-TERM"}


def validate_onboarding(
    request: OnboardingRequest,
    known_subject_ids: set[int],
    config: OnboardingConfiguration | None = None,
    today: date | None = None,
) -> OnboardingValidationResult:
    config = config or OnboardingConfiguration()
    today = today or date.today()
    issues: list[ValidationIssue] = []
    compatibility = next(
        (
            row
            for row in config.goal_matrix
            if row.grade_code == request.current_grade.code and row.objective is request.goal.objective
        ),
        None,
    )
    if compatibility is None or compatibility.status is CompatibilityStatus.INCOMPATIBLE:
        compatible = sorted(
            {row.objective.value for row in config.goal_matrix if row.grade_code == request.current_grade.code}
        )
        issues.append(
            ValidationIssue(
                "INCOMPATIBLE_GOAL",
                ValidationSeverity.ERROR,
                "goal.objective",
                "Objectif incompatible avec ce niveau.",
                "GOAL_MATRIX",
                ", ".join(compatible),
            )
        )
    elif compatibility.status is CompatibilityStatus.ANTICIPATION:
        issues.append(
            ValidationIssue(
                "ANTICIPATION_GOAL",
                ValidationSeverity.WARNING,
                "goal.objective",
                "Objectif disponible en anticipation.",
                "GOAL_ANTICIPATION",
            )
        )
    if compatibility and compatibility.target_grade_required and request.goal.target_grade is None:
        issues.append(
            ValidationIssue(
                "TARGET_GRADE_REQUIRED",
                ValidationSeverity.ERROR,
                "goal.target_grade",
                "Le niveau cible est obligatoire.",
                "NEXT_GRADE_REQUIRES_TARGET",
                NEXT_GRADE.get(request.current_grade.code),
            )
        )
    if (
        request.goal.objective is ObjectiveKind.PREPARATION_NEXT_GRADE
        and request.goal.target_grade
        and NEXT_GRADE.get(request.current_grade.code) != request.goal.target_grade.code
    ):
        issues.append(
            ValidationIssue(
                "INVALID_TARGET_GRADE",
                ValidationSeverity.ERROR,
                "goal.target_grade",
                "Transition de niveau incohérente.",
                "NEXT_GRADE_SEQUENCE",
                NEXT_GRADE.get(request.current_grade.code),
            )
        )
    if compatibility and compatibility.examination_required and not request.goal.examination_code:
        issues.append(
            ValidationIssue(
                "EXAM_REQUIRED",
                ValidationSeverity.ERROR,
                "goal.examination_code",
                "Un examen doit être précisé.",
                "EXAM_GOAL_REQUIRES_EXAM",
            )
        )
    if request.goal.target_date and request.goal.target_date < today:
        issues.append(
            ValidationIssue(
                "TARGET_DATE_IN_PAST",
                ValidationSeverity.ERROR,
                "goal.target_date",
                "La date cible est passée.",
                "FUTURE_TARGET_DATE",
            )
        )
    unknown = sorted({item.subject_id for item in request.subjects} - known_subject_ids)
    if unknown:
        issues.append(
            ValidationIssue(
                "UNKNOWN_SUBJECT",
                ValidationSeverity.ERROR,
                "subjects",
                f"Matières inconnues : {unknown}",
                "REFERENCE_SUBJECT_REQUIRED",
            )
        )
    if not request.study.availability:
        issues.append(
            ValidationIssue(
                "NO_AVAILABILITY",
                ValidationSeverity.WARNING,
                "study.availability",
                "Aucune disponibilité définie.",
                "ACTIVE_PLAN_AVAILABILITY",
            )
        )
    if request.study.daily_duration_minutes <= 0:
        issues.append(
            ValidationIssue(
                "INVALID_DAILY_DURATION",
                ValidationSeverity.ERROR,
                "study.daily_duration_minutes",
                "La durée doit être positive.",
                "POSITIVE_DURATION",
            )
        )
    return OnboardingValidationResult(tuple(issues))
