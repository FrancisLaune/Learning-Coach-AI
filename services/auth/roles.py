"""Authenticated account roles for the legacy Streamlit login system."""

from __future__ import annotations

from enum import StrEnum


class AuthRole(StrEnum):
    """Human roles that authenticate through the V1 users table."""

    PARENT = "parent"
    STUDENT = "student"


def is_known_auth_role(role: object) -> bool:
    value = str(role)
    return any(item.value == value for item in AuthRole)


def normalize_auth_role(role: object) -> AuthRole | None:
    value = str(role)
    for item in AuthRole:
        if item.value == value:
            return item
    return None
