"""Optional productive TTS providers (LCAI-0023)."""

from __future__ import annotations

import io
import os

from domain.virtual_teacher.models import TTSResult
from services.virtual_teacher.tts_service import ConsoleTTSService, TTSService

_VOICE_MAP = {
    "warm_female": "nova",
    "warm_male": "onyx",
}


class OpenAITTSService:
    """Optional OpenAI speech synthesis."""

    def __init__(self, *, api_key: str, model: str = "tts-1") -> None:
        self.api_key = api_key
        self.model = model

    def synthesize(self, *, text: str, voice_id: str) -> TTSResult:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("TTS_UNAVAILABLE") from exc
        client = OpenAI(api_key=self.api_key)
        voice = _VOICE_MAP.get(voice_id, "nova")
        response = client.audio.speech.create(
            model=self.model,
            voice=voice,
            input=text,
        )
        payload = _speech_bytes(response)
        return TTSResult(content=payload, mime_type="audio/mpeg", duration_ms=None, detail="openai-tts")

    def list_available_voices(self) -> tuple[str, ...]:
        return ("warm_female", "warm_male")


def build_tts_service(*, prefer_openai: bool = True) -> TTSService:
    if prefer_openai:
        try:
            from infrastructure.config.openai_settings import load_openai_api_key

            api_key = load_openai_api_key()
        except Exception:
            api_key = None
        if api_key:
            model = (os.getenv("OPENAI_TTS_MODEL") or "tts-1").strip() or "tts-1"
            return OpenAITTSService(api_key=api_key, model=model)
    return ConsoleTTSService()


def _speech_bytes(response: object) -> bytes:
    if hasattr(response, "read") and callable(response.read):
        data = response.read()
        return data if isinstance(data, bytes) else bytes(data)
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    if hasattr(response, "iter_bytes"):
        buffer = io.BytesIO()
        for chunk in response.iter_bytes():
            buffer.write(chunk)
        return buffer.getvalue()
    raise RuntimeError("TTS_UNAVAILABLE")
