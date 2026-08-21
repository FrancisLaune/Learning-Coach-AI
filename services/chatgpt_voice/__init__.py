"""LCAI-0030-E — ChatGPT Voice package (simple external access)."""

from services.chatgpt_voice.link import (
    CHATGPT_BASE_URL,
    SCHOOL_FRAME_MESSAGE,
    VOICE_HINT,
    ChatGptVoiceContext,
    build_context_prompt,
    chatgpt_open_url,
    context_from_priorities,
)

__all__ = [
    "CHATGPT_BASE_URL",
    "SCHOOL_FRAME_MESSAGE",
    "VOICE_HINT",
    "ChatGptVoiceContext",
    "build_context_prompt",
    "chatgpt_open_url",
    "context_from_priorities",
]
