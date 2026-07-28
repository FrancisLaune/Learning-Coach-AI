"""Authorization helpers for the Virtual Teacher feature."""

from __future__ import annotations

from services.auth.roles import AuthRole, normalize_auth_role


class VirtualTeacherAccessError(PermissionError):
    """Raised when Virtual Teacher access is denied."""


def require_resolved_learner_id(learner_id: int | None) -> int:
    if learner_id is None:
        raise VirtualTeacherAccessError("LEARNER_ID_REQUIRED")
    return int(learner_id)


def authorize_student_access(
    *,
    user: dict | None,
    learner_id: int,
    student_learner_id: int | None,
    feature_enabled: bool,
) -> None:
    if normalize_auth_role(user.get("role") if user else None) is not AuthRole.STUDENT:
        raise VirtualTeacherAccessError("STUDENT_ACCESS_DENIED")
    if student_learner_id is None:
        raise VirtualTeacherAccessError("LEARNER_ID_UNRESOLVED")
    if int(student_learner_id) != int(learner_id):
        raise VirtualTeacherAccessError("CROSS_LEARNER_ACCESS_DENIED")
    if not feature_enabled:
        raise VirtualTeacherAccessError("FEATURE_DISABLED")


def authorize_parent_access(
    *,
    user: dict | None,
    parent_ref: str,
    learner_id: int,
    parent_authorized: bool,
) -> None:
    if normalize_auth_role(user.get("role") if user else None) is not AuthRole.PARENT:
        raise VirtualTeacherAccessError("PARENT_ACCESS_DENIED")
    if not parent_authorized:
        raise VirtualTeacherAccessError("CROSS_FAMILY_ACCESS_DENIED")
