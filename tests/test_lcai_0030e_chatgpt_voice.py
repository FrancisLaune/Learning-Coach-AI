"""LCAI-0030-E — ChatGPT Voice simple link helpers."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from services.chatgpt_voice import (
    CHATGPT_BASE_URL,
    SCHOOL_FRAME_MESSAGE,
    VOICE_HINT,
    ChatGptVoiceContext,
    build_context_prompt,
    chatgpt_open_url,
)


def test_build_context_prompt_includes_school_profile() -> None:
    prompt = build_context_prompt(
        ChatGptVoiceContext(
            display_name="Michael",
            grade_label="3e",
            subject_label="Mathématiques",
            chapter_label="Fonctions linéaires",
            objective="Préparer le brevet",
        )
    )
    assert "tuteur scolaire" in prompt
    assert "Michael" in prompt
    assert "Mathématiques" in prompt
    assert "Fonctions linéaires" in prompt
    assert prompt.rstrip().endswith("Ma question :")


def test_chatgpt_open_url_prefills_query() -> None:
    url = chatgpt_open_url(ChatGptVoiceContext(subject_label="Histoire", chapter_label="1914-1918"))
    assert url.startswith(CHATGPT_BASE_URL)
    assert "q=" in url
    decoded = unquote(url)
    assert "Histoire" in decoded
    assert "1914-1918" in decoded


def test_chatgpt_open_url_without_context() -> None:
    assert chatgpt_open_url(None) == CHATGPT_BASE_URL


def test_school_frame_and_voice_copy_are_french() -> None:
    assert "scolaire" in SCHOOL_FRAME_MESSAGE.casefold()
    assert "vocal" in VOICE_HINT.casefold()


def test_student_shell_wires_chatgpt_not_professor_banner() -> None:
    root = Path(__file__).resolve().parents[1]
    unified = (root / "ui" / "unified_app.py").read_text(encoding="utf-8")
    home = (root / "ui" / "student_guidance.py").read_text(encoding="utf-8")
    student_fn = unified.split("def run_student")[1].split("def _render_child_management_back")[0]
    assert "render_chatgpt_voice_sidebar" in student_fn
    assert "render_professor_ai_banner" not in student_fn
    assert "render_chatgpt_voice_access" in home
