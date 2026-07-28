from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class VirtualTeacherPreferences:
    id: int
    learner_id: int
    teacher_profile: str
    teacher_name: str | None
    voice_id: str
    tone: str
    response_length: str
    help_level: int
    audio_enabled: bool
    feature_enabled: bool
    parent_locked: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VirtualTeacherSession:
    id: int
    learner_id: int
    actor_type: str
    actor_ref: str
    subject_id: int | None
    skill_id: int | None
    exercise_ref: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class VirtualTeacherMessage:
    id: int
    session_id: int
    message_role: str
    response_type: str | None
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class VirtualTeacherSummary:
    session_id: int
    skills_worked: tuple[str, ...]
    difficulties: tuple[str, ...]
    successful_elements: tuple[str, ...]
    next_action: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PedagogicalContext:
    learner_id: int
    learner_display_name: str
    grade_label: str | None = None
    subject_label: str | None = None
    skill_label: str | None = None
    exercise_statement: str | None = None
    learner_answer: str | None = None
    session_summary: str | None = None


@dataclass(frozen=True, slots=True)
class AITeacherResponse:
    message: str
    response_type: str
    suggested_actions: tuple[str, ...] = ()
    skill_code: str | None = None
    confidence: float = 0.0
    audio_allowed: bool = True


@dataclass(frozen=True, slots=True)
class PreferencesUpdate:
    teacher_profile: str | None = None
    teacher_name: str | None = None
    voice_id: str | None = None
    tone: str | None = None
    response_length: str | None = None
    help_level: int | None = None
    audio_enabled: bool | None = None
    feature_enabled: bool | None = None
    parent_locked: bool | None = None


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    learner_id: int
    actor_type: str
    actor_ref: str
    session_id: int | None
    user_message: str
    context: PedagogicalContext
    quick_action: str | None = None


@dataclass(frozen=True, slots=True)
class TTSResult:
    content: bytes
    mime_type: str
    duration_ms: int | None = None
    detail: str = ""


@dataclass
class PreferencesPatch:
    """Mutable patch used by the preferences service."""

    teacher_profile: str | None = None
    teacher_name: str | None = None
    voice_id: str | None = None
    tone: str | None = None
    response_length: str | None = None
    help_level: int | None = None
    audio_enabled: bool | None = None
    feature_enabled: bool | None = None
    parent_locked: bool | None = None
    fields: set[str] = field(default_factory=set)
