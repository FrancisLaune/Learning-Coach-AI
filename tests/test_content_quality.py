from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from domain.content.factory import (
    AnswerKind,
    AnswerSpecification,
)
from domain.learning_session.models import AnswerType, AssessmentMethod
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from scripts.run_content_quality_audit import _candidate_sources
from services.content.factory import CandidateValidator
from services.content.quality import AuditDecision, GateResult, promotion_eligible, qcm_issues, structural_issues
from services.learning_session.assessment import DeterministicAssessmentEngine
from services.learning_session.models import AssessmentRequest
from services.unified_session_execution import UnifiedSessionExecutionService


@pytest.fixture
def quality_database(tmp_path: Path) -> Path:
    source = Path(__file__).parents[1] / "data" / "learning_coach_v2.duckdb"
    target = tmp_path / "quality.duckdb"
    shutil.copy2(source, target)
    return target


def _item(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "program": "P",
        "grade": "FR-4E",
        "subject": "MATHEMATICS",
        "chapter": "CH",
        "skill": "SK",
        "curriculum_relation_count": 1,
        "difficulty": 2,
        "prompt": "Calcule.",
        "explanation": "Une explication suffisamment complète.",
        "stored_answer": "4",
        "payload": {"curriculum_target": {}},
    }
    base.update(changes)
    return base


def _candidate_target(**changes: Any) -> dict[str, Any]:
    target = {
        "program_code": "P",
        "grade_code": "FR-4E",
        "subject_code": "MATHEMATICS",
        "chapter_code": "CH",
        "primary_skill_code": "SK",
    }
    target.update(changes)
    return {"target": target, "language_code": "fr-FR"}


def test_invalid_skill_and_wrong_chapter_skill_relation_are_rejected() -> None:
    issues = structural_issues(
        _item(curriculum_relation_count=0),
        _candidate_target(primary_skill_code="WRONG"),
    )
    assert "invalid_primary_skill_code" in issues
    assert "invalid_chapter_skill_relation" in issues


def test_empty_prompt_and_malformed_answer_are_rejected() -> None:
    issues = structural_issues(_item(prompt=" ", stored_answer=None), _candidate_target())
    assert "empty_prompt" in issues
    assert "malformed_answer" in issues


@pytest.mark.parametrize(
    ("answer", "expected_issue"),
    [
        ({"kind": "single_choice", "expected": "A", "options": []}, "missing_choices"),
        ({"kind": "single_choice", "expected": "A", "options": ["A", " A "]}, "duplicate_choices"),
        ({"kind": "single_choice", "expected": "C", "options": ["A", "B"]}, "correct_answer_not_in_choices"),
    ],
)
def test_qcm_hard_gates_reject_invalid_choices(answer: dict[str, Any], expected_issue: str) -> None:
    assert expected_issue in qcm_issues({"answer": answer}, None)


def test_qcm_choices_are_persisted_and_retrieved(quality_database: Path) -> None:
    repository = DuckDBContentQualityRepository(quality_database)
    inventory = repository.draft_inventory()
    candidates = _candidate_sources()
    item = next(
        row for row in inventory if candidates[row["code"]]["answer"]["kind"] in {"single_choice", "multiple_choice"}
    )
    candidate = candidates[item["code"]]
    repository.persist_qcm_execution_payload(item, candidate)
    persisted = repository.qcm_execution_payload(item["content_id"])
    assert persisted is not None
    assert qcm_issues(candidate, persisted) == ()
    assert persisted["expected_answer"]
    assert any(option["correct"] for option in persisted["options"])


def test_known_correct_incorrect_and_unit_normalization() -> None:
    validator = CandidateValidator()
    from tests.test_content_factory import candidate

    correct = candidate(answer=AnswerSpecification(AnswerKind.NUMERIC, "12,5 cm", independently_computed="12.5 cm"))
    incorrect = candidate(answer=AnswerSpecification(AnswerKind.NUMERIC, "12 cm", independently_computed="13 cm"))
    assert validator.validate(correct).valid
    assert not validator.validate(incorrect).valid


def test_review_or_failed_hard_gate_cannot_enter_approval_workflow() -> None:
    passed = GateResult(True, True, True, True, True, True)
    failed = GateResult(True, False, True, True, True, True)
    assert not promotion_eligible(AuditDecision.REVIEW, 1.0, passed)
    assert not promotion_eligible(AuditDecision.PASS, 1.0, failed)
    assert promotion_eligible(AuditDecision.PASS, 0.97, passed)
    assert promotion_eligible(AuditDecision.PASS, 0.97, passed)


def test_multiple_choice_submission_is_order_independent() -> None:
    answer_type, method = UnifiedSessionExecutionService._strategy("multiple_choice")
    assert (answer_type, method) == (AnswerType.MCQ_MULTI, AssessmentMethod.MCQ)
    result = DeterministicAssessmentEngine().assess(
        AssessmentRequest(
            answer_type,
            ["OPT-2", "OPT-1"],
            ["OPT-1", "OPT-2"],
            method,
            correct_options=("OPT-1", "OPT-2"),
            partial_scoring=False,
        )
    )
    assert result.correct


def test_historical_approved_are_preserved_and_drafts_not_production_ready() -> None:
    repository = DuckDBContentFactoryRepository()
    assert sum(row.approved_count for row in repository.approved_coverage()) == 68
    connection = connect_v2(read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM approved_learning_catalog").fetchone() == (68,)
        assert connection.execute(
            """
            SELECT count(*) FROM approved_learning_catalog alc
            JOIN content_versions cv ON cv.id=alc.content_version_id
            WHERE cv.status<>'approved'
            """
        ).fetchone() == (0,)
    finally:
        connection.close()
