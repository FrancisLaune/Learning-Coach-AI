"""LCAI-0031 Phase 4 — Brevet exams, archives, mocks, oral."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.dnb.archives import ArchiveProvenance, assert_not_official_ai, seed_archive_catalog
from domain.dnb.exam_builder import build_brevet_exam, build_global_mock_exam, choose_science_pair
from domain.dnb.exam_templates import BrevetExamCode, BrevetExamMode, mathematics_template
from domain.dnb.oral import build_oral_project, generate_jury_questions
from domain.dnb.prioritizer import BrevetImportance, SkillPriorityInput
from infrastructure.database.v2 import connect_v2
from migrations.runner import apply_migrations
from services import dnb as dnb_service


def test_maths_template_has_automatisms_without_calculator() -> None:
    template = mathematics_template()
    auto = template.sections[0]
    assert auto.code == "AUTOMATISMS"
    assert auto.calculator_allowed is False
    assert auto.max_points == 6
    assert template.sections[1].code == "REASONING"
    assert template.allows_immediate_hints is False


def test_build_brevet_maths_style_exam() -> None:
    blueprint = build_brevet_exam(BrevetExamCode.MATHEMATICS, mode=BrevetExamMode.BREVET_STYLE)
    assert blueprint.template.exam_code is BrevetExamCode.MATHEMATICS
    assert "AUTOMATISMS" in blueprint.template.section_codes
    assert any("sans calculatrice" in rule.casefold() for rule in blueprint.rules)
    assert "non officiel" in blueprint.provenance_note.casefold() or "type" in blueprint.provenance_note.casefold()


def test_sciences_pair_must_be_two_of_three() -> None:
    pair = choose_science_pair(preferred=("SVT", "TECHNOLOGY"))
    assert pair == ("SVT", "TECHNOLOGY")
    with pytest.raises(ValueError):
        choose_science_pair(preferred=("SVT", "SVT"))
    blueprint = build_brevet_exam(
        BrevetExamCode.SCIENCES,
        mode=BrevetExamMode.MOCK_EXAM,
        science_pair=("PHYSICS_CHEMISTRY", "TECHNOLOGY"),
    )
    assert blueprint.selected_science_pair == ("PHYSICS_CHEMISTRY", "TECHNOLOGY")
    assert len(blueprint.section_plan) == 2


def test_adaptive_brevet_uses_priority_skills() -> None:
    priorities = (
        SkillPriorityInput(11, "Équations", 30, BrevetImportance.CRITICAL),
        SkillPriorityInput(12, "Thalès", 40, BrevetImportance.HIGH),
    )
    ranked = dnb_service.skill_priorities(priorities, limit=2)
    blueprint = build_brevet_exam(
        BrevetExamCode.MATHEMATICS,
        mode=BrevetExamMode.ADAPTIVE_BREVET,
        priorities=ranked,
    )
    assert 11 in blueprint.target_skill_ids


def test_global_mock_includes_four_writtens() -> None:
    session = build_global_mock_exam(include_oral=True)
    codes = [item.template.exam_code for item in session]
    assert BrevetExamCode.FRENCH in codes
    assert BrevetExamCode.MATHEMATICS in codes
    assert BrevetExamCode.ORAL in codes
    assert len(session) == 5


def test_archives_are_official_and_ai_cannot_impersonate() -> None:
    seeds = seed_archive_catalog()
    assert all(item.is_official() for item in seeds)
    assert_not_official_ai(ArchiveProvenance.GENERATED_MOCK_EXAM, is_ai_generated=True)
    with pytest.raises(ValueError):
        assert_not_official_ai(ArchiveProvenance.OFFICIAL_EXAM, is_ai_generated=True)


def test_oral_project_and_jury_questions() -> None:
    project = build_oral_project(
        title="Mon stage en entreprise",
        problematique="En quoi ce stage a-t-il développé mon autonomie ?",
        outline=("Contexte", "Compétences", "Bilan"),
    )
    questions = generate_jury_questions(project)
    assert len(project.stages) >= 8
    assert len(questions) == 5
    assert "jury" in questions[-2].prompt.casefold() or "contre-argument" in questions[-2].prompt.casefold()


def test_dnb_service_phase4_facade() -> None:
    exam = dnb_service.brevet_exam("MATHEMATICS_WRITTEN", mode="BREVET_STYLE")
    assert exam.template.duration_minutes == 120
    mocks = dnb_service.mock_brevet_session(include_oral=False)
    assert len(mocks) == 4
    oral = dnb_service.oral_project(
        title="Projet EPI",
        problematique="Comment convaincre un jury ?",
        outline=("Intro", "Développement", "Conclusion"),
    )
    assert dnb_service.oral_jury_pack(oral)
    assert len(dnb_service.official_archive_seeds()) >= 3


def test_migration_029_brevet_tables(tmp_path: Path) -> None:
    path = tmp_path / "p4.duckdb"
    applied = apply_migrations(path)
    assert any(item.version == 29 for item in applied)
    connection = connect_v2(path, read_only=True)
    try:
        templates = connection.execute("SELECT COUNT(*) FROM brevet_exam_templates").fetchone()[0]
        archives = connection.execute("SELECT COUNT(*) FROM exam_archives").fetchone()[0]
        assert int(templates) >= 5
        assert int(archives) >= 3
        provenance = connection.execute(
            "SELECT provenance FROM exam_archives WHERE archive_code='DNB-2026-METROPOLE-MATHS'"
        ).fetchone()[0]
        assert str(provenance) == "OFFICIAL_EXAM"
    finally:
        connection.close()
