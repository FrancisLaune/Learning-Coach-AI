"""Repository namespace retained for future non-database adapters."""

from infrastructure.database import ExamRepository, PracticeRepository, ProgressRepository, UserRepository
from infrastructure.repositories.v2 import (
    AttemptRepositoryV2,
    ContentRepositoryV2,
    DecisionRepositoryV2,
    LearnerRepositoryV2,
    MasteryRepositoryV2,
    ObjectiveRepositoryV2,
    RecommendationRepositoryV2,
    ReferenceRepositoryV2,
    SessionRepositoryV2,
)

__all__ = [
    "AttemptRepositoryV2",
    "ContentRepositoryV2",
    "DecisionRepositoryV2",
    "ExamRepository",
    "LearnerRepositoryV2",
    "MasteryRepositoryV2",
    "ObjectiveRepositoryV2",
    "PracticeRepository",
    "ProgressRepository",
    "RecommendationRepositoryV2",
    "ReferenceRepositoryV2",
    "SessionRepositoryV2",
    "UserRepository",
]
