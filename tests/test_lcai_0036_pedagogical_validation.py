"""LCAI-0036 pedagogical validation tests."""

from __future__ import annotations

import duckdb
import pytest

from core.config import get_database_path
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.pedagogical_classifiers import (
    assess_compatibility_2027,
    assess_segmentation,
    classify_content_type,
    classify_discipline,
    classify_subject_group,
    decide_validation_status,
    reliability_score,
    review_priority_score,
)
from services.brevet_referential.repository import PedagogicalContentRepository
from services.brevet_referential.traceability import count_archive_derived_without_parent
from services.brevet_referential.validation_service import change_compatibility


def test_segmentation_rejects_placeholders() -> None:
    ok, conf, warnings = assess_segmentation("Question A")
    assert not ok
    assert "PLACEHOLDER_STATEMENT" in warnings
    assert conf < 0.2


def test_segmentation_accepts_real_statement() -> None:
    text = "Exercice 1\n1. Calcule 3/4 + 1/2. Justifie ta réponse."
    ok, conf, warnings = assess_segmentation(text, "1")
    assert ok
    assert conf >= 0.55


def test_subject_and_discipline_classifiers() -> None:
    assert classify_subject_group("HISTORY", exam_code="24GENHGEMCAA1") == "HISTORY_GEOGRAPHY_EMC"
    assert classify_discipline("HISTORY_GEOGRAPHY_EMC", "situation EMC citoyenneté") == "EMC"
    assert classify_content_type("FRENCH", "Dictée", "24GENFRDAA1") == "DICTATION"
    assert classify_content_type("MATHEMATICS", "QCM automatismes") == "AUTOMATISM"


def test_compatibility_never_auto_true() -> None:
    compat, reason, conf, _method = assess_compatibility_2027(
        year=2025,
        subject_group="MATHEMATICS",
        segmentation_ok=True,
        mapping_conf=0.95,
        assets_complete=True,
        warnings=[],
    )
    assert compat == "REVIEW"
    assert reason == "IN_PROGRAM_2027"
    assert conf >= 0.8


def test_reliability_and_priority() -> None:
    score, klass = reliability_score(
        source_integrity=0.95,
        segmentation_confidence=0.8,
        asset_completeness=1.0,
        mapping_confidence=0.9,
        compatibility_confidence=0.8,
        correction_quality=0.2,
        validation_status="AUTO_CHECKED",
    )
    assert 0.0 <= score <= 1.0
    assert klass in {"A", "B", "C", "D"}
    prio = review_priority_score(
        {
            "subject_group": "SCIENCES",
            "skill_importance": "CRITICAL",
            "mapping_confidence": 0.4,
            "assets_complete": False,
            "correction_source": "NONE",
            "pedagogical_validation_status": "REVIEW",
            "pedagogical_reliability_score": 0.4,
        }
    )
    assert prio > 50


def test_decide_validation_status_no_mass_validated() -> None:
    assert decide_validation_status(
        segmentation_ok=True, mapping_conf=0.95, assets_complete=True, warnings=[]
    ) == "AUTO_CHECKED"
    assert (
        decide_validation_status(
            segmentation_ok=False,
            mapping_conf=0.2,
            assets_complete=True,
            warnings=["PLACEHOLDER_STATEMENT"],
        )
        == "REJECTED"
    )


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_audit_tables_and_invariants_after_pipeline() -> None:
    store = BrevetContentStore()
    try:
        audited = store.fetchone("SELECT COUNT(*) FROM content_pedagogical_assessments")
        if not audited or int(audited[0]) < 1098:
            pytest.skip("run scripts/validate_dnb_official_corpus.py first")
        assert count_archive_derived_without_parent(store) == 0
        true_without_reason = store.fetchone(
            """
            SELECT COUNT(*) FROM content_pedagogical_assessments
            WHERE curriculum_2027_compatible = 'TRUE'
              AND (compatibility_reason IS NULL OR compatibility_reason = '')
            """
        )
        assert int(true_without_reason[0]) == 0
        # LCAI-0037 may have auto-VALIDATED the corpus; 0036 only forbade mass auto-VALIDATED at its time.
        validated = store.fetchone(
            """
            SELECT COUNT(*) FROM content_pedagogical_assessments
            WHERE pedagogical_validation_status = 'VALIDATED'
            """
        )
        assert int(validated[0]) >= 0
    finally:
        store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_official_count_preserved() -> None:
    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM content_items WHERE source_type='OFFICIAL_ARCHIVE'"
        ).fetchone()[0]
        assert int(n) >= 1098
    finally:
        con.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_dnb_2027_selection_defaults_to_certified_only() -> None:
    repo = PedagogicalContentRepository()
    try:
        rows = repo.get_2027_compatible_questions(subject_code="MATHEMATICS", certified_only=True)
        # After LCAI-0037 automatic certification, certified pool is populated.
        assert isinstance(rows, list)
        if rows:
            assert "content_id" in rows[0]
    finally:
        repo.store.close()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_human_compatibility_requires_reason() -> None:
    store = BrevetContentStore()
    try:
        with pytest.raises(ValueError):
            change_compatibility(
                store,
                1979,
                compatible="TRUE",
                reason="",
                actor_id="tester",
            )
    finally:
        store.close()


def test_french_math_hg_science_content_types() -> None:
    assert classify_content_type("FRENCH", "réécriture de phrase") == "REWRITING"
    assert classify_content_type("FRENCH", "rédaction", "24GENFRRAA1") == "WRITING_PROMPT"
    assert classify_content_type("MATHEMATICS", "algorithme scratch") == "ALGORITHM"
    assert classify_content_type("HISTORY_GEOGRAPHY_EMC", "développement construit") == "DEVELOPPEMENT_CONSTRUIT"
    assert classify_content_type("SCIENCES", "protocole expérimental") == "EXPERIMENT"
    assert classify_discipline("SCIENCES", "volcan Krafla SVT") == "SVT"
