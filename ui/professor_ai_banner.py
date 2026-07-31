"""LCAI-0022B/C — fixed Professor AI banner for the student parcours."""

from __future__ import annotations

import streamlit as st

from application.experience_factory import build_professor_ai_orchestrator
from domain.virtual_teacher.models import PreferencesPatch
from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.professor_ai.banner import (
    BannerPresenceState,
    build_banner_view,
    mode_label,
    parse_operating_mode,
)
from services.professor_ai.models import ProfessorOperatingMode, SessionPlan
from services.virtual_teacher.ai_teacher_preferences_service import AITeacherPreferencesService
from services.virtual_teacher.authorization import VirtualTeacherAccessError
from services.virtual_teacher.voice_pipeline import PRESENCE_STATE_KEY
from ui.navigation import request_navigation
from ui.professor_ai_guided_cycle import apply_guided_cycle_cta, build_cycle_snapshot

_MODE_OPTIONS = (
    ProfessorOperatingMode.PROFESSOR,
    ProfessorOperatingMode.COMPANION,
    ProfessorOperatingMode.MANUAL,
)

_VOICE_FOCUS_KEY = "professor_ai_voice_focus"


def render_professor_ai_banner(
    *,
    user: dict[str, object],
    learner_id: int,
    preferences_service: AITeacherPreferencesService | None = None,
    presence: BannerPresenceState = BannerPresenceState.IDLE,
) -> None:
    """Render the fixed top banner on student screens."""
    stored_presence = st.session_state.get(PRESENCE_STATE_KEY)
    if stored_presence in {item.value for item in BannerPresenceState}:
        presence = BannerPresenceState(str(stored_presence))

    repository = DuckDBVirtualTeacherRepository()
    preferences_service = preferences_service or AITeacherPreferencesService(repository)
    try:
        preferences = preferences_service.get_preferences_for_student(
            user=user,
            student_learner_id=int(user.get("resolved_learner_id", learner_id)),
            learner_id=learner_id,
        )
    except VirtualTeacherAccessError:
        preferences = repository.ensure_preferences(learner_id)

    stored_mode = parse_operating_mode(preferences.operating_mode)
    orchestrator = build_professor_ai_orchestrator()
    resolved_mode = orchestrator.resolve_mode(
        learner_id,
        requested=stored_mode if preferences.feature_enabled else ProfessorOperatingMode.MANUAL,
    )

    message = "Je suis prêt à t'accompagner dans ta séance."
    primary_action = "Continuer"
    secondary: tuple[str, ...] = ()
    plan: SessionPlan | None = None
    try:
        plan = orchestrator.plan_session(user, learner_id, mode=resolved_mode)
        message = plan.welcome.greeting
        primary_action = plan.welcome.primary_action or primary_action
        secondary = plan.welcome.secondary_actions
        if presence is BannerPresenceState.IDLE and message:
            presence = BannerPresenceState.SPEAKING
    except Exception:
        if presence is BannerPresenceState.IDLE:
            presence = BannerPresenceState.IDLE

    cycle = build_cycle_snapshot(plan, st.session_state) if plan is not None else None
    if cycle is not None:
        primary_action = cycle.cta_label

    banner = build_banner_view(
        learner_id=learner_id,
        teacher_name=preferences.teacher_name,
        mode=resolved_mode,
        feature_enabled=preferences.feature_enabled,
        parent_locked=preferences.parent_locked,
        message=message,
        primary_action=primary_action,
        secondary_actions=secondary,
        presence=presence,
    )

    with st.container(border=True):
        title_cols = st.columns([3, 2])
        title_cols[0].markdown(f"### {banner.teacher_name}")
        title_cols[1].caption(banner.caption)
        st.write(banner.message)
        if cycle is not None:
            st.caption(cycle.progress_caption)
        if banner.primary_action:
            st.caption(f"Priorité : {banner.primary_action}")

        action_cols = st.columns(5)
        cta_label = (cycle.cta_label if cycle is not None else banner.primary_action) or "Continuer"
        if action_cols[0].button(cta_label, key=f"banner_cta_{learner_id}", type="primary", use_container_width=True):
            if cycle is not None:
                apply_guided_cycle_cta(st.session_state, cycle)
            else:
                request_navigation(st.session_state, "student", "Tableau de bord")
            st.rerun()
        if action_cols[1].button("Devoirs", key=f"banner_hw_{learner_id}", use_container_width=True):
            request_navigation(st.session_state, "student", "Devoirs")
            st.rerun()
        if action_cols[2].button("Séance", key=f"banner_session_{learner_id}", use_container_width=True):
            request_navigation(st.session_state, "student", "Ma séance IA")
            st.rerun()
        if action_cols[3].button("Discuter", key=f"banner_chat_{learner_id}", use_container_width=True):
            request_navigation(st.session_state, "student", "Mon professeur IA")
            st.rerun()
        if action_cols[4].button("Parler", key=f"banner_voice_{learner_id}", use_container_width=True):
            st.session_state[_VOICE_FOCUS_KEY] = True
            st.session_state[PRESENCE_STATE_KEY] = BannerPresenceState.LISTENING.value
            request_navigation(st.session_state, "student", "Mon professeur IA")
            st.rerun()

        if banner.mode_editable:
            labels = {mode: mode_label(mode) for mode in _MODE_OPTIONS}
            selected = st.radio(
                "Mode d'accompagnement",
                _MODE_OPTIONS,
                index=_MODE_OPTIONS.index(
                    resolved_mode if resolved_mode in _MODE_OPTIONS else ProfessorOperatingMode.MANUAL
                ),
                format_func=labels.__getitem__,
                horizontal=True,
                key=f"banner_mode_{learner_id}",
            )
            if selected is not resolved_mode:
                try:
                    preferences_service.save_for_student(
                        user=user,
                        student_learner_id=int(user.get("resolved_learner_id", learner_id)),
                        learner_id=learner_id,
                        patch=PreferencesPatch(operating_mode=selected.value, fields={"operating_mode"}),
                    )
                    st.rerun()
                except VirtualTeacherAccessError as exc:
                    st.warning(str(exc))
        elif not banner.feature_enabled:
            st.info("Le Professeur IA peut être activé par un parent depuis la fiche élève.")
        else:
            st.caption("Le mode est verrouillé par le parent.")
