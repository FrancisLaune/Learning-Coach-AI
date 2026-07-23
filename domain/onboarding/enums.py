from enum import StrEnum


class CreatorRole(StrEnum):
    PARENT = "parent"
    STUDENT = "student"
    ADMINISTRATOR = "administrator"


class CompatibilityStatus(StrEnum):
    ALLOWED = "allowed"
    RECOMMENDED = "recommended"
    ANTICIPATION = "anticipation"
    INCOMPATIBLE = "incompatible"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class DifficultyPreference(StrEnum):
    PROGRESSIVE = "progressive"
    STANDARD = "standard"
    CHALLENGE = "challenge"


class StudyBalance(StrEnum):
    BALANCED = "balanced"
    GAPS_FIRST = "gaps_first"
    GOAL_FIRST = "goal_first"


class ContentFormat(StrEnum):
    EXERCISE = "exercise"
    QUIZ = "quiz"
    SHEET = "sheet"
    PROBLEM = "problem"
    MIXED = "mixed"
