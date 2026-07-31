"""LCAI-0023 — school-secure voice pipeline (STT → filter → answer → TTS)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from domain.virtual_teacher.enums import ResponseType
from domain.virtual_teacher.models import (
    AITeacherResponse,
    ConversationRequest,
    PedagogicalContext,
    TTSResult,
)
from services.professor_ai.banner import BannerPresenceState
from services.school_safety import SchoolSafetyFilter
from services.virtual_teacher.authorization import VirtualTeacherAccessError
from services.virtual_teacher.stt_service import ConsoleSTTService
from services.virtual_teacher.tts_service import ConsoleTTSService
from services.virtual_teacher.voice_pipeline import SchoolVoicePipeline


class _FakeSTT:
    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav", language: str = "fr") -> str:
        _ = audio, mime_type, language
        return self.text


def _request(message: str = "") -> ConversationRequest:
    return ConversationRequest(
        learner_id=7,
        actor_type="STUDENT",
        actor_ref="10",
        session_id=3,
        user_message=message,
        context=PedagogicalContext(learner_id=7, learner_display_name="Noa"),
    )


def test_console_stt_reads_utf8_fixture() -> None:
    assert (
        ConsoleSTTService().transcribe(b"[stt] Comment additionner ?", mime_type="text/plain")
        == "Comment additionner ?"
    )


def test_voice_pipeline_blocks_unsafe_transcript_without_llm() -> None:
    teacher = MagicMock()
    teacher.synthesize_audio.return_value = TTSResult(b"safe", "audio/mpeg", detail="test")
    pipeline = SchoolVoicePipeline(teacher=teacher, stt=_FakeSTT("je veux mourir"), safety=SchoolSafetyFilter())
    result = pipeline.process_turn(
        user={"id": 10, "role": "STUDENT"},
        request=_request(),
        student_learner_id=7,
        audio=b"ignored",
        mime_type="audio/wav",
        voice_id="warm_female",
        audio_enabled=True,
    )
    assert result.blocked is True
    assert result.response is None
    assert result.block_category == "DISTRESS"
    teacher.answer.assert_not_called()
    teacher.synthesize_audio.assert_called_once()


def test_voice_pipeline_answers_and_synthesizes_safe_turn() -> None:
    teacher = MagicMock()
    response = AITeacherResponse(
        message="Voici une explication claire.",
        response_type=ResponseType.EXPLANATION.value,
        confidence=0.9,
        audio_allowed=True,
    )
    teacher.answer.return_value = (SimpleNamespace(id=3), response)
    teacher.synthesize_audio.return_value = TTSResult(b"\x00\x01", "audio/mpeg", detail="test")
    pipeline = SchoolVoicePipeline(
        teacher=teacher,
        stt=_FakeSTT("Explique-moi les fractions"),
        safety=SchoolSafetyFilter(),
    )
    result = pipeline.process_turn(
        user={"id": 10, "role": "STUDENT"},
        request=_request(),
        student_learner_id=7,
        audio=b"ignored",
        mime_type="audio/wav",
        voice_id="warm_female",
        audio_enabled=True,
    )
    assert result.blocked is False
    assert result.transcript == "Explique-moi les fractions"
    assert result.response is response
    assert result.audio is not None
    assert result.presence is BannerPresenceState.SPEAKING
    teacher.answer.assert_called_once()
    assert teacher.answer.call_args.kwargs["request"].user_message == "Explique-moi les fractions"


def test_voice_pipeline_empty_audio_raises() -> None:
    pipeline = SchoolVoicePipeline(teacher=MagicMock(), stt=ConsoleSTTService())
    with pytest.raises(VirtualTeacherAccessError, match="STT_EMPTY"):
        pipeline.process_turn(
            user={},
            request=_request(),
            student_learner_id=7,
            audio=b"",
            mime_type="audio/wav",
            voice_id="warm_female",
        )


def test_build_tts_defaults_to_console_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "infrastructure.config.openai_settings.load_openai_api_key",
        lambda **_: None,
    )
    from services.virtual_teacher.openai_tts import build_tts_service

    service = build_tts_service(prefer_openai=True)
    assert isinstance(service, ConsoleTTSService)
