"""Student guidance widgets — parcours élève (LCAI-0030-A)."""

from __future__ import annotations

import streamlit as st

from application.dto.student_guidance import (
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


_STATUS_LABELS_FR = {
    "DRAFT": "Brouillon",
    "READY": "À faire",
    "IN_PROGRESS": "En cours",
    "PAUSED": "En pause",
    "COMPLETED": "Terminé",
    "EXPIRED": "Expiré",
    "CANCELLED": "Annulé",
}


def render_evaluation_progress(
    snapshot: StudentDashboardSnapshot,
    *,
    key_prefix: str = "eval_progress",
    title: str = "Mes évaluations",
    allow_retake: bool = True,
    show_corrections: bool = True,
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
            if show_corrections and item.session_id is not None:
                render_answer_corrections(
                    snapshot.context.learner_id,
                    int(item.session_id),
                    key_prefix=f"{key_prefix}_corr_{item.homework_id}",
                    expanded=False,
                )
            if allow_retake and item.needs_retake:
                st.caption("Pas encore à 100 % — tu peux refaire cette évaluation.")
                if st.button(
                    "🔁 Relancer cette évaluation",
                    key=f"{key_prefix}_retake_{item.homework_id}",
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


def _render_home_assignment_card(
    *,
    learner_id: int,
    card,
    key_prefix: str,
) -> None:
    from application.experience_factory import build_homework_session_service
    from services.homework.factory import build_homework_service
    from ui.homework_actions import focus_homework_on_devoirs, open_homework_session, render_delete_homework_button

    kind = "Évaluation" if card.is_evaluation else "Devoir"
    status_label = _STATUS_LABELS_FR.get(card.status, card.status)
    if card.score_out_of_20 is not None:
        note = f"{card.score_out_of_20:g}/20"
    elif card.score_percent is not None:
        note = f"{card.score_percent:.0f} %"
    else:
        note = "—"
    with st.container(border=True):
        st.markdown(f"**{kind}** · {card.exercise_count} question(s) · {status_label} · note **{note}**")
        labels: list[str] = []
        handlers: list[object] = []
        if card.can_open:
            labels.append("▶️ Reprendre" if card.status in {"IN_PROGRESS", "PAUSED"} else "▶️ Commencer")
            handlers.append("open")
        if card.can_retake:
            labels.append("🔁 Relancer")
            handlers.append("retake")
        if card.can_delete and not st.session_state.get(f"{key_prefix}_del_pending_{card.homework_id}"):
            labels.append("🗑️ Supprimer cette évaluation" if card.is_evaluation else "🗑️ Supprimer ce devoir")
            handlers.append("delete")
        if labels:
            cols = st.columns(len(labels))
            for column, label, handler in zip(cols, labels, handlers, strict=True):
                if column.button(label, key=f"{key_prefix}_{handler}_{card.homework_id}", use_container_width=True):
                    if handler == "open":
                        try:
                            if card.status == "PAUSED":
                                build_homework_service().resume(learner_id, int(card.homework_id))
                            opened = open_homework_session(
                                learner_id=learner_id,
                                homework_id=int(card.homework_id),
                                open_for_learner=build_homework_session_service().open_for_learner,
                            )
                            if not opened:
                                focus_homework_on_devoirs(int(card.homework_id))
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()
                    elif handler == "retake":
                        try:
                            retake = build_homework_service().retake_assignment(learner_id, int(card.homework_id))
                            opened = open_homework_session(
                                learner_id=learner_id,
                                homework_id=int(retake.homework_id),
                                open_for_learner=build_homework_session_service().open_for_learner,
                            )
                            if not opened:
                                focus_homework_on_devoirs(int(retake.homework_id))
                        except Exception as exc:
                            st.error(str(exc))
                        else:
                            st.rerun()
                    elif handler == "delete":
                        st.session_state[f"{key_prefix}_del_pending_{card.homework_id}"] = True
                        st.rerun()
        if card.can_delete and st.session_state.get(f"{key_prefix}_del_pending_{card.homework_id}"):
            # Full-width confirmation outside action columns (avoids nested columns crash).
            render_delete_homework_button(
                homework_id=int(card.homework_id),
                key_prefix=key_prefix,
                label_kind="évaluation" if card.is_evaluation else "devoir",
                on_confirm=lambda hid=int(card.homework_id): build_homework_service().cancel(learner_id, hid),
            )
        if card.can_view_corrections and card.session_id is not None:
            with st.expander("Voir la correction (erreurs et solutions)", expanded=False):
                render_answer_corrections(
                    learner_id,
                    int(card.session_id),
                    key_prefix=f"{key_prefix}_corr_{card.homework_id}",
                    expanded=True,
                )


def render_student_home(
    *,
    snapshot: StudentDashboardSnapshot,
    dashboard: StudentDashboard | None = None,
) -> None:
    """Accueil élève Objectif Brevet (§29) — délègue au dashboard DNB."""
    from ui.dnb_student_home import render_brevet_student_home

    render_brevet_student_home(snapshot=snapshot, dashboard=dashboard)


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
    """Oui/Non help: Coach Brevet tip for the exercise, then chat follow-ups."""
    service = build_student_guidance_service()
    chat_key = f"{key_prefix}_help_chat"
    with st.container(border=True):
        st.markdown("### Aide — Coach Brevet")
        st.caption(
            "Choisis Oui pour envoyer l'exercice au Coach Brevet (contexte DNB complet). "
            "Tu pourras ensuite poser des questions si ce n'est pas suffisant."
        )
        want_help = st.radio(
            "Aide",
            options=("Non", "Oui"),
            index=0,
            horizontal=True,
            key=f"{key_prefix}_help_on_off",
        )
        if want_help == "Non":
            st.session_state.pop(chat_key, None)
            return

        chat: list[dict[str, str]] = list(st.session_state.get(chat_key) or [])
        if not chat:
            with st.spinner("Envoi de l'exercice au Coach Brevet…"):
                response = service.guide_current_exercise(
                    _student_actor(user, learner_id),
                    learner_id,
                    session_id,
                    activity_id,
                    1,
                    statement=statement,
                    hint_text=hint_text,
                    notion_reminder=notion_reminder,
                    method_outline=method_outline,
                )
                chat = [{"role": "assistant", "content": response.message}]
                if response.degraded_notice:
                    chat[0]["notice"] = response.degraded_notice
                st.session_state[chat_key] = chat

        for message in chat:
            role = message.get("role", "assistant")
            label = "Toi" if role == "user" else "Coach Brevet"
            st.markdown(f"**{label} :**")
            if role == "assistant":
                st.info(message.get("content", ""))
            else:
                st.write(message.get("content", ""))
            notice = message.get("notice")
            if notice:
                st.caption(notice)

        follow_key = f"{key_prefix}_help_followup"
        follow_up = st.text_area(
            "Ta question au Coach Brevet (si l'aide ne suffit pas)",
            key=follow_key,
            height=90,
            placeholder="Ex. : Je ne comprends pas la première étape…",
        )
        cols = st.columns(2)
        with cols[0]:
            send = st.button(
                "Envoyer au Coach Brevet",
                key=f"{key_prefix}_help_send",
                use_container_width=True,
                type="primary",
                disabled=not str(follow_up or "").strip(),
            )
        with cols[1]:
            regen = st.button(
                "Nouvelle aide",
                key=f"{key_prefix}_regen_help",
                use_container_width=True,
            )
        if regen:
            st.session_state.pop(chat_key, None)
            st.session_state.pop(follow_key, None)
            st.rerun()
        if send:
            question = str(follow_up or "").strip()
            history = tuple(
                (item["role"], item["content"]) for item in chat if item.get("role") in {"user", "assistant"}
            )
            with st.spinner("Réponse du Coach Brevet…"):
                try:
                    reply = service.continue_exercise_help(
                        _student_actor(user, learner_id),
                        learner_id,
                        follow_up=question,
                        history=history,
                        statement=statement,
                        notion_reminder=notion_reminder,
                    )
                except ValueError as exc:
                    st.warning(str(exc))
                    return
            chat.append({"role": "user", "content": question})
            assistant_msg: dict[str, str] = {"role": "assistant", "content": reply.message}
            if reply.degraded_notice:
                assistant_msg["notice"] = reply.degraded_notice
            chat.append(assistant_msg)
            st.session_state[chat_key] = chat
            st.session_state.pop(follow_key, None)
            st.rerun()


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
    expanded: bool = True,
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
    correct_count = sum(1 for item in items if item.correct)
    st.subheader("Correction détaillée", anchor=False)
    st.caption(f"{correct_count}/{len(items)} réponse(s) correcte(s).")
    show = st.toggle(
        "Afficher toutes les réponses et corrections",
        value=expanded,
        key=f"{key_prefix}_show_{session_id}",
    )
    if not show:
        return
    for item in items:
        badge = "✅ Correcte" if item.correct else "❌ Incorrecte"
        with st.container(border=True):
            st.markdown(f"**Question {item.position}** — {badge} · {item.score:.0f} %")
            st.write(item.statement)
            st.markdown(f"**Ta réponse :** {item.student_answer or '—'}")
            st.markdown(f"**Bonne réponse :** {item.expected_answer or '—'}")
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
