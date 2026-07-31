"""Banner state for the Professor AI fixed strip (LCAI-0022B)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from services.professor_ai.models import ProfessorOperatingMode


class BannerPresenceState(StrEnum):
    """Master Book visual states of the Professor IA bandeau."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


@dataclass(frozen=True, slots=True)
class ProfessorAIBannerView:
    learner_id: int
    teacher_name: str
    mode: ProfessorOperatingMode
    presence: BannerPresenceState
    message: str
    primary_action: str
    secondary_actions: tuple[str, ...]
    mode_editable: bool
    feature_enabled: bool
    caption: str


_MODE_LABELS = {
    ProfessorOperatingMode.PROFESSOR: "Mode Professeur IA",
    ProfessorOperatingMode.COMPANION: "Mode Compagnon",
    ProfessorOperatingMode.MANUAL: "Mode manuel",
}

_PRESENCE_LABELS = {
    BannerPresenceState.IDLE: "Disponible",
    BannerPresenceState.LISTENING: "À l'écoute",
    BannerPresenceState.THINKING: "Réflexion",
    BannerPresenceState.SPEAKING: "Parole",
}


def mode_label(mode: ProfessorOperatingMode) -> str:
    return _MODE_LABELS[mode]


def presence_label(presence: BannerPresenceState) -> str:
    return _PRESENCE_LABELS[presence]


def parse_operating_mode(value: str | None) -> ProfessorOperatingMode:
    token = (value or ProfessorOperatingMode.MANUAL.value).strip().upper()
    try:
        return ProfessorOperatingMode(token)
    except ValueError:
        return ProfessorOperatingMode.MANUAL


def build_banner_view(
    *,
    learner_id: int,
    teacher_name: str | None,
    mode: ProfessorOperatingMode,
    feature_enabled: bool,
    parent_locked: bool,
    message: str,
    primary_action: str = "",
    secondary_actions: tuple[str, ...] = (),
    presence: BannerPresenceState = BannerPresenceState.IDLE,
) -> ProfessorAIBannerView:
    caption = mode_label(mode)
    if not feature_enabled:
        caption = "Professeur IA désactivé — mode manuel"
        mode = ProfessorOperatingMode.MANUAL
    return ProfessorAIBannerView(
        learner_id=learner_id,
        teacher_name=(teacher_name or "Professeur").strip() or "Professeur",
        mode=mode,
        presence=presence,
        message=message.strip() or "Je suis prêt à t'accompagner.",
        primary_action=primary_action,
        secondary_actions=secondary_actions,
        mode_editable=bool(feature_enabled and not parent_locked),
        feature_enabled=feature_enabled,
        caption=f"{caption} · {_PRESENCE_LABELS[presence]}",
    )
