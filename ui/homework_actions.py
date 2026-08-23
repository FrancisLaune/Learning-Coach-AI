"""Shared student homework action widgets (open / delete with 2-step confirm)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import streamlit as st

from domain.unified_experience.models import AssignmentStatus, HomeworkAssignment
from ui.navigation import request_navigation


def open_homework_session(
    *,
    learner_id: int,
    homework_id: int,
    open_for_learner: Callable[..., object],
) -> bool:
    """Open or resume a homework session and navigate to Ma séance."""
    opened = open_for_learner(learner_id, homework_id, datetime.now(UTC))
    session_id = getattr(opened, "session_id", None) if opened is not None else None
    if not session_id:
        return False
    st.session_state.v2_session_id = int(session_id)
    try:
        from ui.professor_ai_guided_cycle import remember_session_status

        remember_session_status(st.session_state, int(session_id), "RUNNING")
    except Exception:
        pass
    request_navigation(st.session_state, "student", "Ma séance")
    return True


def focus_homework_on_devoirs(homework_id: int) -> None:
    from services.professor_ai.guided_cycle import FOCUS_HOMEWORK_KEY

    st.session_state[FOCUS_HOMEWORK_KEY] = int(homework_id)
    request_navigation(st.session_state, "student", "Devoirs")


def render_delete_homework_button(
    *,
    homework_id: int,
    key_prefix: str,
    on_confirm: Callable[[], None],
    label_kind: str = "devoir",
) -> None:
    """Two-step deletion: (1) Supprimer (2) confirmation."""
    pending_key = f"{key_prefix}_del_pending_{homework_id}"
    if not st.session_state.get(pending_key):
        if st.button(
            f"🗑️ Supprimer ce {label_kind}",
            key=f"{key_prefix}_del_{homework_id}",
            use_container_width=True,
        ):
            st.session_state[pending_key] = True
            st.rerun()
        return

    st.warning(f"Êtes-vous certain de vouloir supprimer ce {label_kind} ? Cette action est définitive.")
    confirm, cancel = st.columns(2)
    if confirm.button(
        "Oui, je confirme la suppression",
        type="primary",
        key=f"{key_prefix}_del_yes_{homework_id}",
        use_container_width=True,
    ):
        st.session_state.pop(pending_key, None)
        on_confirm()
        st.rerun()
    if cancel.button(
        "Non, annuler",
        key=f"{key_prefix}_del_no_{homework_id}",
        use_container_width=True,
    ):
        st.session_state.pop(pending_key, None)
        st.rerun()


def kind_label(item: HomeworkAssignment) -> str:
    return "évaluation" if item.is_evaluation else "devoir"


def can_delete(item: HomeworkAssignment) -> bool:
    return item.status in {
        AssignmentStatus.READY,
        AssignmentStatus.IN_PROGRESS,
        AssignmentStatus.PAUSED,
    }
