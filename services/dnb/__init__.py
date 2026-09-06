"""LCAI-0031 — Product-facing DNB helpers (grades, subjects, calendar, engine)."""

from __future__ import annotations

from datetime import date
from typing import Any

from domain.dnb import (
    DnbExamCalendar,
    DnbProductConfig,
    SubjectCapabilities,
    capabilities_for,
    load_dnb_exam_calendar,
    load_dnb_product_config,
)
from domain.dnb.archives import ArchiveProvenance, assert_not_official_ai, seed_archive_catalog
from domain.dnb.exam_builder import BrevetExamBlueprint, build_brevet_exam, build_global_mock_exam
from domain.dnb.exam_templates import BrevetExamCode, BrevetExamMode, BrevetExamTemplate, template_for
from domain.dnb.oral import OralProjectPlan, build_oral_project, generate_jury_questions
from domain.dnb.planner import BrevetStudyPlan, build_brevet_study_plan
from domain.dnb.prioritizer import (
    BrevetImportance,
    SkillPriorityInput,
    SkillPriorityResult,
    default_importance_for_subject,
    prioritize_skills,
)
from domain.dnb.readiness import BrevetReadinessScore, compute_brevet_readiness
from domain.dnb.remediation import PrerequisiteGap, RemediationPlan, build_remediation_plan
from domain.dnb.subject_capabilities import terminal_brevet_subject_codes
from domain.pedagogical_intelligence.paths import brevet_baseline_path_code
from services.dnb.coach import (
    COACH_NAME,
    BrevetCoachContext,
    build_coach_system_briefing,
    build_coach_user_turn,
    coach_context_from_home,
)
from services.dnb.coach_decisions import CoachDecision, decide_next_work, format_decision_for_student


def product_config() -> DnbProductConfig:
    return load_dnb_product_config()


def exam_calendar() -> DnbExamCalendar:
    return load_dnb_exam_calendar()


def product_facing_grade_codes() -> frozenset[str]:
    return frozenset({product_config().primary_grade_code})


def is_product_facing_grade(grade_code: str | None) -> bool:
    if grade_code is None:
        return False
    return product_config().is_user_facing_grade(grade_code)


def filter_product_facing_grades(
    grades: tuple[tuple[int, str, str], ...],
    *,
    include_remediation: bool = False,
) -> tuple[tuple[int, str, str], ...]:
    """Filter (id, code, label) rows for product UX."""
    config = product_config()
    if include_remediation:
        allowed = frozenset({config.primary_grade_code, *config.remediation_grade_codes})
    else:
        allowed = frozenset({config.primary_grade_code})
    return tuple(row for row in grades if str(row[1]).upper() in allowed)


def filter_brevet_prep_subjects(
    subjects: tuple[tuple[int, str, str], ...],
) -> tuple[tuple[int, str, str], ...]:
    """Keep terminal DNB subjects (+ oral); drop continuous-only languages from Brevet paths."""
    config = product_config()
    return tuple(row for row in subjects if config.belongs_in_brevet_prep_path(str(row[1])))


def subject_capabilities(subject_code: str) -> SubjectCapabilities:
    return capabilities_for(subject_code)


def brevet_terminal_codes() -> frozenset[str]:
    return terminal_brevet_subject_codes()


def baseline_diagnostic_path_code() -> str:
    return brevet_baseline_path_code()


def skill_priorities(
    items: list[SkillPriorityInput] | tuple[SkillPriorityInput, ...],
    *,
    today: date | None = None,
    limit: int = 10,
) -> tuple[SkillPriorityResult, ...]:
    days = exam_calendar().countdown_days(today=today)
    return prioritize_skills(items, days_until_exam=days, limit=limit)


def priorities_from_mastery_rows(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    today: date | None = None,
    limit: int = 10,
) -> tuple[SkillPriorityResult, ...]:
    """Build priorities from simple mastery dicts.

    Expected keys: skill_id, label, mastery_score; optional subject_code,
    prerequisite_impact, revision_urgency, confidence.
    """
    items: list[SkillPriorityInput] = []
    for row in rows:
        items.append(
            SkillPriorityInput(
                skill_id=int(row["skill_id"]),
                label=str(row.get("label") or f"Compétence {row['skill_id']}"),
                mastery_score=float(row.get("mastery_score") or 0.0),
                importance=default_importance_for_subject(
                    None if row.get("subject_code") is None else str(row.get("subject_code"))
                ),
                prerequisite_impact=float(row.get("prerequisite_impact") or 0.0),
                revision_urgency=float(row.get("revision_urgency") or 0.0),
                confidence=float(row.get("confidence") or 0.5),
            )
        )
    return skill_priorities(items, today=today, limit=limit)


def study_plan(
    priorities: tuple[SkillPriorityResult, ...] | list[SkillPriorityResult],
    *,
    weekly_minutes: int = 180,
    today: date | None = None,
    readiness_score: float | None = None,
) -> BrevetStudyPlan:
    return build_brevet_study_plan(
        priorities=priorities,
        weekly_minutes=weekly_minutes,
        today=today,
        calendar=exam_calendar(),
        readiness_score=readiness_score,
    )


def remediation_for_gap(gap: PrerequisiteGap, *, estimated_minutes: int = 15) -> RemediationPlan:
    return build_remediation_plan(gap, estimated_minutes=estimated_minutes)


def readiness_score(
    *,
    mastery: float,
    coverage: float,
    stability: float = 0.5,
    exam_performance: float = 0.0,
    critical_gap_ratio: float = 0.0,
) -> BrevetReadinessScore:
    return compute_brevet_readiness(
        mastery=mastery,
        coverage=coverage,
        stability=stability,
        exam_performance=exam_performance,
        critical_gap_ratio=critical_gap_ratio,
    )


def brevet_exam(
    exam_code: str,
    *,
    mode: str = BrevetExamMode.BREVET_STYLE.value,
    science_pair: tuple[str, str] | None = None,
    priorities: tuple[SkillPriorityResult, ...] | list[SkillPriorityResult] | None = None,
) -> BrevetExamBlueprint:
    return build_brevet_exam(
        exam_code,
        mode=mode,
        science_pair=science_pair,
        priorities=priorities,
    )


def mock_brevet_session(
    *,
    include_oral: bool = False,
    science_pair: tuple[str, str] | None = None,
) -> tuple[BrevetExamBlueprint, ...]:
    return build_global_mock_exam(include_oral=include_oral, science_pair=science_pair)


def oral_project(
    *,
    title: str,
    problematique: str,
    outline: tuple[str, ...] | list[str],
) -> OralProjectPlan:
    return build_oral_project(title=title, problematique=problematique, outline=outline)


def oral_jury_pack(project: OralProjectPlan):
    return generate_jury_questions(project)


def official_archive_seeds():
    return seed_archive_catalog()


def reject_ai_as_official(provenance: str, *, is_ai_generated: bool = True) -> None:
    assert_not_official_ai(provenance, is_ai_generated=is_ai_generated)


__all__ = [
    "ArchiveProvenance",
    "BrevetCoachContext",
    "BrevetExamBlueprint",
    "BrevetExamCode",
    "BrevetExamMode",
    "BrevetExamTemplate",
    "BrevetImportance",
    "BrevetReadinessScore",
    "BrevetStudyPlan",
    "COACH_NAME",
    "CoachDecision",
    "OralProjectPlan",
    "PrerequisiteGap",
    "RemediationPlan",
    "SkillPriorityInput",
    "SkillPriorityResult",
    "baseline_diagnostic_path_code",
    "brevet_exam",
    "brevet_terminal_codes",
    "build_coach_system_briefing",
    "build_coach_user_turn",
    "coach_context_from_home",
    "decide_next_work",
    "exam_calendar",
    "filter_brevet_prep_subjects",
    "filter_product_facing_grades",
    "format_decision_for_student",
    "is_product_facing_grade",
    "mock_brevet_session",
    "official_archive_seeds",
    "oral_jury_pack",
    "oral_project",
    "priorities_from_mastery_rows",
    "product_config",
    "product_facing_grade_codes",
    "readiness_score",
    "reject_ai_as_official",
    "remediation_for_gap",
    "skill_priorities",
    "study_plan",
    "subject_capabilities",
    "template_for",
]
