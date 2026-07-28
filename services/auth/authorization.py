"""Authentication authorization helpers."""

from __future__ import annotations

from core.config import get_v2_database_path
from services.auth.roles import AuthRole, is_known_auth_role, normalize_auth_role


def parent_owns_learner(parent_user_id: int, learner_external_ref: str) -> bool:
    from infrastructure.repositories.unified_experience import DuckDBUnifiedExperienceRepository

    repository = DuckDBUnifiedExperienceRepository(get_v2_database_path())
    try:
        learner_id = repository.learner_for_external_ref(learner_external_ref.strip())
    except Exception:
        return True
    if learner_id is None:
        return True
    return repository.parent_authorized(str(parent_user_id), int(learner_id))


def require_parent_role(user: dict | None) -> dict:
    if user is None or normalize_auth_role(user.get("role")) is not AuthRole.PARENT:
        raise PermissionError("PARENT_ACCESS_DENIED")
    return user


def require_student_role(user: dict | None) -> dict:
    if user is None or normalize_auth_role(user.get("role")) is not AuthRole.STUDENT:
        raise PermissionError("STUDENT_ACCESS_DENIED")
    return user


def require_known_auth_role(user: dict | None) -> dict:
    if user is None or not is_known_auth_role(user.get("role")):
        raise PermissionError("AUTH_ROLE_DENIED")
    return user
