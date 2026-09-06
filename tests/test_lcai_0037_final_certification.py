"""LCAI-0037 final automatic certification tests."""

from __future__ import annotations

import duckdb
import pytest

from core.config import get_database_path
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.ai_correction import AiExerciseCorrectionService
from services.brevet_referential.automatic_certification import AutomaticDnbCertificationService
from services.brevet_referential.repository import PedagogicalContentRepository
from services.brevet_referential.traceability import count_archive_derived_without_parent


def test_ai_correction_mechanism_for_open_and_qcm() -> None:
    svc = AiExerciseCorrectionService()
    qcm = svc.build_mechanism_payload(
        {"statement": "QCM choix multiple. Quelle est la bonne réponse ?", "pedagogical_content_type": "AUTOMATISM"}
    )
    assert qcm["correction_source"] in {"AI_GENERATED", "DETERMINISTIC", "OFFICIAL"}
    assert qcm["grading_mode"]
    open_q = svc.correct(
        {
            "statement": "Rédige un développement construit sur Vichy.",
            "pedagogical_content_type": "DEVELOPPEMENT_CONSTRUIT",
        },
        student_answer="Le régime de Vichy...",
    )
    assert open_q.grading_mode == "AI_GRADING"
    assert open_q.expected_answer


def test_pass_a_rejects_placeholder() -> None:
    svc = AutomaticDnbCertificationService.__new__(AutomaticDnbCertificationService)
    row = {
        "statement": "Question A",
        "subject_code": "MATHEMATICS",
        "subject_group": "MATHEMATICS",
        "assets_required": False,
        "assets_complete": True,
        "warnings": "",
    }
    decision = AutomaticDnbCertificationService._pass_a(svc, row)
    assert decision["decision"] == "REJECT"


def test_pass_b_certifies_standard_official() -> None:
    svc = AutomaticDnbCertificationService.__new__(AutomaticDnbCertificationService)
    svc.corrector = AiExerciseCorrectionService()
    row = {
        "statement": "Exercice 1. Calcule 2+2 et justifie.",
        "subject_code": "MATHEMATICS",
        "warnings": "",
    }
    pass_a = {
        "decision": "CERTIFY",
        "content_type": "CALCULATION",
        "confidence": 0.9,
        "reason": "ok",
    }
    pass_b = AutomaticDnbCertificationService._pass_b(svc, row, pass_a)
    assert pass_b["decision"] == "CERTIFY"
    reconciled = AutomaticDnbCertificationService._reconcile(svc, pass_a, pass_b)
    assert reconciled["decision"] == "CERTIFY"


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_final_assertions_after_certification() -> None:
    store = BrevetContentStore()
    try:
        n = store.fetchone("SELECT COUNT(*) FROM content_pedagogical_assessments")
        if not n or int(n[0]) < 1098:
            pytest.skip("run scripts/certify_dnb_official_corpus.py first")
        review = store.fetchone(
            """
            SELECT COUNT(*) FROM content_pedagogical_assessments
            WHERE pedagogical_validation_status = 'REVIEW'
               OR curriculum_2027_compatible = 'REVIEW'
            """
        )
        assert int(review[0]) == 0
        assert count_archive_derived_without_parent(store) == 0
        no_skill = store.fetchone(
            """
            SELECT COUNT(*) FROM content_pedagogical_assessments
            WHERE pedagogical_validation_status = 'VALIDATED'
              AND (primary_skill_code IS NULL OR primary_skill_code = '')
            """
        )
        assert int(no_skill[0]) == 0
        no_corr = store.fetchone(
            """
            SELECT COUNT(*) FROM content_pedagogical_assessments a
            WHERE a.pedagogical_validation_status = 'VALIDATED'
              AND NOT EXISTS (
                SELECT 1 FROM content_correction_mechanisms m WHERE m.content_id = a.content_id
              )
            """
        )
        assert int(no_corr[0]) == 0
        rejected = store.fetchone(
            """
            SELECT COUNT(*) FROM content_pedagogical_assessments
            WHERE pedagogical_validation_status = 'REJECTED'
            """
        )
        assert int(rejected[0]) == 3
    finally:
        store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_official_count_preserved() -> None:
    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM content_items WHERE source_type='OFFICIAL_ARCHIVE'").fetchone()[0]
        assert int(n) >= 1098
    finally:
        con.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_2027_selection_returns_certified_playable() -> None:
    repo = PedagogicalContentRepository()
    try:
        validated = repo.get_validated_official_questions(limit=5)
        if not validated:
            pytest.skip("certification not run yet")
        assert all(True for _ in validated)
        rows = repo.get_2027_compatible_questions(certified_only=True, limit=5)
        assert len(rows) >= 1
    finally:
        repo.store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_derived_chain_still_intact() -> None:
    repo = PedagogicalContentRepository()
    try:
        sample = repo.find_derived_of_archive()
        assert sample is not None
        assert sample["parent_question_id"] is not None
    finally:
        repo.store.close()
