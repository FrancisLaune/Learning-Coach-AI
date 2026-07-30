"""LCAI-0020 — Professeur IA guidance widgets for the student parcours."""

from __future__ import annotations

import streamlit as st

from application.dto.student_guidance import (
    AIAvailabilityMode,
    GuidanceSource,
    HomeworkGuidanceResponse,
    ResultExplanationContext,
    RevisionGuidanceContext,
    StudentDashboardSnapshot,
)
from application.experience_factory import build_student_guidance_service
from services.auth.roles import AuthRole
from ui.navigation import request_navigation


def _student_actor(user: dict[str, object], learner_id: int) -> dict[str, object]:
    actor = dict(user)
    actor["resolved_learner_id"] = learner_id
    actor["learner_id"] = learner_id
    if "role" not in actor:
        actor["role"] = AuthRole.STUDENT.value
    return actor


def load_student_dashboard_snapshot(user: dict[str, object], learner_id: int) -> StudentDashboardSnapshot:
    service = build_student_guidance_service()
    return service.build_dashboard_snapshot(_student_actor(user, learner_id), learner_id)


def render_professor_ia_card(snapshot: StudentDashboardSnapshot) -> None:
    welcome = snapshot.welcome
    with st.container(border=True):
        st.subheader("Professeur IA", anchor=False)
        if welcome.degraded_notice:
            st.caption(welcome.degraded_notice)
        source_label = "Accompagnement IA" if welcome.source is GuidanceSource.AI else "Accompagnement standard"
        st.caption(source_label)
        st.write(welcome.greeting)
        st.markdown(f"**Priorité :** {welcome.primary_action}")
        if welcome.secondary_actions:
            st.markdown("**Actions possibles :**")
            for action in welcome.secondary_actions:
                st.write(f"- {action}")
        if snapshot.availability.mode is AIAvailabilityMode.INACTIVE:
            st.info("Le Professeur IA peut être activé depuis le profil parent.")
        cols = st.columns(2)
        if cols[0].button("Mes devoirs", key=f"guidance_homework_{snapshot.context.learner_id}", use_container_width=True):
            request_navigation(st.session_state, "student", "Devoirs")
            st.rerun()
        if cols[1].button("Mon professeur IA", key=f"guidance_vt_{snapshot.context.learner_id}", use_container_width=True):
            request_navigation(st.session_state, "student", "Mon professeur IA")
            st.rerun()


def render_mastery_bands(snapshot: StudentDashboardSnapshot) -> None:
    if not snapshot.context.mastery:
        st.info("Les catégories de maîtrise apparaîtront après les premières activités évaluées.")
        return
    st.subheader("Catégories de maîtrise", anchor=False)
    for _band_key, items in sorted(snapshot.mastery_by_band.items()):
        if not items:
            continue
        label = items[0].band_label
        with st.expander(f"{label} ({len(items)})", expanded=False):
            for item in items:
                st.write(f"**{item.label}** — {item.score:.0f} %")


def render_homework_before_guidance(user: dict[str, object], learner_id: int, homework_id: int) -> None:
    service = build_student_guidance_service()
    context = service.prepare_homework_guidance(_student_actor(user, learner_id), learner_id, homework_id)
    with st.expander("Conseil du Professeur IA — avant le devoir", expanded=True):
        st.markdown(f"**Objectif :** {context.objective}")
        if context.estimated_minutes:
            st.caption(f"Durée estimée : {context.estimated_minutes} min")
        st.write(context.advice_before)


def render_homework_during_guidance(
    user: dict[str, object],
    learner_id: int,
    session_id: int,
    activity_id: int,
    *,
    key_prefix: str,
) -> None:
    service = build_student_guidance_service()
    with st.expander("Demander au Professeur IA", expanded=False):
        help_level = st.slider(
            "Niveau d'aide",
            1,
            6,
            3,
            key=f"{key_prefix}_help_level",
            help="Les niveaux 1 à 5 guident sans donner la réponse finale.",
        )
        if st.button("Obtenir un conseil", key=f"{key_prefix}_ask_professor"):
            response = service.guide_current_exercise(
                _student_actor(user, learner_id),
                learner_id,
                session_id,
                activity_id,
                help_level,
            )
            st.session_state[f"{key_prefix}_hw_guidance"] = response
        cached = st.session_state.get(f"{key_prefix}_hw_guidance")
        if isinstance(cached, HomeworkGuidanceResponse):
            source = "IA" if cached.source is GuidanceSource.AI else "standard"
            st.info(f"Accompagnement {source} : {cached.message}")
            if cached.degraded_notice:
                st.caption(cached.degraded_notice)


def render_homework_result_explanation(context: ResultExplanationContext) -> None:
    with st.container(border=True):
        st.subheader("Explication du Professeur IA", anchor=False)
        st.write(context.score_summary)
        if context.strengths:
            st.markdown("**Forces :** " + ", ".join(context.strengths))
        if context.weaknesses:
            st.markdown("**À consolider :** " + ", ".join(context.weaknesses))
        st.caption(context.deterministic_recommendation)


def load_revision_guidance(user: dict[str, object], learner_id: int) -> RevisionGuidanceContext:
    service = build_student_guidance_service()
    return service.recommend_revision(_student_actor(user, learner_id), learner_id)


def load_homework_result_explanation(
    user: dict[str, object],
    learner_id: int,
    homework_id: int,
) -> ResultExplanationContext:
    service = build_student_guidance_service()
    return service.explain_homework_result(_student_actor(user, learner_id), learner_id, homework_id)


def load_session_result_explanation(
    user: dict[str, object],
    learner_id: int,
    session_id: int,
) -> ResultExplanationContext | None:
    service = build_student_guidance_service()
    return service.explain_session_result(_student_actor(user, learner_id), learner_id, session_id)
