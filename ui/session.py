"""Streamlit session-state helpers extracted from the legacy entry point."""

from __future__ import annotations

import streamlit as st


def _session_defaults() -> dict[str, object]:
    """Create fresh mutable defaults for each Streamlit session."""
    return {
        "user": None,
        "active_exam_id": None,
        "practice_question": None,
        "practice_feedback": None,
        "practice_answer_checked": None,
        "training_questions": [],
        "training_page": 0,
        "training_results": None,
        "training_signature": None,
        "training_started_at": None,
        "exam_opened_at": {},
    }


def initialize_state() -> None:
    """Populate missing state keys with the same defaults as the legacy UI."""
    for key, value in _session_defaults().items():
        st.session_state.setdefault(key, value)


def logout() -> None:
    """Clear the current Streamlit session and rerun the page."""
    st.session_state.clear()
    st.rerun()
