"""Password hashing and verification with legacy compatibility."""

from __future__ import annotations

import hashlib
import hmac
import secrets

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 4


def password_length_error() -> str:
    return f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."


def is_password_too_short(password: str) -> bool:
    return len(password.strip()) < MIN_PASSWORD_LENGTH


def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith(f"{PBKDF2_ALGORITHM}$"):
        try:
            _, iterations_raw, salt, expected = stored_hash.split("$", 3)
            iterations = int(iterations_raw)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt),
                iterations,
            ).hex()
            return hmac.compare_digest(digest, expected)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(_legacy_sha256(password), stored_hash)


def needs_rehash(stored_hash: str) -> bool:
    return not stored_hash.startswith(f"{PBKDF2_ALGORITHM}$")
