"""UI — accès ChatGPT Voice simple pour l'élève (LCAI-0030-E)."""

from __future__ import annotations

import streamlit as st

from application.dto.student_guidance import StudentDashboardSnapshot, StudentHomeContext
from services.chatgpt_voice import (
    SCHOOL_FRAME_MESSAGE,
    VOICE_HINT,
    ChatGptVoiceContext,
    build_context_prompt,
    chatgpt_open_url,
    context_from_priorities,
)


def _context_from_home(context: StudentHomeContext) -> ChatGptVoiceContext:
    subject = ""
    chapter = ""
    if context.revision_priorities:
        top = context.revision_priorities[0]
        subject = top.subject_label
        chapter = top.skill_label
    elif context.fragile_skills:
        top_skill = context.fragile_skills[0]
        subject = top_skill.subject_label
        chapter = top_skill.chapter_label or top_skill.label
    return context_from_priorities(
        display_name=context.display_name,
        objective=context.objective,
        subject_label=subject,
        skill_or_chapter=chapter,
    )


def render_chatgpt_voice_access(
    *,
    context: ChatGptVoiceContext | None = None,
    snapshot: StudentDashboardSnapshot | None = None,
    expanded: bool = False,
    key_prefix: str = "chatgpt_voice",
) -> None:
    """Cadre scolaire + lien ChatGPT (nouvel onglet) + prompt copiable."""
    voice_context = context
    if voice_context is None and snapshot is not None:
        voice_context = _context_from_home(snapshot.context)
    if voice_context is None:
        voice_context = ChatGptVoiceContext()

    prompt = build_context_prompt(voice_context)
    url = chatgpt_open_url(voice_context)

    with st.expander("Poser une question (ChatGPT)", expanded=expanded):
        st.info(SCHOOL_FRAME_MESSAGE)
        st.caption(VOICE_HINT)
        st.link_button(
            "Ouvrir ChatGPT (voix ou texte)",
            url,
            type="primary",
            use_container_width=True,
        )
        st.text_area(
            "Contexte à coller si besoin",
            value=prompt,
            height=160,
            key=f"{key_prefix}_prompt",
        )


def render_chatgpt_voice_sidebar(*, snapshot: StudentDashboardSnapshot | None = None) -> None:
    """Entrée discrète dans la barre latérale élève."""
    voice_context = _context_from_home(snapshot.context) if snapshot is not None else ChatGptVoiceContext()
    url = chatgpt_open_url(voice_context)
    st.markdown("---")
    st.caption(SCHOOL_FRAME_MESSAGE)
    st.link_button("ChatGPT — question libre", url, use_container_width=True)
