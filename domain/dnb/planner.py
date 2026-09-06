"""LCAI-0031 — Brevet study planner until DNB (pure DTO builder)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.dnb.calendar import DnbExamCalendar, load_dnb_exam_calendar
from domain.dnb.prioritizer import SkillPriorityResult


@dataclass(frozen=True, slots=True)
class WeeklyFocusItem:
    skill_id: int
    label: str
    reason: str
    suggested_minutes: int


@dataclass(frozen=True, slots=True)
class BrevetStudyPlan:
    as_of: date
    days_until_first_exam: int | None
    weekly_minutes: int
    objective: str
    focuses: tuple[WeeklyFocusItem, ...]
    recommended_sessions: tuple[str, ...]
    mock_exam_hint: str
    readiness_hint: str


def build_brevet_study_plan(
    *,
    priorities: tuple[SkillPriorityResult, ...] | list[SkillPriorityResult],
    weekly_minutes: int = 180,
    today: date | None = None,
    calendar: DnbExamCalendar | None = None,
    readiness_score: float | None = None,
) -> BrevetStudyPlan:
    as_of = today or date.today()
    cal = calendar or load_dnb_exam_calendar()
    days = cal.countdown_days(today=as_of)
    budget = max(60, min(600, int(weekly_minutes)))
    top = tuple(priorities[:5])
    if not top:
        focuses: tuple[WeeklyFocusItem, ...] = ()
        sessions = ("Faire le diagnostic initial Brevet", "Revoir un chapitre fragile")
        objective = "Lancer le diagnostic initial pour construire le plan."
    else:
        share = max(15, budget // max(1, len(top)))
        focuses = tuple(
            WeeklyFocusItem(
                skill_id=item.skill_id,
                label=item.label,
                reason=item.reason,
                suggested_minutes=share,
            )
            for item in top
        )
        sessions = (
            f"Session prioritaire : {top[0].label}",
            "Devoir personnalisé panaché (catalogue puis IA si déficit)",
            "Révision espacée des notions dues",
        )
        objective = f"Consolider {top[0].label} et les compétences critiques avant le DNB."

    if days is None:
        mock_hint = "Planifier un premier Brevet blanc après le diagnostic."
    elif days > 120:
        mock_hint = "Premier Brevet blanc recommandé dans 4 à 6 semaines."
    elif days > 45:
        mock_hint = "Brevet blanc matière à planifier ce mois-ci."
    else:
        mock_hint = "Enchaîner Brevets blancs et annales ; corriger les lacunes critiques."

    if readiness_score is None:
        readiness_hint = "Readiness non encore calculé — terminer le diagnostic."
    elif readiness_score >= 0.8:
        readiness_hint = f"Readiness élevé ({readiness_score:.0%}) — maintenir le rythme et les blancs."
    elif readiness_score >= 0.55:
        readiness_hint = f"Readiness intermédiaire ({readiness_score:.0%}) — prioriser les fragilités."
    else:
        readiness_hint = f"Readiness bas ({readiness_score:.0%}) — remédiation et prérequis d'abord."

    return BrevetStudyPlan(
        as_of=as_of,
        days_until_first_exam=days,
        weekly_minutes=budget,
        objective=objective,
        focuses=focuses,
        recommended_sessions=sessions,
        mock_exam_hint=mock_hint,
        readiness_hint=readiness_hint,
    )
