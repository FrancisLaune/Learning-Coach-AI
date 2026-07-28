"""LLM abstraction for the Virtual Teacher."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from domain.virtual_teacher.enums import ResponseType
from domain.virtual_teacher.models import AITeacherResponse, PedagogicalContext


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


class LLMService(Protocol):
    def generate(self, *, system_prompt: str, messages: tuple[LLMMessage, ...]) -> AITeacherResponse: ...


class DeterministicLLMService:
    """Test-friendly provider returning predictable pedagogical answers."""

    def generate(self, *, system_prompt: str, messages: tuple[LLMMessage, ...]) -> AITeacherResponse:
        last_user = next((item.content for item in reversed(messages) if item.role == "user"), "")
        lowered = last_user.lower()
        if "indice" in lowered or "aide" in lowered:
            response_type = ResponseType.HINT.value
            message = (
                "Commence par identifier ce que l'énoncé te demande exactement, "
                "puis vérifie ta première étape de calcul."
            )
        elif "exemple" in lowered:
            response_type = ResponseType.EXAMPLE.value
            message = "Voici un exemple proche : si tu dois additionner deux fractions, mets-les d'abord au même dénominateur."
        else:
            response_type = ResponseType.EXPLANATION.value
            message = (
                "Je vais t'expliquer calmement la notion. "
                "L'important est de comprendre la méthode avant de chercher le résultat final."
            )
        return AITeacherResponse(
            message=message,
            response_type=response_type,
            suggested_actions=("Donne-moi un indice", "Explique plus simplement"),
            confidence=0.82,
            audio_allowed=True,
        )


class OpenAILLMService:
    """Optional OpenAI-backed provider."""

    def __init__(self, *, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, *, system_prompt: str, messages: tuple[LLMMessage, ...]) -> AITeacherResponse:
        try:
            import urllib.request

            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}]
                + [{"role": item.role, "content": item.content} for item in messages],
                "temperature": 0.4,
            }
            request = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"].strip()
        except Exception:
            return DeterministicLLMService().generate(system_prompt=system_prompt, messages=messages)
        return _response_from_text(text)


def build_llm_service() -> LLMService:
    from infrastructure.config.openai_settings import load_openai_api_key, load_openai_model

    api_key = load_openai_api_key()
    if api_key:
        return OpenAILLMService(api_key=api_key, model=load_openai_model() or "gpt-4o-mini")
    return DeterministicLLMService()


def build_prompt(system_template: str, *, context: PedagogicalContext, preferences: dict[str, str]) -> str:
    pedagogical_context = "\n".join(
        filter(
            None,
            [
                f"Learner: {context.learner_display_name}",
                f"Grade: {context.grade_label or 'unknown'}",
                f"Subject: {context.subject_label or 'general'}",
                f"Skill: {context.skill_label or 'general'}",
                f"Exercise: {context.exercise_statement or 'none'}",
                f"Student attempt: {context.learner_answer or 'none'}",
                f"Session summary: {context.session_summary or 'none'}",
            ],
        )
    )
    return system_template.format(
        grade=context.grade_label or "inconnue",
        subject=context.subject_label or "général",
        teacher_name=preferences.get("teacher_name", "Professeur"),
        tone=preferences.get("tone", "encouraging"),
        response_length=preferences.get("response_length", "normal"),
        help_level=preferences.get("help_level", "2"),
        pedagogical_context=pedagogical_context,
    )


def _response_from_text(text: str) -> AITeacherResponse:
    response_type = ResponseType.EXPLANATION.value
    lowered = text.lower()
    if "indice" in lowered:
        response_type = ResponseType.HINT.value
    elif "exemple" in lowered:
        response_type = ResponseType.EXAMPLE.value
    elif "hors sujet" in lowered or "revenons" in lowered:
        response_type = ResponseType.REDIRECTION.value
    if re.search(r"\bd[eé]tresse\b|\badulte de confiance\b", lowered):
        response_type = ResponseType.SAFETY.value
    return AITeacherResponse(
        message=text,
        response_type=response_type,
        suggested_actions=("Donne-moi un indice", "Explique plus simplement"),
        confidence=0.75,
        audio_allowed=True,
    )
