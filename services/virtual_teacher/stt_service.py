"""Speech-to-text adapters for school voice mode (LCAI-0023)."""

from __future__ import annotations

import io
from typing import Protocol


class STTService(Protocol):
    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav", language: str = "fr") -> str: ...


class ConsoleSTTService:
    """Deterministic STT for tests/CI — accepts UTF-8 transcript fixtures."""

    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav", language: str = "fr") -> str:
        _ = language
        if not audio:
            return ""
        if mime_type.startswith("text/") or _looks_like_text(audio):
            text = audio.decode("utf-8", errors="ignore").strip()
            if text.startswith("[stt]"):
                return text[5:].strip()
            return text
        return ""


class DisabledSTTService:
    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav", language: str = "fr") -> str:
        _ = audio, mime_type, language
        raise RuntimeError("STT_UNAVAILABLE")


class OpenAISTTService:
    """Optional Whisper transcription via the OpenAI SDK."""

    def __init__(self, *, api_key: str, model: str = "whisper-1") -> None:
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav", language: str = "fr") -> str:
        if not audio:
            return ""
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("STT_UNAVAILABLE") from exc
        extension = _extension_for_mime(mime_type)
        buffer = io.BytesIO(audio)
        buffer.name = f"voice.{extension}"
        client = OpenAI(api_key=self.api_key)
        result = client.audio.transcriptions.create(
            model=self.model,
            file=buffer,
            language=language,
        )
        return str(getattr(result, "text", "") or "").strip()


def build_stt_service(*, prefer_openai: bool = True) -> STTService:
    if prefer_openai:
        try:
            from infrastructure.config.openai_settings import load_openai_api_key

            api_key = load_openai_api_key()
        except Exception:
            api_key = None
        if api_key:
            model = _env_model("OPENAI_STT_MODEL", "whisper-1")
            return OpenAISTTService(api_key=api_key, model=model)
    return ConsoleSTTService()


def _env_model(name: str, default: str) -> str:
    import os

    return (os.getenv(name) or default).strip() or default


def _extension_for_mime(mime_type: str) -> str:
    token = (mime_type or "").casefold()
    if "mpeg" in token or "mp3" in token:
        return "mp3"
    if "webm" in token:
        return "webm"
    if "ogg" in token:
        return "ogg"
    if "mp4" in token or "m4a" in token:
        return "m4a"
    return "wav"


def _looks_like_text(payload: bytes) -> bool:
    sample = payload[: min(len(payload), 256)]
    if not sample:
        return False
    printable = sum(32 <= byte < 127 or byte in (9, 10, 13) for byte in sample)
    return printable / len(sample) >= 0.9
