"""Password reset token lifecycle."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

RESET_PURPOSE_PARENT = "parent_reset"
RESET_PURPOSE_CHILD = "child_recovery"
DEFAULT_EXPIRY_MINUTES = 60


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expiry_timestamp(*, minutes: int = DEFAULT_EXPIRY_MINUTES) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


def neutral_recovery_message() -> str:
    return (
        "Si un compte correspond à ces informations, un e-mail de réinitialisation "
        "a été envoyé à l'adresse associée."
    )
