"""Student guidance widgets — parcours élève (LCAI-0030-A)."""

from __future__ import annotations

import streamlit as st

from application.dto.student_guidance import (
    GuidanceSource,
    HomeworkGuidanceResponse,
    ResultExplanationContext,
    RevisionGuidanceContext,
    StudentDashboardSnapshot,
)
from application.experience_factory import build_student_guidance_service
from services.auth.roles import AuthRole
from services.learning_session.experience import StudentDashboard
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


def render_evaluation_progress(
    snapshot: StudentDashboardSnapshot,
    *,
    key_prefix: str = "eval_progress",
    title: str = "Mes évaluations",
    allow_retake: bool = True,
) -> None:
    """Affiche les évaluations terminées avec score % et note /20."""
    from ui.homework_actions import focus_homework_on_devoirs, open_homework_session

    items = snapshot.context.evaluation_progress
    if not items:
        st.info("Aucune évaluation terminée pour le moment.")
        return
    st.subheader(title, anchor=False)
    for item in items:
        score = "—" if item.overall_score is None else f"{item.overall_score:.0f} %"
        with st.container(border=True):
            st.markdown(f"**{item.subject_label}** — {item.exercise_count} questions · score {score}")
            if item.overall_score is not None:
                from services.homework.evaluation_sizing import score_percent_to_out_of_20

                on_20 = score_percent_to_out_of_20(item.overall_score)
                if on_20 is not None:
                    st.caption(f"Note ramenée sur 20 : **{on_20:g}/20**")
            if allow_retake and item.needs_retake:
                st.caption("Pas encore à 100 % — tu peux refaire cette évaluation.")
                if st.button(
                    "🔁 Refaire cette évaluation",
                    key=f"{key_prefix}_retake_{item.homework_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    from application.experience_factory import build_homework_session_service
                    from services.homework.factory import build_homework_service

                    try:
                        retake = build_homework_service().retake_evaluation(
                            snapshot.context.learner_id, int(item.homework_id)
                        )
                        opened = open_homework_session(
                            learner_id=snapshot.context.learner_id,
                            homework_id=int(retake.homework_id),
                            open_for_learner=build_homework_session_service().open_for_learner,
                        )
                        if not opened:
                            focus_homework_on_devoirs(int(retake.homework_id))
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()


def render_student_home(
    *,
    snapshot: StudentDashboardSnapshot,
    dashboard: StudentDashboard | None = None,
) -> None:
    """Accueil élève : évolution + priorités matières/chapitres (sans Professeur IA)."""
    from ui.homework_actions import focus_homework_on_devoirs, open_homework_session, render_delete_homework_button

    context = snapshot.context
    st.title(f"Bonjour {context.display_name}")
    if context.objective:
        st.markdown(f"### Objectif : {context.objective}")

    metrics = dashboard.metrics if dashboard is not None else ()
    if metrics:
        st.subheader("Mon évolution", anchor=False)
        columns = st.columns(min(5, len(metrics)))
        for column, metric in zip(columns, metrics, strict=True):
            column.metric(metric.label, metric.value, help=metric.help_text or None)
    elif context.success_rate or context.recent_score:
        st.subheader("Mon évolution", anchor=False)
        cols = st.columns(2)
        if context.recent_score:
            cols[0].metric("Indicateur récent", context.recent_score)
        if context.success_rate:
            cols[1].metric("Réussite", context.success_rate)

    if context.evaluation_progress:
        render_evaluation_progress(snapshot, key_prefix=f"home_eval_{context.learner_id}")

    st.subheader("À travailler", anchor=False)
    overdue = context.homework_overdue
    priorities = snapshot.recommendations or context.revision_priorities
    if overdue:
        st.warning(f"{len(overdue)} devoir(s) en retard.")
        for item in overdue[:5]:
            cols = st.columns([3, 1])
            kind = "Évaluation" if item.is_evaluation else "Devoir"
            cols[0].write(f"**{item.subject_label}** — {kind} · échéance dépassée")
            if cols[1].button("📂 Ouvrir", key=f"home_overdue_{item.homework_id}", use_container_width=True):
                focus_homework_on_devoirs(item.homework_id)
                st.rerun()
    if priorities:
        for item in priorities[:8]:
            with st.container(border=True):
                st.markdown(f"**{item.subject_label}** — {item.skill_label}")
                st.caption(item.reason)
                st.caption(f"Durée estimée : ~{item.estimated_minutes} min")
                action_cols = st.columns(2 if item.homework_id else 1)
                primary_label = f"▶️ {item.action_label}"
                if action_cols[0].button(
                    primary_label,
                    key=f"home_act_{item.homework_id or item.skill_id}_{item.action_label}",
                    type="primary",
                    use_container_width=True,
                ):
                    if item.homework_id:
                        from application.experience_factory import build_homework_session_service
                        from services.homework.factory import build_homework_service

                        homework_service = build_homework_service()
                        target_id = int(item.homework_id)
                        if "refaire" in item.action_label.casefold():
                            try:
                                retake = homework_service.retake_evaluation(context.learner_id, target_id)
                                target_id = int(retake.homework_id)
                            except Exception as exc:
                                st.error(str(exc))
                                st.stop()
                        sessions = build_homework_session_service()
                        try:
                            opened = open_homework_session(
                                learner_id=context.learner_id,
                                homework_id=target_id,
                                open_for_learner=sessions.open_for_learner,
                            )
                        except Exception:
                            opened = False
                        if not opened:
                            focus_homework_on_devoirs(target_id)
                        st.rerun()
                    else:
                        request_navigation(st.session_state, "student", "Révision")
                        st.rerun()
                if item.homework_id and len(action_cols) > 1:
                    from services.homework.factory import build_homework_service

                    with action_cols[1]:
                        render_delete_homework_button(
                            homework_id=int(item.homework_id),
                            key_prefix=f"home_{context.learner_id}",
                            label_kind="évaluation" if "évaluation" in item.action_label.casefold() else "devoir",
                            on_confirm=lambda hid=int(item.homework_id): build_homework_service().cancel(
                                context.learner_id, hid
                            ),
                        )
    elif not overdue:
        st.info("Continue tes devoirs ou une révision pour affiner tes priorités.")

    actions = st.columns(3)
    if actions[0].button("Mes devoirs", key=f"home_hw_{context.learner_id}", use_container_width=True, type="primary"):
        request_navigation(st.session_state, "student", "Devoirs")
        st.rerun()
    if actions[1].button("Ma séance", key=f"home_session_{context.learner_id}", use_container_width=True):
        request_navigation(st.session_state, "student", "Ma séance")
        st.rerun()
    if actions[2].button("Révision", key=f"home_revision_{context.learner_id}", use_container_width=True):
        request_navigation(st.session_state, "student", "Révision")
        st.rerun()

    from ui.chatgpt_voice import render_chatgpt_voice_access

    render_chatgpt_voice_access(
        snapshot=snapshot,
        expanded=False,
        key_prefix=f"home_chatgpt_{context.learner_id}",
    )

    if dashboard is not None and dashboard.current_session is not None:
        session = dashboard.current_session
        st.caption(
            f"Séance en cours ou planifiée — durée conseillée : {dashboard.recommended_duration_minutes} min "
            f"(état : {session.status})."
        )
    if context.next_revision:
        st.caption(f"Prochaine révision suggérée : {context.next_revision.strftime('%d/%m/%Y')}")


def render_professor_ia_card(snapshot: StudentDashboardSnapshot) -> None:
    """Deprecated LCAI-0030-A — conservé pour compat tests / strangler, non exposé UI."""
    render_student_home(snapshot=snapshot)


def render_mastery_bands(snapshot: StudentDashboardSnapshot) -> None:
    if not snapshot.context.mastery:
        st.info("Les catégories de maîtrise apparaîtront après les premières activités évaluées.")
        return
    st.subheader("Matières et chapitres — maîtrise", anchor=False)
    for _band_key, items in sorted(snapshot.mastery_by_band.items()):
        if not items:
            continue
        label = items[0].band_label
        with st.expander(f"{label} ({len(items)})", expanded=_band_key in {"FRAGILE", "TO_REVISE"}):
            for item in items:
                subject = item.subject_label or "Compétence"
                chapter = f" / {item.chapter_label}" if item.chapter_label else ""
                st.write(f"**{subject}{chapter}** — {item.label} — {item.score:.0f} %")


def render_homework_before_guidance(user: dict[str, object], learner_id: int, homework_id: int) -> None:
    service = build_student_guidance_service()
    context = service.prepare_homework_guidance(_student_actor(user, learner_id), learner_id, homework_id)
    with st.expander("Conseil avant le devoir", expanded=True):
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
    statement: str | None = None,
    hint_text: str | None = None,
    notion_reminder: str | None = None,
    method_outline: str | None = None,
) -> None:
    service = build_student_guidance_service()
    with st.expander("🆘 Demander une aide", expanded=True):
        st.caption("Aides progressives : indice → notion → démarche (sans spoiler immédiat).")
        help_level = st.radio(
            "Type d'aide",
            options=(1, 2, 3, 4, 5),
            format_func={
                1: "1 — Repérer la demande",
                2: "2 — Indice utile",
                3: "3 — Rappel de notion",
                4: "4 — Démarche étape par étape",
                5: "5 — Piste guidée (sans réponse finale)",
            }.get,
            horizontal=False,
            key=f"{key_prefix}_help_level",
        )
        if st.button("Obtenir un conseil", key=f"{key_prefix}_ask_professor"):
            response = service.guide_current_exercise(
                _student_actor(user, learner_id),
                learner_id,
                session_id,
                activity_id,
                int(help_level),
                statement=statement,
                hint_text=hint_text,
                notion_reminder=notion_reminder,
                method_outline=method_outline,
            )
            st.session_state[f"{key_prefix}_hw_guidance"] = response
        cached = st.session_state.get(f"{key_prefix}_hw_guidance")
        if isinstance(cached, HomeworkGuidanceResponse):
            source = "IA" if cached.source is GuidanceSource.AI else "standard"
            st.info(f"Aide {source} : {cached.message}")
            if cached.degraded_notice:
                st.caption(cached.degraded_notice)


def render_homework_result_explanation(context: ResultExplanationContext) -> None:
    with st.container(border=True):
        st.subheader("Bilan de ton devoir", anchor=False)
        st.write(context.score_summary)
        if context.strengths:
            st.markdown("**Forces :** " + ", ".join(context.strengths))
        if context.weaknesses:
            st.markdown("**À consolider :** " + ", ".join(context.weaknesses))
        st.caption(context.deterministic_recommendation)


def render_answer_corrections(
    learner_id: int,
    session_id: int,
    *,
    key_prefix: str = "corrections",
) -> None:
    """Show per-question corrections for a completed homework/evaluation session."""
    from application.experience_factory import build_unified_session_execution_service

    try:
        items = build_unified_session_execution_service().corrections(learner_id, int(session_id))
    except Exception as exc:
        st.warning(f"Corrections indisponibles : {exc}")
        return
    if not items:
        st.info("Aucune réponse enregistrée à corriger pour cette séance.")
        return
    with st.expander("Voir les corrections détaillées", expanded=False):
        for item in items:
            badge = "✅" if item.correct else "❌"
            with st.container(border=True):
                st.markdown(f"{badge} **Question {item.position}** — {item.score:.0f} %")
                st.write(item.statement)
                st.caption(f"Ta réponse : {item.student_answer or '—'}")
                st.caption(f"Réponse attendue : {item.expected_answer or '—'}")
                if item.explanation:
                    st.info(item.explanation)
                if item.method:
                    st.caption(f"Méthode : {item.method}")


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
