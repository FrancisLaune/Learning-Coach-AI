"""School-secure voice pipeline: STT → filter → Professor AI → TTS (LCAI-0023)."""

from __future__ import annotations

from dataclasses import dataclass

from domain.virtual_teacher.models import AITeacherResponse, ConversationRequest, TTSResult
from services.professor_ai.banner import BannerPresenceState
from services.school_safety import SafetyAction, SafetyChannel, SchoolSafetyFilter, get_school_safety_filter
from services.virtual_teacher.ai_teacher_service import AITeacherService
from services.virtual_teacher.authorization import VirtualTeacherAccessError
from services.virtual_teacher.stt_service import STTService

PRESENCE_STATE_KEY = "professor_ai_presence"


@dataclass(frozen=True, slots=True)
class VoiceTurnResult:
    transcript: str
    response: AITeacherResponse | None
    audio: TTSResult | None
    blocked: bool
    block_category: str | None
    safety_message: str | None
    presence: BannerPresenceState


class SchoolVoicePipeline:
    """Turn-based secure voice interaction for minors."""

    def __init__(
        self,
        *,
        teacher: AITeacherService,
        stt: STTService,
        safety: SchoolSafetyFilter | None = None,
    ) -> None:
        self.teacher = teacher
        self.stt = stt
        self.safety = safety or get_school_safety_filter()

    def process_turn(
        self,
        *,
        user: dict,
        request: ConversationRequest,
        student_learner_id: int | None,
        audio: bytes,
        mime_type: str,
        voice_id: str,
        audio_enabled: bool = True,
    ) -> VoiceTurnResult:
        if not audio:
            raise VirtualTeacherAccessError("STT_EMPTY")
        try:
            transcript = self.stt.transcribe(audio, mime_type=mime_type, language="fr").strip()
        except Exception as exc:
            message = str(exc).casefold()
            if "invalid_api_key" in message or "incorrect api key" in message or "401" in message:
                raise VirtualTeacherAccessError("OPENAI_KEY_INVALID") from exc
            raise VirtualTeacherAccessError("STT_UNAVAILABLE") from exc
        if not transcript:
            raise VirtualTeacherAccessError("STT_EMPTY")

        filtered = self.safety.filter_text(transcript, channel=SafetyChannel.STT)
        if filtered.action is SafetyAction.BLOCK:
            audio_out = self._safe_tts(
                user=user,
                learner_id=request.learner_id,
                student_learner_id=student_learner_id,
                actor_type=request.actor_type,
                actor_ref=request.actor_ref,
                text=filtered.text,
                voice_id=voice_id,
                audio_enabled=audio_enabled,
            )
            return VoiceTurnResult(
                transcript=transcript,
                response=None,
                audio=audio_out,
                blocked=True,
                block_category=filtered.category.value,
                safety_message=filtered.text,
                presence=BannerPresenceState.SPEAKING if audio_out else BannerPresenceState.IDLE,
            )

        voice_request = ConversationRequest(
            learner_id=request.learner_id,
            actor_type=request.actor_type,
            actor_ref=request.actor_ref,
            session_id=request.session_id,
            user_message=transcript,
            context=request.context,
            quick_action="voice",
        )
        _, response = self.teacher.answer(
            user=user,
            request=voice_request,
            student_learner_id=student_learner_id,
        )
        audio_out = self._safe_tts(
            user=user,
            learner_id=request.learner_id,
            student_learner_id=student_learner_id,
            actor_type=request.actor_type,
            actor_ref=request.actor_ref,
            text=response.message,
            voice_id=voice_id,
            audio_enabled=audio_enabled and response.audio_allowed,
        )
        return VoiceTurnResult(
            transcript=transcript,
            response=response,
            audio=audio_out,
            blocked=False,
            block_category=None,
            safety_message=None,
            presence=BannerPresenceState.SPEAKING if audio_out else BannerPresenceState.IDLE,
        )

    def _safe_tts(
        self,
        *,
        user: dict,
        learner_id: int,
        student_learner_id: int | None,
        actor_type: str,
        actor_ref: str,
        text: str,
        voice_id: str,
        audio_enabled: bool,
    ) -> TTSResult | None:
        if not audio_enabled:
            return None
        try:
            return self.teacher.synthesize_audio(
                user=user,
                learner_id=learner_id,
                student_learner_id=student_learner_id,
                actor_type=actor_type,
                actor_ref=actor_ref,
                text=text,
                voice_id=voice_id,
            )
        except VirtualTeacherAccessError as exc:
            if str(exc) in {"OPENAI_KEY_INVALID", "AUDIO_DISABLED", "SAFETY_BLOCKED"}:
                raise
            return None
