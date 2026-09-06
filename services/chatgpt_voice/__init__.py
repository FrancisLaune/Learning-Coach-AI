"""ChatGPT Voice package — unique Coach Brevet access."""

from services.chatgpt_voice.link import (
    CHATGPT_BASE_URL,
    COACH_NAME,
    SCHOOL_FRAME_MESSAGE,
    VOICE_HINT,
    BrevetCoachContext,
    ChatGptVoiceContext,
    build_context_prompt,
    chatgpt_open_url,
    context_from_priorities,
    context_from_snapshot,
)

__all__ = [
    "CHATGPT_BASE_URL",
    "COACH_NAME",
    "SCHOOL_FRAME_MESSAGE",
    "VOICE_HINT",
    "BrevetCoachContext",
    "ChatGptVoiceContext",
    "build_context_prompt",
    "chatgpt_open_url",
    "context_from_priorities",
    "context_from_snapshot",
]
