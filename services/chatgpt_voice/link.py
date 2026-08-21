"""ChatGPT Voice — simple external link helpers (LCAI-0030-E)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

CHATGPT_BASE_URL = "https://chatgpt.com/"
SCHOOL_FRAME_MESSAGE = (
    "Cadre scolaire : pose uniquement des questions de cours (leçon, exercice, méthode). Pas de sujet hors programme."
)
VOICE_HINT = "Dans ChatGPT, tu peux utiliser le mode vocal (micro) pour parler comme avec un professeur."


@dataclass(frozen=True, slots=True)
class ChatGptVoiceContext:
    display_name: str = ""
    grade_label: str = ""
    subject_label: str = ""
    chapter_label: str = ""
    objective: str = ""
    topic_hint: str = ""


def build_context_prompt(context: ChatGptVoiceContext) -> str:
    """Build a short French school prompt the student can paste or prefill."""
    lines = [
        "Tu es un tuteur scolaire bienveillant pour un élève français.",
        "Réponds clairement, étape par étape, sans donner seulement la réponse finale si l'élève travaille un exercice.",
        "Reste sur le programme scolaire demandé.",
    ]
    profile: list[str] = []
    if context.display_name.strip():
        profile.append(f"Prénom : {context.display_name.strip()}")
    if context.grade_label.strip():
        profile.append(f"Classe : {context.grade_label.strip()}")
    if context.subject_label.strip():
        profile.append(f"Matière : {context.subject_label.strip()}")
    if context.chapter_label.strip():
        profile.append(f"Chapitre : {context.chapter_label.strip()}")
    if context.objective.strip():
        profile.append(f"Objectif : {context.objective.strip()}")
    if context.topic_hint.strip():
        profile.append(f"Sujet : {context.topic_hint.strip()}")
    if profile:
        lines.append("Contexte élève :")
        lines.extend(f"- {item}" for item in profile)
    lines.append("Ma question : ")
    return "\n".join(lines)


def chatgpt_open_url(context: ChatGptVoiceContext | None = None) -> str:
    """Open ChatGPT with an optional prefilled prompt via `q` query param."""
    if context is None:
        return CHATGPT_BASE_URL
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
    return ChatGptVoiceContext(
        display_name=display_name,
        objective=objective,
        subject_label=subject_label,
        chapter_label=skill_or_chapter,
        topic_hint=skill_or_chapter,
    )
