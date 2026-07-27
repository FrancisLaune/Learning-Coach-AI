from __future__ import annotations

from collections import Counter
from dataclasses import replace

from domain.content.factory import (
    AnswerSpecification,
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    GeneratedContentCandidate,
    PedagogicalIntent,
)
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from services.content.factory import CandidateValidator, ContentFactoryService
from services.content.pilot import DeterministicPilotGenerator, pilot_specifications


def _request(
    target: CurriculumTarget,
    content_type: CanonicalContentType = CanonicalContentType.PRACTICE,
    difficulty: int = 2,
    quantity: int = 1,
) -> ContentGenerationRequest:
    intent = {
        CanonicalContentType.WORKED_EXAMPLE: PedagogicalIntent.MODEL,
        CanonicalContentType.GUIDED_PRACTICE: PedagogicalIntent.SCAFFOLD,
        CanonicalContentType.PRACTICE: PedagogicalIntent.PRACTICE,
        CanonicalContentType.ASSESSMENT: PedagogicalIntent.CHECK,
        CanonicalContentType.DIAGNOSTIC: PedagogicalIntent.DIAGNOSE,
        CanonicalContentType.REMEDIATION: PedagogicalIntent.REMEDIATE,
        CanonicalContentType.CHALLENGE: PedagogicalIntent.EXTEND,
        CanonicalContentType.REVISION: PedagogicalIntent.CONSOLIDATE,
        CanonicalContentType.LESSON: PedagogicalIntent.INTRODUCE,
    }[content_type]
    return ContentGenerationRequest(target, content_type, difficulty, intent, quantity)


class _MemoryRepository:
    def __init__(self) -> None:
        self.persisted: list[GeneratedContentCandidate] = []

    def validate_target(self, target: object) -> tuple[str, ...]:
        return ()

    def known_fingerprints(self) -> dict[str, tuple[str | None, str | None]]:
        return {}

    def persist_draft(self, candidate: GeneratedContentCandidate, author: str) -> None:
        self.persisted.append(candidate)


def test_approved_pilot_scope_is_exact_and_cross_disciplinary() -> None:
    specifications = pilot_specifications()
    assert len(specifications) == 24
    assert Counter(item.target.grade_code for item in specifications) == {"FR-4E": 12, "FR-3E": 12}
    subjects = Counter(item.target.subject_code for item in specifications)
    assert subjects["MATHEMATICS"] == 8
    assert subjects["FRENCH"] == 8
    assert sum(count for subject, count in subjects.items() if subject not in {"MATHEMATICS", "FRENCH"}) == 8
    assert set(subjects) >= {"ENGLISH", "SPANISH", "HISTORY", "GEOGRAPHY", "SVT", "PHYSICS_CHEMISTRY", "EMC"}


def test_scope_preserves_initial_six_covered_skills_after_human_approvals() -> None:
    coverage = {row.skill_code: row.approved_count for row in DuckDBContentFactoryRepository().approved_coverage()}
    counts = Counter(coverage[item.target.primary_skill_code] > 0 for item in pilot_specifications())
    assert sum(counts.values()) == 24
    assert counts[True] >= 6


def test_every_pilot_target_resolves_exactly_in_curriculum() -> None:
    repository = DuckDBContentFactoryRepository()
    assert all(repository.validate_target(item.target) == () for item in pilot_specifications())


def test_deterministic_generator_propagates_type_and_difficulty() -> None:
    specification = pilot_specifications()[0]
    generator = DeterministicPilotGenerator((specification,))
    for content_type in CanonicalContentType:
        for difficulty in (1, 2, 3):
            candidate = generator.generate(_request(specification.target, content_type, difficulty))[0]
            assert candidate.content_type is content_type
            assert candidate.difficulty == difficulty
            assert candidate.target == specification.target


def test_difficulty_progression_changes_reasoning_not_only_numbers() -> None:
    generator = DeterministicPilotGenerator(pilot_specifications())
    for specification in pilot_specifications()[:5]:
        candidates = [
            generator.generate(_request(specification.target, CanonicalContentType.PRACTICE, level))[0]
            for level in (1, 2, 3)
        ]
        assert len({candidate.prompt for candidate in candidates}) == 3
        assert "raisonnement" in candidates[2].metadata["difficulty_basis"]
        assert candidates[0].metadata["difficulty_basis"] != candidates[2].metadata["difficulty_basis"]


def test_math_french_language_humanities_and_science_candidates_validate() -> None:
    specifications = pilot_specifications()
    generator = DeterministicPilotGenerator(specifications)
    selected_subjects = {"MATHEMATICS", "FRENCH", "ENGLISH", "HISTORY", "SVT"}
    for specification in specifications:
        if specification.target.subject_code in selected_subjects:
            candidate = generator.generate(_request(specification.target))[0]
            assert CandidateValidator().validate(candidate).valid


def test_diagnostic_and_remediation_share_a_misconception_target() -> None:
    specification = pilot_specifications()[0]
    generator = DeterministicPilotGenerator((specification,))
    diagnostic_request = _request(specification.target, CanonicalContentType.DIAGNOSTIC, 1)
    remediation_request = _request(specification.target, CanonicalContentType.REMEDIATION, 1)
    diagnostic = generator.generate(diagnostic_request)[0]
    remediation = generator.generate(remediation_request)[0]
    assert remediation.misconception_target == specification.misconception
    assert diagnostic.family_code == remediation.family_code
    assert diagnostic.variant_role != remediation.variant_role


def test_same_skill_variation_is_meaningful() -> None:
    specification = pilot_specifications()[1]
    generator = DeterministicPilotGenerator((specification,))
    candidates = [
        generator.generate(_request(specification.target, CanonicalContentType.PRACTICE, level))[0]
        for level in (1, 2, 3)
    ]
    assert len({candidate.prompt for candidate in candidates}) == 3
    assert len({candidate.explanation for candidate in candidates}) == 3


def test_invalid_answer_is_rejected_then_one_controlled_retry_succeeds() -> None:
    specification = pilot_specifications()[0]
    valid = DeterministicPilotGenerator((specification,)).generate(_request(specification.target))[0]
    invalid = replace(
        valid,
        answer=AnswerSpecification(
            valid.answer.kind,
            valid.answer.expected,
            independently_computed="contradiction",
        ),
    )
    validator = CandidateValidator()
    assert not validator.validate(invalid).valid
    assert validator.validate(valid).valid


def test_technical_orchestration_persists_valid_candidate_as_draft_boundary() -> None:
    specification = pilot_specifications()[0]
    repository = _MemoryRepository()
    service = ContentFactoryService(DeterministicPilotGenerator((specification,)), repository)
    report = service.generate_drafts(_request(specification.target), "test")
    assert report.persisted_as_draft == 1
    assert len(repository.persisted) == 1


def test_assessment_has_no_hint_while_guided_practice_has_scaffolding() -> None:
    specification = pilot_specifications()[0]
    generator = DeterministicPilotGenerator((specification,))
    assessment = generator.generate(_request(specification.target, CanonicalContentType.ASSESSMENT, 2))[0]
    guided = generator.generate(_request(specification.target, CanonicalContentType.GUIDED_PRACTICE, 2))[0]
    assert assessment.hints == ()
    assert guided.hints
    assert assessment.instructions != guided.instructions


def test_generator_provenance_is_versioned_and_provider_independent() -> None:
    specification = pilot_specifications()[0]
    candidate = DeterministicPilotGenerator((specification,)).generate(_request(specification.target))[0]
    assert candidate.provenance.template_version == "lcai-0012b-template-v1"
    assert candidate.provenance.generator_type == "deterministic_template"
