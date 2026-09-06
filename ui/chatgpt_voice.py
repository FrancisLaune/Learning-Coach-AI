"""UI — accès unique au Coach Brevet via ChatGPT (voix/texte)."""

from __future__ import annotations

import streamlit as st

from application.dto.student_guidance import StudentDashboardSnapshot
from services.chatgpt_voice import (
    COACH_NAME,
    SCHOOL_FRAME_MESSAGE,
    VOICE_HINT,
    ChatGptVoiceContext,
    build_context_prompt,
    chatgpt_open_url,
    context_from_snapshot,
)


def render_chatgpt_voice_access(
    *,
    context: ChatGptVoiceContext | None = None,
    snapshot: StudentDashboardSnapshot | None = None,
    expanded: bool = False,
    key_prefix: str = "chatgpt_voice",
    exercise_statement: str = "",
    notion_reminder: str = "",
) -> None:
    """Coach Brevet unique : lien ChatGPT + briefing complet copiable."""
    if context is not None:
        voice_context = context
    elif snapshot is not None:
        voice_context = context_from_snapshot(
            snapshot,
            exercise_statement=exercise_statement,
            notion_reminder=notion_reminder,
        )
    else:
        voice_context = ChatGptVoiceContext(grade_label="3e")

    prompt = build_context_prompt(voice_context)
    url = chatgpt_open_url(voice_context)

    with st.expander(f"{COACH_NAME} — poser une question (ChatGPT)", expanded=expanded):
        st.info(SCHOOL_FRAME_MESSAGE)
        st.caption(VOICE_HINT)
        coach = voice_context.as_coach()
        if coach.days_until_exam is not None:
            st.caption(
                f"Compte à rebours DNB : {coach.days_until_exam} jour(s) · "
                f"Readiness {coach.readiness_band or '—'}"
            )
        st.link_button(
            f"Ouvrir {COACH_NAME} dans ChatGPT (voix ou texte)",
            url,
            type="primary",
            use_container_width=True,
        )
        st.text_area(
            "Contexte complet envoyé au coach (copie de secours)",
            value=prompt,
            height=220,
            key=f"{key_prefix}_prompt",
        )


def render_chatgpt_voice_sidebar(*, snapshot: StudentDashboardSnapshot | None = None) -> None:
    """Entrée unique Coach Brevet dans la barre latérale élève."""
    voice_context = (
        context_from_snapshot(snapshot) if snapshot is not None else ChatGptVoiceContext(grade_label="3e")
    )
    url = chatgpt_open_url(voice_context)
    st.markdown("---")
    st.caption(SCHOOL_FRAME_MESSAGE)
    st.link_button(f"{COACH_NAME} (ChatGPT)", url, use_container_width=True)
