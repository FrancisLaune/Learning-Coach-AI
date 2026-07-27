from __future__ import annotations

from scripts.audit_ui_language import run
from ui.i18n import (
    PRIORITY_LABELS_FR,
    format_date_fr,
    format_duration,
    format_number_fr,
    grade_label,
    label,
    subject_label,
    tier_label,
)


def test_pedagogical_and_status_labels_are_french() -> None:
    assert label("practice") == "Entraînement"
    assert label("assessment") == "Évaluation"
    assert label("APPROVED") == "Approuvé"
    assert label("KEEP_FOR_REVIEW") == "Maintenir en révision"


def test_subjects_and_school_levels_are_french() -> None:
    assert subject_label("MATHEMATICS") == "Mathématiques"
    assert subject_label("PHYSICS_CHEMISTRY") == "Physique-Chimie"
    assert grade_label("FR-CM1") == "CM1"
    assert grade_label("FR-3E") == "3e"


def test_tier_and_priority_labels_explain_technical_codes() -> None:
    assert tier_label(1) == "Compétence complète (Tier 1)"
    assert "Validation prioritaire" in PRIORITY_LABELS_FR["TIER1_IMMEDIATE"]
    assert "Plan prioritaire" in PRIORITY_LABELS_FR["TIER1_PLAN"]


def test_french_date_number_and_duration_formats() -> None:
    from datetime import date

    assert format_date_fr(date(2026, 7, 26)) == "26/07/2026"
    assert format_number_fr(1250.5, 1) == "1\u00a0250,5"
    assert format_duration(90) == "1 h 30 min"


def test_unknown_technical_identifier_is_not_translated_or_mutated() -> None:
    assert label("skill_id") == "skill_id"
    assert subject_label("CUSTOM_SUBJECT_CODE") == "CUSTOM_SUBJECT_CODE"


def test_static_ui_language_audit_has_no_unjustified_english() -> None:
    result = run()
    assert result["files_analyzed"] >= 12
    assert result["visible_strings_analyzed"] >= 400
    assert result["residual_english_occurrences"] == 0
