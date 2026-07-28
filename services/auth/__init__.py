"""Authentication services for Learning Coach AI."""

from services.auth.authorization import (
    parent_owns_learner,
    require_known_auth_role,
    require_parent_role,
    require_student_role,
)
from services.auth.email_delivery import deliver_auth_email
from services.auth.password_reset import (
    RESET_PURPOSE_CHILD,
    RESET_PURPOSE_PARENT,
    generate_reset_token,
    hash_reset_token,
    neutral_recovery_message,
)
from services.auth.passwords import hash_password, needs_rehash, verify_password
from services.auth.roles import AuthRole, is_known_auth_role, normalize_auth_role

__all__ = [
    "AuthRole",
    "RESET_PURPOSE_CHILD",
    "RESET_PURPOSE_PARENT",
    "deliver_auth_email",
    "generate_reset_token",
    "hash_password",
    "hash_reset_token",
    "is_known_auth_role",
    "needs_rehash",
    "neutral_recovery_message",
    "normalize_auth_role",
    "parent_owns_learner",
    "require_known_auth_role",
    "require_parent_role",
    "require_student_role",
    "verify_password",
]
