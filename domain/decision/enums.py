"""Decision-domain enumerations."""

from enum import IntEnum, StrEnum


class ObjectiveKind(StrEnum):
    REVISION = "revision"
    CATCH_UP = "catch_up"
    CONSOLIDATION = "consolidation"
    PREPARATION_NEXT_GRADE = "preparation_next_grade"
    PREPARATION_BREVET = "preparation_brevet"
    PREPARATION_BAC = "preparation_bac"
    HOMEWORK = "homework"
    EXAM = "exam"
    LONG_TERM_MASTERY = "long_term_mastery"


class PedagogicalStrategy(StrEnum):
    SPACED_REVISION = "spaced_revision"
    INTENSIVE_REVISION = "intensive_revision"
    EXAM_PREPARATION = "exam_preparation"
    FOUNDATION_REINFORCEMENT = "foundation_reinforcement"
    CATCH_UP = "catch_up"
    TRANSITION_PREPARATION = "transition_preparation"
    BALANCED_LEARNING = "balanced_learning"


class PriorityBand(IntEnum):
    BLOCKING_PREREQUISITE = 1
    FRAGILE_SKILL = 2
    PERIODIC_REVISION = 3
    NEW_SKILL = 4


class ActivityKind(StrEnum):
    REMEDIATION = "remediation"
    REVISION = "revision"
    CONSOLIDATION = "consolidation"
    LEARNING = "learning"
    EXAM_PRACTICE = "exam_practice"


class DecisionMode(StrEnum):
    DISABLED = "disabled"
    SHADOW = "shadow"
    ASSISTED = "assisted"
    ACTIVE = "active"
