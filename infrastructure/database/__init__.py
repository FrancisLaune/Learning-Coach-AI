"""DuckDB V1 adapters preserved during the progressive migration."""

from infrastructure.database.repositories import (
    ExamRepository,
    PracticeRepository,
    ProgressRepository,
    UserRepository,
)

__all__ = ["ExamRepository", "PracticeRepository", "ProgressRepository", "UserRepository"]
