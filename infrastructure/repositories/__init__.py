"""Repository namespace retained for future non-database adapters."""

from infrastructure.database import ExamRepository, PracticeRepository, ProgressRepository, UserRepository
from infrastructure.repositories.content import (
    ContentSearchRepository,
    ContentUnitOfWork,
    ExerciseRepository,
    MediaRepository,
    ProgramRepository,
    QuestionRepository,
    SkillRepository,
    SubjectRepository,
    ValidationRepository,
    VersionRepository,
)
from infrastructure.repositories.decision import DuckDBDecisionRepository
from infrastructure.repositories.learning import DuckDBLearningRepository
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
    "ContentSearchRepository",
    "ContentUnitOfWork",
    "DecisionRepositoryV2",
    "DuckDBDecisionRepository",
    "DuckDBLearningRepository",
    "ExamRepository",
    "ExerciseRepository",
    "LearnerRepositoryV2",
    "MasteryRepositoryV2",
    "MediaRepository",
    "ObjectiveRepositoryV2",
    "PracticeRepository",
    "ProgramRepository",
    "ProgressRepository",
    "RecommendationRepositoryV2",
    "ReferenceRepositoryV2",
    "QuestionRepository",
    "SessionRepositoryV2",
    "SkillRepository",
    "SubjectRepository",
    "UserRepository",
    "ValidationRepository",
    "VersionRepository",
]
