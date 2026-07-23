from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class OnboardingEvent:
    event_type: str
    learner_id: int | None
    correlation_id: str
    payload: dict
    occurred_at: datetime


EVENT_TYPES = (
    "LearnerProfileCreated",
    "OnboardingStarted",
    "OnboardingCompleted",
    "OnboardingValidationFailed",
    "LearnerJourneyCreated",
    "LearnerJourneyChanged",
    "GoalChanged",
    "TargetGradeChanged",
    "SubjectPriorityChanged",
    "AvailabilityChanged",
    "CandidateSetBuilt",
    "CandidateExcluded",
    "NoCompatibleContentDetected",
    "PersonalizedSessionGenerated",
    "PersonalizedSessionGenerationFailed",
)
