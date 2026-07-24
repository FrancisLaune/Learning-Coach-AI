"""Safe deferred navigation for Streamlit widget-backed routes."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

NAVIGATION_REQUEST_KEY = "_navigation_request"


def request_navigation(
    state: MutableMapping[str, Any],
    scope: str,
    page: str,
    learner_id: int | None = None,
) -> None:
    """Record a route request without mutating an instantiated widget key."""
    state[NAVIGATION_REQUEST_KEY] = {
        "scope": scope,
        "page": page,
        "learner_id": learner_id,
    }


def apply_navigation_request(
    state: MutableMapping[str, Any],
    scope: str,
    widget_key: str,
    allowed_pages: tuple[str, ...],
) -> None:
    """Apply a pending request before the navigation widget is instantiated."""
    request = state.get(NAVIGATION_REQUEST_KEY)
    if not isinstance(request, dict) or request.get("scope") != scope:
        return
    page = request.get("page")
    if page not in allowed_pages:
        state.pop(NAVIGATION_REQUEST_KEY, None)
        return
    state[widget_key] = page
    learner_id = request.get("learner_id")
    if learner_id is not None:
        state["parent_selected_learner"] = int(learner_id)
    state.pop(NAVIGATION_REQUEST_KEY, None)
