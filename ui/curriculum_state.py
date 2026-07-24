"""State reconciliation for dependent curriculum selectors."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def reconcile_subject_change(
    state: MutableMapping[str, Any],
    prefix: str,
    subject_id: int | None,
) -> None:
    marker = f"{prefix}_subject_marker"
    if state.get(marker) != subject_id:
        state[f"{prefix}_chapters"] = []
        state[f"{prefix}_skills"] = []
        state[marker] = subject_id


def reconcile_skills(
    state: MutableMapping[str, Any],
    prefix: str,
    valid_skill_ids: set[int],
) -> None:
    key = f"{prefix}_skills"
    selected = state.get(key, [])
    state[key] = [int(skill_id) for skill_id in selected if int(skill_id) in valid_skill_ids]


def clear_curriculum_selection(state: MutableMapping[str, Any], prefix: str) -> None:
    state[f"{prefix}_chapters"] = []
    state[f"{prefix}_skills"] = []
