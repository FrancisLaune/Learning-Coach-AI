"""Text-to-speech adapter for the Virtual Teacher."""

from __future__ import annotations

from typing import Protocol

from domain.virtual_teacher.models import TTSResult


class TTSService(Protocol):
    def synthesize(self, *, text: str, voice_id: str) -> TTSResult: ...

    def list_available_voices(self) -> tuple[str, ...]: ...


class ConsoleTTSService:
    """Development provider that does not call external APIs."""

    def synthesize(self, *, text: str, voice_id: str) -> TTSResult:
        payload = f"[voice={voice_id}] {text}".encode()
        return TTSResult(content=payload, mime_type="text/plain", duration_ms=None, detail="console-tts")

    def list_available_voices(self) -> tuple[str, ...]:
        return ("warm_female", "warm_male")


class DisabledTTSService:
    def synthesize(self, *, text: str, voice_id: str) -> TTSResult:
        raise RuntimeError("TTS_UNAVAILABLE")

    def list_available_voices(self) -> tuple[str, ...]:
        return ("warm_female", "warm_male")
