"""Repository namespace retained for future non-database adapters."""

from infrastructure.database import ExamRepository, PracticeRepository, ProgressRepository, UserRepository

__all__ = ["ExamRepository", "PracticeRepository", "ProgressRepository", "UserRepository"]
