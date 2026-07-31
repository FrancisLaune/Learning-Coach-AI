"""UI helpers for the Professor AI guided cycle (LCAI-0022C)."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from services.professor_ai.guided_cycle import (
    CYCLE_STATE_KEY,
    FOCUS_DIAGNOSTIC_KEY,
    FOCUS_HOMEWORK_KEY,
    GuidedCycleSnapshot,
    closed_session_key,
    resolve_guided_cycle,
)
from services.professor_ai.models import SessionPlan
from ui.navigation import request_navigation


def read_active_session_signals(state: MutableMapping[str, Any]) -> tuple[int | None, str | None]:
    raw_id = state.get("v2_session_id")
    if raw_id is None:
        return None, None
    try:
        session_id = int(raw_id)
    except (TypeError, ValueError):
        return None, None
    status = state.get(f"professor_ai_session_status_{session_id}")
    if status is None:
        status = state.get("professor_ai_active_session_status")
    return session_id, str(status) if status is not None else None


def remember_session_status(state: MutableMapping[str, Any], session_id: int, status: str) -> None:
    state[f"professor_ai_session_status_{int(session_id)}"] = str(status)
    state["professor_ai_active_session_status"] = str(status)


def synthesis_closed_session_id(state: MutableMapping[str, Any], session_id: int | None) -> int | None:
    if session_id is None:
        return None
    if state.get(closed_session_key(session_id)):
        return int(session_id)
    return None


def build_cycle_snapshot(
    plan: SessionPlan,
    state: MutableMapping[str, Any],
) -> GuidedCycleSnapshot:
    session_id, status = read_active_session_signals(state)
    snapshot = resolve_guided_cycle(
        plan,
        active_session_id=session_id,
        active_session_status=status,
        synthesis_closed_for_session=synthesis_closed_session_id(state, session_id),
    )
    state[CYCLE_STATE_KEY] = snapshot.step.value
    return snapshot


def apply_guided_cycle_cta(
    state: MutableMapping[str, Any],
    snapshot: GuidedCycleSnapshot,
) -> None:
    """Navigate to the recommended cycle page and set soft focus flags."""
    state[CYCLE_STATE_KEY] = snapshot.step.value
    if snapshot.focus_diagnostic:
        state[FOCUS_DIAGNOSTIC_KEY] = True
    else:
        state.pop(FOCUS_DIAGNOSTIC_KEY, None)
    if snapshot.homework_id is not None:
        state[FOCUS_HOMEWORK_KEY] = int(snapshot.homework_id)
    else:
        state.pop(FOCUS_HOMEWORK_KEY, None)
    if snapshot.session_id is not None:
        state["v2_session_id"] = int(snapshot.session_id)
    request_navigation(state, "student", snapshot.page)


def mark_cycle_synthesis_closed(state: MutableMapping[str, Any], session_id: int) -> None:
    state[closed_session_key(session_id)] = True
    state[CYCLE_STATE_KEY] = "SYNTHESE"
