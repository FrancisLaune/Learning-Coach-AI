from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from domain.content.factory import (
    DIFFICULTY_PROFILES,
    AnswerKind,
    AnswerSpecification,
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    GeneratedContentCandidate,
    GenerationProvenance,
    IssueSeverity,
    PedagogicalIntent,
    normalized_content_fingerprint,
)
from infrastructure.database.v2 import connect_v2
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from services.content.factory import CandidateValidator, ContentCoverageService, ContentFactoryService, QualityAssessor

TARGET = CurriculumTarget("FR-COLLEGE-2025", "5e", "MATHEMATICS", "CHAPTER", "SKILL", "SUBSKILL")
PROVENANCE = GenerationProvenance("fake", "deterministic-test", "1", "template-1", "curriculum-1")


def candidate(**changes: Any) -> GeneratedContentCandidate:
    base = GeneratedContentCandidate(
        "FACTORY-1",
        "Proportionnalité",
        "Calcule puis justifie.",
        "Un article coûte 80 €. Quel est son prix après une remise de 25 % ?",
        AnswerSpecification(AnswerKind.NUMERIC, 60, independently_computed=60),
        "25 % de 80 vaut 20 ; 80 - 20 = 60.",
        TARGET,
        CanonicalContentType.PRACTICE,
        PedagogicalIntent.PRACTICE,
        2,
        PROVENANCE,
        ("Calcule d'abord le montant de la remise.",),
        family_code="percentage-discount",
        variant_role="independent",
    )
    return replace(base, **changes)


class FakeRepository:
    def __init__(
        self, errors: tuple[str, ...] = (), fingerprints: dict[str, tuple[str | None, str | None]] | None = None
    ) -> None:
        self.errors = errors
        self.fingerprints = fingerprints or {}
        self.persisted: list[GeneratedContentCandidate] = []

    def validate_target(self, target: object) -> tuple[str, ...]:
        return self.errors

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        return dict(self.fingerprints)

    def persist_draft(self, item: GeneratedContentCandidate, author: str) -> None:
        self.persisted.append(item)


class FakeGenerator:
    def __init__(self, *items: GeneratedContentCandidate) -> None:
        self.items = items

    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]:
        return self.items


def request(quantity: int = 1) -> ContentGenerationRequest:
    return ContentGenerationRequest(
        TARGET,
        CanonicalContentType.PRACTICE,
        2,
        PedagogicalIntent.PRACTICE,
        quantity,
    )


def test_taxonomy_and_grade_relative_difficulty_profiles() -> None:
    assert len(CanonicalContentType) == 9
    assert {profile.level for profile in DIFFICULTY_PROFILES.values()} == {1, 2, 3}
    assert DIFFICULTY_PROFILES[1].autonomy != DIFFICULTY_PROFILES[3].autonomy
    with pytest.raises(ValueError, match="between 1 and 3"):
        request().__class__(TARGET, CanonicalContentType.PRACTICE, 4, PedagogicalIntent.PRACTICE)


def test_request_requires_primary_skill_and_valid_quantity() -> None:
    with pytest.raises(ValueError, match="primary Skill"):
        request().__class__(
            replace(TARGET, primary_skill_code=""), CanonicalContentType.PRACTICE, 2, PedagogicalIntent.PRACTICE
        )
    with pytest.raises(ValueError, match="quantity"):
        request(101)


def test_candidate_validation_detects_schema_answer_and_security_errors() -> None:
    broken = candidate(
        prompt="<script>alert(1)</script>",
        explanation="",
        answer=AnswerSpecification(AnswerKind.NUMERIC, 61, independently_computed=60),
    )
    report = CandidateValidator().validate(broken)
    assert not report.valid
    assert {issue.code for issue in report.issues} >= {"missing_explanation", "answer_contradiction", "unsafe_content"}


def test_validator_accepts_one_numeric_value_with_decimal_comma_and_unit() -> None:
    item = candidate(answer=AnswerSpecification(AnswerKind.NUMERIC, "43,35 €", independently_computed="43.35"))
    assert CandidateValidator().validate(item).valid


def test_validator_rejects_explanation_or_list_in_numeric_answer() -> None:
    verbose = candidate(
        answer=AnswerSpecification(
            AnswerKind.NUMERIC,
            "43,35 € avec le calcul 42,50 × 1,02",
            independently_computed="43.35",
        )
    )
    listed = candidate(
        answer=AnswerSpecification(
            AnswerKind.NUMERIC,
            "288, 486, 648",
            independently_computed="288, 486, 648",
        )
    )
    assert "invalid_numeric_format" in {issue.code for issue in CandidateValidator().validate(verbose).issues}
    assert "invalid_numeric_format" in {issue.code for issue in CandidateValidator().validate(listed).issues}


def test_choice_answer_validation_is_deterministic() -> None:
    broken = candidate(answer=AnswerSpecification(AnswerKind.SINGLE_CHOICE, "C", ("A", "A")))
    assert {issue.code for issue in CandidateValidator().validate(broken).issues} == {
        "invalid_choices",
        "answer_not_in_choices",
    }


def test_curriculum_and_subskill_errors_block_generation() -> None:
    repository = FakeRepository(("Sub-skill does not belong to primary Skill",))
    report = ContentFactoryService(FakeGenerator(candidate()), repository).generate_drafts(request(), "author")
    assert report.persisted_as_draft == 0
    assert report.rejected == 1
    assert not repository.persisted


def test_normalized_duplicate_is_rejected() -> None:
    fingerprint = normalized_content_fingerprint(candidate().prompt.upper() + " !!!")
    repository = FakeRepository(fingerprints={fingerprint: (None, None)})
    report = ContentFactoryService(FakeGenerator(candidate()), repository).generate_drafts(request(), "author")
    assert report.duplicates == 1
    assert report.persisted_as_draft == 0


def test_declared_guided_evaluative_variant_is_not_an_accidental_duplicate() -> None:
    item = candidate(variant_role="guided", content_type=CanonicalContentType.GUIDED_PRACTICE)
    known: dict[str, tuple[str | None, str | None]] = {
        normalized_content_fingerprint(item.prompt): (item.family_code, "evaluative")
    }
    report = CandidateValidator().validate(item, known_fingerprints=known)
    assert report.valid
    assert any(issue.code == "intentional_variant" and issue.severity is IssueSeverity.INFO for issue in report.issues)


def test_valid_candidate_is_persisted_only_as_draft_boundary() -> None:
    repository = FakeRepository()
    report = ContentFactoryService(FakeGenerator(candidate()), repository).generate_drafts(request(), "author")
    assert report == replace(report, persisted_as_draft=1)
    assert [item.code for item in repository.persisted] == ["FACTORY-1"]


def test_quality_score_cannot_hide_fatal_error() -> None:
    item = candidate()
    validation = CandidateValidator().validate(item, target_errors=("Unknown Skill",))
    quality = QualityAssessor().assess(item, validation)
    assert quality.score > 0
    assert not quality.eligible_for_review
    assert "invalid_curriculum_target" in quality.blocking_errors


def test_generator_contract_handles_wrong_answer_and_partial_batch() -> None:
    repository = FakeRepository()
    invalid = candidate(code="BAD", answer=AnswerSpecification(AnswerKind.NUMERIC, 5, independently_computed=6))
    valid = candidate(
        code="GOOD",
        prompt="Calcule 50 % de 20.",
        answer=AnswerSpecification(AnswerKind.NUMERIC, 10, independently_computed=10),
    )
    report = ContentFactoryService(FakeGenerator(invalid, valid), repository).generate_drafts(request(2), "author")
    assert (report.generated, report.valid, report.rejected, report.persisted_as_draft) == (2, 1, 1, 1)


def test_coverage_gap_analysis_does_not_generate() -> None:
    from services.content.factory import CoverageRow

    rows = (
        CoverageRow("P", "5e", "M", "C", "S0", 0, {}, {}),
        CoverageRow("P", "5e", "M", "C", "S1", 1, {"practice": 1}, {2: 1}),
    )

    class CoverageFake:
        def approved_coverage(self) -> tuple[CoverageRow, ...]:
            return rows

    service = ContentCoverageService(CoverageFake())
    assert [row.skill_code for row in service.zero_coverage()] == ["S0"]
    assert service.gaps()["missing_assessment"] == ("S0", "S1")


def test_real_curriculum_coverage_and_subskill_targeting() -> None:
    repository = DuckDBContentFactoryRepository()
    real_target = CurriculumTarget(
        "FR-CYCLE4-4E",
        "FR-4E",
        "MATHEMATICS",
        "CH-MATHEMATICS-4E-RELNUM",
        "SK-MATHEMATICS-4E-RELNUM",
        "SUB-MATHEMATICS-4E-RELNUM",
    )
    assert repository.validate_target(real_target) == ()
    assert repository.validate_target(replace(real_target, subskill_code="UNKNOWN"))
    rows = repository.approved_coverage()
    assert len(rows) == 919
    assert sum(row.approved_count > 0 for row in rows) == 34
    assert sum(row.approved_count for row in rows) == 68


def test_duckdb_adapter_persists_candidate_as_draft_without_approval(tmp_path: Path) -> None:
    database = tmp_path / "factory.duckdb"
    shutil.copy2("data/learning_coach_v2.duckdb", database)
    repository = DuckDBContentFactoryRepository(database)
    real_target = CurriculumTarget(
        "FR-CYCLE4-4E",
        "FR-4E",
        "MATHEMATICS",
        "CH-MATHEMATICS-4E-RELNUM",
        "SK-MATHEMATICS-4E-RELNUM",
        "SUB-MATHEMATICS-4E-RELNUM",
    )
    item = candidate(code="FACTORY-DRAFT-TEST", target=real_target)
    before = sum(row.approved_count for row in repository.approved_coverage())
    repository.persist_draft(item, "factory-test")
    connection = connect_v2(database, read_only=True)
    try:
        assert connection.execute("SELECT status FROM exercises WHERE code='FACTORY-DRAFT-TEST'").fetchone() == (
            "draft",
        )
        assert connection.execute(
            "SELECT status FROM content_versions WHERE entity_type='exercise' "
            "AND entity_id=(SELECT id FROM exercises WHERE code='FACTORY-DRAFT-TEST')"
        ).fetchone() == ("draft",)
        assert connection.execute(
            "SELECT count(*) FROM approved_learning_catalog WHERE stable_code='FACTORY-DRAFT-TEST'"
        ).fetchone() == (0,)
    finally:
        connection.close()
    assert sum(row.approved_count for row in repository.approved_coverage()) == before
