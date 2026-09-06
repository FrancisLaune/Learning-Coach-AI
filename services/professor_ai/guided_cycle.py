"""Guided student cycle Accueil → Diagnostic → Devoir → Séance → Synthèse (LCAI-0022C)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from services.professor_ai.models import ProfessorOperatingMode, SessionPlan

CYCLE_STATE_KEY = "professor_ai_cycle_step"
FOCUS_DIAGNOSTIC_KEY = "professor_ai_focus_diagnostic"
FOCUS_HOMEWORK_KEY = "professor_ai_focus_homework_id"
CLOSED_SESSION_PREFIX = "professor_ai_cycle_closed_"


class GuidedCycleStep(StrEnum):
    ACCUEIL = "ACCUEIL"
    DIAGNOSTIC = "DIAGNOSTIC"
    DEVOIR = "DEVOIR"
    SEANCE = "SEANCE"
    SYNTHESE = "SYNTHESE"


_STEP_ORDER = (
    GuidedCycleStep.ACCUEIL,
    GuidedCycleStep.DIAGNOSTIC,
    GuidedCycleStep.DEVOIR,
    GuidedCycleStep.SEANCE,
    GuidedCycleStep.SYNTHESE,
)

_STEP_LABELS = {
    GuidedCycleStep.ACCUEIL: "Accueil",
    GuidedCycleStep.DIAGNOSTIC: "Diagnostic",
    GuidedCycleStep.DEVOIR: "Devoir",
    GuidedCycleStep.SEANCE: "Séance",
    GuidedCycleStep.SYNTHESE: "Synthèse",
}

_PAGE_BY_STEP = {
    GuidedCycleStep.ACCUEIL: "Accueil",
    GuidedCycleStep.DIAGNOSTIC: "Accueil",
    GuidedCycleStep.DEVOIR: "Devoir personnalisé",
    GuidedCycleStep.SEANCE: "S'entraîner",
    GuidedCycleStep.SYNTHESE: "S'entraîner",
}

_CTA_BY_STEP = {
    GuidedCycleStep.ACCUEIL: "Voir l'accueil",
    GuidedCycleStep.DIAGNOSTIC: "Faire le diagnostic",
    GuidedCycleStep.DEVOIR: "Ouvrir mes devoirs",
    GuidedCycleStep.SEANCE: "Continuer la séance",
    GuidedCycleStep.SYNTHESE: "Voir la synthèse",
}

_DIAGNOSTIC_DONE = frozenset({"COMPLETED", "PLANNED"})
_ACTIVE_SESSION = frozenset({"READY", "RUNNING", "PAUSED"})


@dataclass(frozen=True, slots=True)
class GuidedCycleSnapshot:
    """Recommended next step for the soft-guided parcours."""

    step: GuidedCycleStep
    page: str
    cta_label: str
    progress_caption: str
    homework_id: int | None = None
    session_id: int | None = None
    focus_diagnostic: bool = False


def step_label(step: GuidedCycleStep) -> str:
    return _STEP_LABELS[step]


def step_index(step: GuidedCycleStep) -> int:
    return _STEP_ORDER.index(step) + 1


def progress_caption(step: GuidedCycleStep) -> str:
    return f"Étape {step_index(step)}/{len(_STEP_ORDER)} — {step_label(step)}"


def closed_session_key(session_id: int) -> str:
    return f"{CLOSED_SESSION_PREFIX}{int(session_id)}"


def diagnostic_required(diagnostic_status: str, *, mode: ProfessorOperatingMode) -> bool:
    if mode is ProfessorOperatingMode.MANUAL:
        return False
    token = (diagnostic_status or "UNKNOWN").strip().upper()
    if token in {"UNKNOWN", ""}:
        return False
    return token not in _DIAGNOSTIC_DONE


def resolve_guided_cycle(
    plan: SessionPlan,
    *,
    active_session_id: int | None = None,
    active_session_status: str | None = None,
    synthesis_closed_for_session: int | None = None,
) -> GuidedCycleSnapshot:
    """Pick the next soft-guided step from orchestrator plan + live session signals."""
    status = (active_session_status or "").strip().upper()
    if active_session_id is not None and (status in _ACTIVE_SESSION or status == ""):
        return GuidedCycleSnapshot(
            step=GuidedCycleStep.SEANCE,
            page=_PAGE_BY_STEP[GuidedCycleStep.SEANCE],
            cta_label=_CTA_BY_STEP[GuidedCycleStep.SEANCE],
            progress_caption=progress_caption(GuidedCycleStep.SEANCE),
            session_id=int(active_session_id),
        )

    if (
        active_session_id is not None
        and status == "COMPLETED"
        and synthesis_closed_for_session != int(active_session_id)
    ):
        return GuidedCycleSnapshot(
            step=GuidedCycleStep.SYNTHESE,
            page=_PAGE_BY_STEP[GuidedCycleStep.SYNTHESE],
            cta_label=_CTA_BY_STEP[GuidedCycleStep.SYNTHESE],
            progress_caption=progress_caption(GuidedCycleStep.SYNTHESE),
            session_id=int(active_session_id),
        )

    if diagnostic_required(plan.diagnostic_status, mode=plan.mode):
        return GuidedCycleSnapshot(
            step=GuidedCycleStep.DIAGNOSTIC,
            page=_PAGE_BY_STEP[GuidedCycleStep.DIAGNOSTIC],
            cta_label=_CTA_BY_STEP[GuidedCycleStep.DIAGNOSTIC],
            progress_caption=progress_caption(GuidedCycleStep.DIAGNOSTIC),
            focus_diagnostic=True,
        )

    context = plan.dashboard.context
    if context.homework_overdue:
        hw = context.homework_overdue[0]
        return GuidedCycleSnapshot(
            step=GuidedCycleStep.DEVOIR,
            page=_PAGE_BY_STEP[GuidedCycleStep.DEVOIR],
            cta_label=f"Terminer : {hw.subject_label}",
            progress_caption=progress_caption(GuidedCycleStep.DEVOIR),
            homework_id=int(hw.homework_id),
        )
    if context.homework_todo:
        hw = context.homework_todo[0]
        return GuidedCycleSnapshot(
            step=GuidedCycleStep.DEVOIR,
            page=_PAGE_BY_STEP[GuidedCycleStep.DEVOIR],
            cta_label=f"Commencer : {hw.subject_label}",
            progress_caption=progress_caption(GuidedCycleStep.DEVOIR),
            homework_id=int(hw.homework_id),
        )

    return GuidedCycleSnapshot(
        step=GuidedCycleStep.ACCUEIL,
        page=_PAGE_BY_STEP[GuidedCycleStep.ACCUEIL],
        cta_label=plan.welcome.primary_action or _CTA_BY_STEP[GuidedCycleStep.ACCUEIL],
        progress_caption=progress_caption(GuidedCycleStep.ACCUEIL),
    )
