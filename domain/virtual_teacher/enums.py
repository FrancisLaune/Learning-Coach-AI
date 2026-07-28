from enum import StrEnum


class TeacherProfile(StrEnum):
    FEMALE_01 = "TEACHER_FEMALE_01"
    MALE_01 = "TEACHER_MALE_01"


class VoiceId(StrEnum):
    WARM_FEMALE = "warm_female"
    WARM_MALE = "warm_male"


class TeacherTone(StrEnum):
    CALM = "calm"
    ENCOURAGING = "encouraging"
    ACADEMIC = "academic"


class ResponseLength(StrEnum):
    SHORT = "short"
    NORMAL = "normal"
    DETAILED = "detailed"


class ResponseType(StrEnum):
    HINT = "HINT"
    EXPLANATION = "EXPLANATION"
    EXAMPLE = "EXAMPLE"
    REDIRECTION = "REDIRECTION"
    SAFETY = "SAFETY"


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class GuardrailAction(StrEnum):
    ALLOW = "ALLOW"
    REWRITE = "REWRITE"
    BLOCK = "BLOCK"
