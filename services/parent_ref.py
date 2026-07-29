"""Centralized parent_ref resolution for family management (LCAI-0015B)."""

from __future__ import annotations


def parent_ref_from_user(user: dict[str, object]) -> str:
    """Return the canonical V2 guardian reference for an authenticated parent."""
    return str(user["id"])
