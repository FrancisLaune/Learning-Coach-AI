"""LCAI-0031 Phase 5 — auditable Coach Brevet decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from services.dnb.coach import COACH_NAME, BrevetCoachContext


@dataclass(frozen=True, slots=True)
class CoachDecision:
    """One pedagogical decision the unique Coach Brevet can justify."""

    decision_type: str
    summary: str
    rationale: str
    next_action: str
    candidates: tuple[str, ...] = ()
    created_at: datetime | None = None
    engine_version: str = "brevet-coach-v1"

    def as_audit_payload(self) -> dict[str, Any]:
        return {
            "coach": COACH_NAME,
            "decision_type": self.decision_type,
            "summary": self.summary,
            "rationale": self.rationale,
            "next_action": self.next_action,
            "candidates": list(self.candidates),
            "engine_version": self.engine_version,
            "created_at": (self.created_at or datetime.now(UTC)).isoformat(),
        }


def decide_next_work(context: BrevetCoachContext) -> CoachDecision:
    """Decide the next student action from the full coach pack."""
    now = datetime.now(UTC)
    if context.has_exercise():
        return CoachDecision(
            decision_type="EXERCISE_HELP",
            summary="Guider la méthode sur l'exercice en cours",
            rationale=(
                f"Exercice actif en {context.subject_label or 'matière'}"
                + (f" — {context.chapter_label}" if context.chapter_label else "")
            ),
            next_action="Reformuler la consigne et proposer la première étape",
            candidates=("indice", "rappel de notion", "exemple similaire"),
            created_at=now,
        )
    if context.priorities:
        top = context.priorities[0]
        return CoachDecision(
            decision_type="PRIORITY_WORK",
            summary=f"Prioriser : {top}",
            rationale=(
                f"Readiness {context.readiness_band or 'n/a'} ; "
                f"{context.days_until_exam if context.days_until_exam is not None else '?'} j avant DNB"
            ),
            next_action=f"Lancer une révision courte sur : {top}",
            candidates=context.priorities[:4],
            created_at=now,
        )
    if context.fragile_skills:
        skill = context.fragile_skills[0]
        return CoachDecision(
            decision_type="REMEDIATE_FRAGILE",
            summary=f"Consolider le point faible : {skill}",
            rationale="Maîtrise fragile détectée avant les écrits",
            next_action=f"Séance remédiation / devoir ciblé : {skill}",
            candidates=context.fragile_skills[:4],
            created_at=now,
        )
    return CoachDecision(
        decision_type="WEEKLY_PLAN",
        summary=context.weekly_objective or "Établir un plan hebdomadaire Objectif Brevet",
        rationale=context.readiness_explanation or "Profil encore incomplet — démarrer par un diagnostic",
        next_action=context.mock_exam_hint or "Ouvrir le diagnostic / première séance 3e",
        candidates=(),
        created_at=now,
    )


def format_decision_for_student(decision: CoachDecision) -> str:
    return (
        f"{COACH_NAME} — décision : {decision.summary}. "
        f"Pourquoi : {decision.rationale}. "
        f"Prochaine action : {decision.next_action}."
    )
