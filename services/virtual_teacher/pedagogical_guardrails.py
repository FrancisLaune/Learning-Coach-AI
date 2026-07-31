"""Pedagogical guardrails for Virtual Teacher — delegates minors safety to school filter."""

from __future__ import annotations

import re

from domain.virtual_teacher.enums import GuardrailAction, ResponseType
from domain.virtual_teacher.models import AITeacherResponse
from services.school_safety import SafetyAction, SafetyCategory, SafetyChannel, SchoolSafetyFilter

_CHEATING_PATTERNS = (
    r"\bdonne(?:-|\s)?moi la r[eé]ponse\b",
    r"\br[eé]ponse finale\b",
    r"\bfini(?:s|-)?(?:\s|-)?le(?:\s|-)?devoir\b",
)


class PedagogicalGuardrails:
    def __init__(self, safety: SchoolSafetyFilter | None = None) -> None:
        self.safety = safety or SchoolSafetyFilter()

    def classify_request(self, message: str, *, from_exercise: bool) -> tuple[str, GuardrailAction]:
        verdict = self.safety.classify(message, channel=SafetyChannel.USER)
        if verdict.category is SafetyCategory.EMPTY:
            return "EMPTY_MESSAGE", GuardrailAction.BLOCK
        if verdict.category is SafetyCategory.DISTRESS:
            return "DISTRESS", GuardrailAction.BLOCK
        if verdict.category is SafetyCategory.UNSAFE_CONTENT:
            return "UNSAFE_CONTENT", GuardrailAction.BLOCK
        if verdict.category is SafetyCategory.PROMPT_INJECTION:
            return "PROMPT_INJECTION", GuardrailAction.BLOCK
        lowered = message.strip().lower()
        for pattern in _CHEATING_PATTERNS:
            if re.search(pattern, lowered):
                return "DIRECT_ANSWER_REQUEST", GuardrailAction.REWRITE
        if from_exercise:
            return "EXERCISE_HELP", GuardrailAction.REWRITE
        return "GENERAL", GuardrailAction.ALLOW

    def apply_help_policy(
        self,
        *,
        category: str,
        user_message: str,
        from_exercise: bool,
    ) -> str:
        if category == "DIRECT_ANSWER_REQUEST":
            return (
                "Je peux t'aider à comprendre la démarche, pas te donner directement la réponse finale. "
                "Commence par me dire ce que tu as déjà essayé."
            )
        if category == "EXERCISE_HELP" or from_exercise:
            return (
                "Commence par reformuler l'exercice avec tes mots, puis je te donnerai un premier indice ciblé "
                "sans révéler la réponse complète."
            )
        return user_message

    def validate_response(
        self, response: AITeacherResponse, *, from_exercise: bool
    ) -> tuple[GuardrailAction, AITeacherResponse]:
        filtered = self.safety.filter_text(response.message, channel=SafetyChannel.ASSISTANT)
        if filtered.action is SafetyAction.BLOCK:
            if filtered.category is SafetyCategory.DISTRESS:
                return GuardrailAction.BLOCK, self.safety_response_for_distress()
            return GuardrailAction.BLOCK, self._safety_response(filtered.text)
        if (
            from_exercise
            and response.response_type == ResponseType.EXPLANATION.value
            and re.search(r"\br[eé]ponse(?:\s|:|=)\s*[-+]?\d", response.message.lower())
        ):
            rewritten = AITeacherResponse(
                message=(
                    "Voici un indice pour avancer : vérifie d'abord ta méthode étape par étape. "
                    "Quelle est la première opération que tu peux faire ?"
                ),
                response_type=ResponseType.HINT.value,
                suggested_actions=("Donne-moi un indice", "Explique la méthode"),
                skill_code=response.skill_code,
                confidence=response.confidence,
                audio_allowed=response.audio_allowed,
            )
            return GuardrailAction.REWRITE, rewritten
        return GuardrailAction.ALLOW, response

    def _safety_response(self, message: str | None = None) -> AITeacherResponse:
        return AITeacherResponse(
            message=message or self.safety.safe_message(SafetyCategory.UNSAFE_CONTENT),
            response_type=ResponseType.SAFETY.value,
            suggested_actions=("Revenir à ma leçon",),
            confidence=1.0,
            audio_allowed=False,
        )

    def safety_response_for_distress(self) -> AITeacherResponse:
        return AITeacherResponse(
            message=self.safety.safe_message(SafetyCategory.DISTRESS),
            response_type=ResponseType.SAFETY.value,
            suggested_actions=("Parler à un adulte",),
            confidence=1.0,
            audio_allowed=False,
        )
