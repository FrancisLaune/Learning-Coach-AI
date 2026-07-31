"""Main Virtual Teacher application service."""

from __future__ import annotations

from typing import Protocol

from domain.virtual_teacher.enums import MessageRole, SessionStatus
from domain.virtual_teacher.models import (
    AITeacherResponse,
    ConversationRequest,
    PedagogicalContext,
    TTSResult,
    VirtualTeacherMessage,
    VirtualTeacherSession,
    VirtualTeacherSummary,
)
from services.virtual_teacher.ai_conversation_orchestrator import AIConversationOrchestrator
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.authorization import (
    VirtualTeacherAccessError,
    authorize_parent_access,
    authorize_student_access,
    require_resolved_learner_id,
)
from services.virtual_teacher.tts_service import TTSService

MAX_USER_MESSAGE_LENGTH = 2000


class VirtualTeacherRepositoryProtocol(Protocol):
    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...

    def create_session(
        self,
        *,
        learner_id: int,
        actor_type: str,
        actor_ref: str,
        subject_id: int | None = None,
        skill_id: int | None = None,
        exercise_ref: str | None = None,
    ) -> VirtualTeacherSession: ...

    def get_session(self, session_id: int) -> VirtualTeacherSession | None: ...

    def complete_session(self, session_id: int) -> None: ...

    def append_message(
        self,
        *,
        session_id: int,
        message_role: str,
        content: str,
        response_type: str | None = None,
    ) -> VirtualTeacherMessage: ...

    def list_messages(self, session_id: int) -> tuple[VirtualTeacherMessage, ...]: ...

    def save_summary(
        self,
        *,
        session_id: int,
        skills_worked: tuple[str, ...],
        difficulties: tuple[str, ...],
        successful_elements: tuple[str, ...],
        next_action: str | None,
    ) -> VirtualTeacherSummary: ...

    def record_event(
        self,
        *,
        learner_id: int,
        event_type: str,
        session_id: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...


class AITeacherService:
    def __init__(
        self,
        repository: VirtualTeacherRepositoryProtocol,
        preferences_service: AITeacherPreferencesService,
        orchestrator: AIConversationOrchestrator,
        tts: TTSService,
    ) -> None:
        self.repository = repository
        self.preferences_service = preferences_service
        self.orchestrator = orchestrator
        self.tts = tts

    def start_session(
        self,
        *,
        user: dict,
        learner_id: int,
        student_learner_id: int | None,
        actor_type: str,
        actor_ref: str,
        context: PedagogicalContext,
        subject_id: int | None = None,
        skill_id: int | None = None,
        exercise_ref: str | None = None,
    ) -> VirtualTeacherSession:
        learner_id = require_resolved_learner_id(learner_id)
        preferences = self.preferences_service.get_preferences(learner_id)
        self._authorize_usage(
            user=user,
            learner_id=learner_id,
            student_learner_id=student_learner_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            feature_enabled=preferences.feature_enabled,
        )
        session = self.repository.create_session(
            learner_id=learner_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            subject_id=subject_id,
            skill_id=skill_id,
            exercise_ref=exercise_ref,
        )
        self.repository.record_event(
            learner_id=learner_id,
            session_id=session.id,
            event_type="session_started",
            metadata={"subject_id": subject_id, "skill_id": skill_id},
        )
        return session

    def answer(
        self,
        *,
        user: dict,
        request: ConversationRequest,
        student_learner_id: int | None,
    ) -> tuple[VirtualTeacherSession, AITeacherResponse]:
        learner_id = require_resolved_learner_id(request.learner_id)
        preferences = self.preferences_service.get_preferences(learner_id)
        self._authorize_usage(
            user=user,
            learner_id=learner_id,
            student_learner_id=student_learner_id,
            actor_type=request.actor_type,
            actor_ref=request.actor_ref,
            feature_enabled=preferences.feature_enabled,
        )
        session = self._required_session(request.session_id, learner_id)
        message = request.user_message.strip()
        if not message:
            raise VirtualTeacherAccessError("EMPTY_MESSAGE")
        if len(message) > MAX_USER_MESSAGE_LENGTH:
            raise VirtualTeacherAccessError("MESSAGE_TOO_LONG")
        history = self.orchestrator.history_from_messages(self.repository.list_messages(session.id))
        self.repository.append_message(
            session_id=session.id,
            message_role=MessageRole.USER.value,
            content=message,
        )
        response = self.orchestrator.generate_answer(
            request=request,
            preferences=preferences,
            history=history,
        )
        self.repository.append_message(
            session_id=session.id,
            message_role=MessageRole.ASSISTANT.value,
            content=response.message,
            response_type=response.response_type,
        )
        self.repository.record_event(
            learner_id=learner_id,
            session_id=session.id,
            event_type="answer_generated",
            metadata={"response_type": response.response_type},
        )
        return session, response

    def end_session(
        self,
        *,
        user: dict,
        session_id: int,
        learner_id: int,
        student_learner_id: int | None,
        actor_type: str,
        actor_ref: str,
        context: PedagogicalContext,
        last_user_message: str,
        last_response: AITeacherResponse,
    ) -> VirtualTeacherSummary:
        learner_id = require_resolved_learner_id(learner_id)
        preferences = self.preferences_service.get_preferences(learner_id)
        self._authorize_usage(
            user=user,
            learner_id=learner_id,
            student_learner_id=student_learner_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            feature_enabled=preferences.feature_enabled,
        )
        session = self._required_session(session_id, learner_id)
        skills, difficulties, successes, next_action = self.orchestrator.build_session_summary(
            subject_label=context.subject_label,
            user_message=last_user_message,
            response=last_response,
        )
        self.repository.complete_session(session.id)
        summary = self.repository.save_summary(
            session_id=session.id,
            skills_worked=skills,
            difficulties=difficulties,
            successful_elements=successes,
            next_action=next_action,
        )
        self.repository.record_event(
            learner_id=learner_id,
            session_id=session.id,
            event_type="session_completed",
            metadata={"next_action": next_action},
        )
        return summary

    def synthesize_audio(
        self,
        *,
        user: dict,
        learner_id: int,
        student_learner_id: int | None,
        actor_type: str,
        actor_ref: str,
        text: str,
        voice_id: str,
    ) -> TTSResult:
        learner_id = require_resolved_learner_id(learner_id)
        preferences = self.preferences_service.get_preferences(learner_id)
        self._authorize_usage(
            user=user,
            learner_id=learner_id,
            student_learner_id=student_learner_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            feature_enabled=preferences.feature_enabled,
        )
        if not preferences.audio_enabled:
            raise VirtualTeacherAccessError("AUDIO_DISABLED")
        from services.school_safety import SafetyAction, SafetyChannel, get_school_safety_filter

        filtered = get_school_safety_filter().filter_text(text, channel=SafetyChannel.ASSISTANT)
        if filtered.action is SafetyAction.BLOCK:
            raise VirtualTeacherAccessError("SAFETY_BLOCKED")
        try:
            result = self.tts.synthesize(text=filtered.text, voice_id=voice_id)
        except Exception as exc:
            raise VirtualTeacherAccessError("TTS_UNAVAILABLE") from exc
        self.repository.record_event(
            learner_id=learner_id,
            event_type="tts_generated",
            metadata={"voice_id": voice_id},
        )
        return result

    def list_session_messages(
        self,
        *,
        user: dict,
        session_id: int,
        learner_id: int,
        student_learner_id: int | None,
        actor_type: str,
        actor_ref: str,
    ) -> tuple[VirtualTeacherMessage, ...]:
        learner_id = require_resolved_learner_id(learner_id)
        preferences = self.preferences_service.get_preferences(learner_id)
        self._authorize_usage(
            user=user,
            learner_id=learner_id,
            student_learner_id=student_learner_id,
            actor_type=actor_type,
            actor_ref=actor_ref,
            feature_enabled=preferences.feature_enabled,
        )
        session = self._required_session(session_id, learner_id)
        return self.repository.list_messages(session.id)

    def _required_session(self, session_id: int | None, learner_id: int) -> VirtualTeacherSession:
        if session_id is None:
            raise VirtualTeacherAccessError("SESSION_REQUIRED")
        session = self.repository.get_session(session_id)
        if session is None or session.learner_id != learner_id:
            raise VirtualTeacherAccessError("SESSION_ACCESS_DENIED")
        if session.status != SessionStatus.ACTIVE.value:
            raise VirtualTeacherAccessError("SESSION_NOT_ACTIVE")
        return session

    def _authorize_usage(
        self,
        *,
        user: dict,
        learner_id: int,
        student_learner_id: int | None,
        actor_type: str,
        actor_ref: str,
        feature_enabled: bool,
    ) -> None:
        if actor_type == "STUDENT":
            authorize_student_access(
                user=user,
                learner_id=learner_id,
                student_learner_id=student_learner_id,
                feature_enabled=feature_enabled,
            )
            return
        if actor_type == "PARENT":
            authorize_parent_access(
                user=user,
                parent_ref=actor_ref,
                learner_id=learner_id,
                parent_authorized=self.repository.parent_authorized(actor_ref, learner_id),
            )
            return
        raise VirtualTeacherAccessError("UNSUPPORTED_ACTOR")
