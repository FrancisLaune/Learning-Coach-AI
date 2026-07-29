"""Learner identity cache helpers for Streamlit session revalidation (LCAI-0015B)."""

from __future__ import annotations


def learner_cache_key(user_id: object, external_ref: str) -> str:
    return f"{user_id}:{external_ref}"


def cached_learner_id_if_valid(
    *,
    session_cache_key: str | None,
    user_id: object,
    external_ref: str,
    cached_learner_id: object,
) -> int | None:
    expected = learner_cache_key(user_id, external_ref)
    if session_cache_key != expected or cached_learner_id is None:
        return None
    return int(cached_learner_id)
