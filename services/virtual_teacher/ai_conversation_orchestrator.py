"""Conversation orchestration for the Virtual Teacher."""

from __future__ import annotations

from pathlib import Path

from domain.virtual_teacher.enums import GuardrailAction, MessageRole, ResponseType
from domain.virtual_teacher.models import (
    AITeacherResponse,
    ConversationRequest,
    PedagogicalContext,
    VirtualTeacherPreferences,
)
from services.virtual_teacher.llm_service import LLMMessage, LLMService, build_prompt
from services.virtual_teacher.pedagogical_guardrails import PedagogicalGuardrails

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "virtual_teacher_system.md"


class AIConversationOrchestrator:
    def __init__(
        self,
        *,
        llm: LLMService,
        guardrails: PedagogicalGuardrails | None = None,
        prompt_path: Path = PROMPT_PATH,
    ) -> None:
        self.llm = llm
        self.guardrails = guardrails or PedagogicalGuardrails()
        self.prompt_path = prompt_path

    def build_context(self, context: PedagogicalContext, preferences: VirtualTeacherPreferences) -> dict[str, str]:
        return {
            "teacher_name": preferences.teacher_name or "Professeur",
            "tone": preferences.tone,
            "response_length": preferences.response_length,
            "help_level": str(preferences.help_level),
            "grade_label": context.grade_label or "inconnue",
            "subject_label": context.subject_label or "général",
        }

    def generate_answer(
        self,
        *,
        request: ConversationRequest,
        preferences: VirtualTeacherPreferences,
        history: tuple[tuple[str, str], ...],
    ) -> AITeacherResponse:
        from_exercise = bool(request.context.exercise_statement)
        category, action = self.guardrails.classify_request(request.user_message, from_exercise=from_exercise)
        if action is GuardrailAction.BLOCK:
            if category == "DISTRESS":
                return self.guardrails.safety_response_for_distress()
            return self.guardrails._safety_response()
        user_message = request.user_message
        if action is GuardrailAction.REWRITE:
            user_message = self.guardrails.apply_help_policy(
                category=category,
                user_message=request.user_message,
                from_exercise=from_exercise,
            )
        system_template = self.prompt_path.read_text(encoding="utf-8")
        system_prompt = build_prompt(
            system_template,
            context=request.context,
            preferences=self.build_context(request.context, preferences),
        )
        messages = tuple(
            LLMMessage(role=role.lower(), content=content)
            for role, content in history
        ) + (LLMMessage(role="user", content=user_message),)
        generated = self.llm.generate(system_prompt=system_prompt, messages=messages)
        _, validated = self.guardrails.validate_response(generated, from_exercise=from_exercise)
        if not preferences.audio_enabled:
            validated = AITeacherResponse(
                message=validated.message,
                response_type=validated.response_type,
                suggested_actions=validated.suggested_actions,
                skill_code=validated.skill_code,
                confidence=validated.confidence,
                audio_allowed=False,
            )
        return validated

    @staticmethod
    def history_from_messages(messages: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
        history: list[tuple[str, str]] = []
        for message in messages:
            role = getattr(message, "message_role", "")
            content = getattr(message, "content", "")
            if role == MessageRole.USER.value:
                history.append(("user", content))
            elif role == MessageRole.ASSISTANT.value:
                history.append(("assistant", content))
        return tuple(history)

    @staticmethod
    def build_session_summary(
        *,
        subject_label: str | None,
        user_message: str,
        response: AITeacherResponse,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str]:
        skills = (subject_label or "notion travaillée",)
        difficulties: tuple[str, ...] = ()
        if response.response_type == ResponseType.HINT.value:
            difficulties = ("besoin d'indices",)
        successes = ("participation active",) if user_message.strip() else ()
        next_action = response.suggested_actions[0] if response.suggested_actions else "Continuer la séance"
        return skills, difficulties, successes, next_action
