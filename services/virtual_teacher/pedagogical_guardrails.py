"""Pedagogical guardrails for Virtual Teacher requests and responses."""

from __future__ import annotations

import re

from domain.virtual_teacher.enums import GuardrailAction, ResponseType
from domain.virtual_teacher.models import AITeacherResponse

_BLOCKED_PATTERNS = (
    r"\bmot de passe\b",
    r"\bpassword\b",
    r"\bsexe\b",
    r"\bnude\b",
    r"\bnu\b",
    r"\bpoignard\b",
    r"\barme\b",
    r"\btue\b",
)
_DISTRESS_PATTERNS = (
    r"\bje veux mourir\b",
    r"\bsuicide\b",
    r"\bme faire du mal\b",
    r"\bj['']ai peur chez moi\b",
)
_CHEATING_PATTERNS = (
    r"\bdonne(?:-|\s)?moi la r[eé]ponse\b",
    r"\br[eé]ponse finale\b",
    r"\bfini(?:s|-)?(?:\s|-)?le(?:\s|-)?devoir\b",
)
_INJECTION_PATTERNS = (
    r"\bignore(?:z|r)?\s+(?:les\s+)?(?:instructions|consignes)\b",
    r"\bsystem prompt\b",
    r"\bprompt syst[eè]me\b",
    r"\bcontourn(?:e|er)\s+(?:les\s+)?r[eè]gles\b",
    r"\bjoue(?:z|-)?\s+(?:un\s+)?autre r[oô]le\b",
)


class PedagogicalGuardrails:
    def classify_request(self, message: str, *, from_exercise: bool) -> tuple[str, GuardrailAction]:
        lowered = message.strip().lower()
        if not lowered:
            return "EMPTY_MESSAGE", GuardrailAction.BLOCK
        for pattern in _DISTRESS_PATTERNS:
            if re.search(pattern, lowered):
                return "DISTRESS", GuardrailAction.BLOCK
        for pattern in _BLOCKED_PATTERNS:
            if re.search(pattern, lowered):
                return "UNSAFE_CONTENT", GuardrailAction.BLOCK
        for pattern in _INJECTION_PATTERNS:
            if re.search(pattern, lowered):
                return "PROMPT_INJECTION", GuardrailAction.BLOCK
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

    def validate_response(self, response: AITeacherResponse, *, from_exercise: bool) -> tuple[GuardrailAction, AITeacherResponse]:
        lowered = response.message.lower()
        for pattern in _BLOCKED_PATTERNS:
            if re.search(pattern, lowered):
                return GuardrailAction.BLOCK, self._safety_response()
        if from_exercise and response.response_type == ResponseType.EXPLANATION.value and re.search(
            r"\br[eé]ponse(?:\s|:|=)\s*[-+]?\d", lowered
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

    @staticmethod
    def _safety_response() -> AITeacherResponse:
        return AITeacherResponse(
            message=(
                "Je ne peux pas répondre à ce type de demande. "
                "Parle-en à un adulte de confiance si tu te sens en difficulté."
            ),
            response_type=ResponseType.SAFETY.value,
            suggested_actions=("Revenir à ma leçon",),
            confidence=1.0,
            audio_allowed=False,
        )

    def safety_response_for_distress(self) -> AITeacherResponse:
        return AITeacherResponse(
            message=(
                "Je suis vraiment désolé que tu te sentes ainsi. "
                "Ce n'est pas quelque chose que tu dois garder pour toi : parle-en tout de suite "
                "à un adulte de confiance, à tes parents ou à un enseignant."
            ),
            response_type=ResponseType.SAFETY.value,
            suggested_actions=("Parler à un adulte",),
            confidence=1.0,
            audio_allowed=False,
        )
