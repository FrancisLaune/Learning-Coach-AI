"""ChatGPT Voice — unique Coach Brevet link (LCAI-0030-E / LCAI-0031 Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from services.dnb.coach import (
    COACH_NAME,
    BrevetCoachContext,
    build_coach_system_briefing,
    build_coach_user_turn,
    coach_context_from_home,
)

CHATGPT_BASE_URL = "https://chatgpt.com/"
SCHOOL_FRAME_MESSAGE = (
    f"Cadre scolaire — {COACH_NAME} unique : pose des questions de cours, méthode, DNB. "
    "Le contexte complet de ton parcours est envoyé à chaque ouverture."
)
VOICE_HINT = (
    "Dans ChatGPT, tu peux utiliser le mode vocal (micro) pour parler avec ton Coach Brevet "
    "comme avec un professeur."
)


@dataclass(frozen=True, slots=True)
class ChatGptVoiceContext:
    """Compat thin wrapper — prefer BrevetCoachContext for full packs."""

    display_name: str = ""
    grade_label: str = "3e"
    subject_label: str = ""
    chapter_label: str = ""
    objective: str = ""
    topic_hint: str = ""
    coach: BrevetCoachContext | None = None

    def as_coach(self) -> BrevetCoachContext:
        if self.coach is not None:
            return self.coach
        return BrevetCoachContext(
            display_name=self.display_name,
            grade_label=self.grade_label or "3e",
            subject_label=self.subject_label,
            chapter_label=self.chapter_label,
            weekly_objective=self.objective,
            student_question=self.topic_hint,
        )


def build_context_prompt(context: ChatGptVoiceContext | BrevetCoachContext) -> str:
    """Full Coach Brevet briefing + student turn (for URL prefill / copy)."""
    coach = context.as_coach() if isinstance(context, ChatGptVoiceContext) else context
    return build_coach_user_turn(coach)


def chatgpt_open_url(context: ChatGptVoiceContext | BrevetCoachContext | None = None) -> str:
    """Open ChatGPT with the full coach pack prefilled via `q`."""
    if context is None:
        # Still open with a minimal coach identity so there is a single professor.
        prompt = build_coach_user_turn(BrevetCoachContext(grade_label="3e"))
        return f"{CHATGPT_BASE_URL}?q={quote(prompt)}"
    prompt = build_context_prompt(context).strip()
    if not prompt:
        return CHATGPT_BASE_URL
    return f"{CHATGPT_BASE_URL}?q={quote(prompt)}"


def context_from_priorities(
    *,
    display_name: str = "",
    objective: str = "",
    subject_label: str = "",
    skill_or_chapter: str = "",
) -> ChatGptVoiceContext:
    coach = coach_context_from_home(
        display_name=display_name,
        objective=objective,
        subject_label=subject_label,
        chapter_label=skill_or_chapter,
    )
    return ChatGptVoiceContext(
        display_name=display_name,
        objective=objective,
        subject_label=subject_label,
        chapter_label=skill_or_chapter,
        topic_hint=skill_or_chapter,
        coach=coach,
    )


def context_from_snapshot(snapshot: object, **kwargs: object) -> ChatGptVoiceContext:
    """Build rich coach context from a StudentDashboardSnapshot-like object."""
    home = getattr(snapshot, "context", snapshot)
    coach = coach_context_from_home(
        display_name=str(getattr(home, "display_name", "") or ""),
        objective=str(getattr(home, "objective", "") or ""),
        fragile=tuple(getattr(home, "fragile_skills", ()) or ()),
        strong=tuple(getattr(home, "strong_skills", ()) or ()),
        mastery=tuple(getattr(home, "mastery", ()) or ()),
        revision_priorities=tuple(getattr(home, "revision_priorities", ()) or ()),
        recent_score=getattr(home, "recent_score", None),
        success_rate=getattr(home, "success_rate", None),
        subject_label=str(kwargs.get("subject_label") or ""),
        chapter_label=str(kwargs.get("chapter_label") or ""),
        exercise_statement=str(kwargs.get("exercise_statement") or ""),
        notion_reminder=str(kwargs.get("notion_reminder") or ""),
        hint_text=str(kwargs.get("hint_text") or ""),
        student_question=str(kwargs.get("student_question") or ""),
    )
    return ChatGptVoiceContext(
        display_name=coach.display_name,
        grade_label=coach.grade_label,
        subject_label=coach.subject_label,
        chapter_label=coach.chapter_label,
        objective=coach.weekly_objective,
        coach=coach,
    )


__all__ = [
    "CHATGPT_BASE_URL",
    "COACH_NAME",
    "SCHOOL_FRAME_MESSAGE",
    "VOICE_HINT",
    "BrevetCoachContext",
    "ChatGptVoiceContext",
    "build_coach_system_briefing",
    "build_context_prompt",
    "chatgpt_open_url",
    "context_from_priorities",
    "context_from_snapshot",
]
