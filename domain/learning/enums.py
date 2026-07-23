"""Stable enumerations used by the longitudinal learning domain."""

from enum import StrEnum


class LearningPhase(StrEnum):
    DIAGNOSTIC = "diagnostic"
    REMEDIATION = "remediation"
    PRE_YEAR_PREPARATION = "pre_year_preparation"
    CURRENT_LEARNING = "current_learning"
    CONSOLIDATION = "consolidation"
    PRACTICE = "practice"
    SPACED_REVISION = "spaced_revision"
    ASSESSMENT_PREPARATION = "assessment_preparation"
    EXAM_PREPARATION = "exam_preparation"
    TRANSITION_PREPARATION = "transition_preparation"


class MasteryLevel(StrEnum):
    NOT_STARTED = "not_started"
    EMERGING = "emerging"
    DEVELOPING = "developing"
    PROFICIENT = "proficient"
    MASTERED = "mastered"


class Trend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class PrerequisiteCondition(StrEnum):
    ACQUIRED = "acquired"
    FRAGILE = "fragile"
    NOT_ACQUIRED = "not_acquired"
    NOT_EVALUATED = "not_evaluated"
