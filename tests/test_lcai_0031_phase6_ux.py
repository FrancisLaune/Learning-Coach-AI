"""LCAI-0031 Phase 6 — UX navigation / dashboards."""

from __future__ import annotations

from pathlib import Path

from services import dnb as dnb_service
from ui.dnb_navigation import (
    PARENT_PAGES,
    STUDENT_PAGES,
    resolve_parent_page,
    resolve_student_page,
)
from ui.dnb_parent_dashboard import project_dnb_band
from ui.navigation import apply_navigation_request, request_navigation


ROOT = Path(__file__).resolve().parents[1]


def test_student_nav_matches_ticket_33() -> None:
    expected = (
        "Accueil",
        "Mon programme",
        "Réviser",
        "S'entraîner",
        "Devoir personnalisé",
        "Sujets Brevet",
        "Brevets blancs",
        "Oral",
        "Mes résultats",
        "Coach Brevet",
    )
    assert STUDENT_PAGES == expected
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    block = source.split("_STUDENT_PAGES = (")[1].split(")")[0]
    for label in expected:
        assert label in block


def test_parent_nav_matches_ticket_33() -> None:
    assert "Vue générale" in PARENT_PAGES
    assert "Préparation Brevet" in PARENT_PAGES
    assert "Contrôle continu" in PARENT_PAGES
    assert "Alertes & recommandations" in PARENT_PAGES
    source = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    assert "PARENT_PAGES" in source
    assert "render_parent_brevet_overview" in source


def test_legacy_aliases_resolve() -> None:
    assert resolve_student_page("Tableau de bord") == "Accueil"
    assert resolve_student_page("Devoirs") == "Devoir personnalisé"
    assert resolve_student_page("Ma séance") == "S'entraîner"
    assert resolve_parent_page("Tableau de bord") == "Vue générale"
    assert resolve_parent_page("Recommandations") == "Alertes & recommandations"


def test_request_navigation_applies_aliases() -> None:
    state: dict[str, object] = {}
    request_navigation(state, "student", "Devoirs")
    apply_navigation_request(state, "student", "unified_student_page", STUDENT_PAGES)
    assert state["unified_student_page"] == "Devoir personnalisé"


def test_exam_pages_build_blueprints() -> None:
    maths = dnb_service.brevet_exam("MATHEMATICS_WRITTEN")
    assert maths.template.label
    mocks = dnb_service.mock_brevet_session(include_oral=False)
    assert len(mocks) >= 3
    project = dnb_service.oral_project(
        title="Test",
        problematique="Pourquoi ?",
        outline=("A", "B"),
    )
    jury = dnb_service.oral_jury_pack(project)
    assert len(jury) >= 3


def test_projection_band_is_a_range() -> None:
    text, confidence = project_dnb_band(0.55)
    assert "–" in text or "-" in text
    assert "/ 20" in text
    assert confidence in {"faible", "moyenne", "élevée"}


def test_multi_level_target_grade_hidden_in_edit_and_wizard() -> None:
    unified = (ROOT / "ui" / "unified_app.py").read_text(encoding="utf-8")
    wizard = (ROOT / "ui" / "parent_child_wizard.py").read_text(encoding="utf-8")
    # Edit learner: no Classe cible selectbox
    edit_fn = unified.split("def _edit_learner")[1].split("def _")[0]
    assert "Classe cible" not in edit_fn or "alignée sur la 3e" in edit_fn
    assert 'st.selectbox(\n            "Classe cible"' not in edit_fn
    assert "Classe cible" not in wizard or "pas de multi-niveaux" in wizard or "Objectif Brevet" in wizard
    assert 'st.selectbox(\n        "Classe cible"' not in wizard


def test_student_home_module_covers_section_29() -> None:
    home = (ROOT / "ui" / "dnb_student_home.py").read_text(encoding="utf-8")
    for needle in (
        "Jours avant le DNB",
        "Readiness",
        "Objectif de la semaine",
        "Progression programme",
        "Points forts",
        "Points faibles",
        "Révisions dues",
        "Prochain Brevet blanc",
        "Message du Coach Brevet",
    ):
        assert needle in home
