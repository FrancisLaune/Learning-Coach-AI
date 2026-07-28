from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from infrastructure.repositories.content_quality import DuckDBContentQualityRepository
from services.content.primary_draft_import import IMPORT_CAMPAIGN, import_primary_drafts, load_version_mapping
from services.content.primary_full_integration import (
    compute_skill_slot_coverage,
    filter_importable_records,
    prepare_corrected_records,
)
from services.content.primary_integration import (
    PRIMARY_GRADES,
    audit_prepared_resources,
    candidate_from_record,
    import_prepared_candidates,
    load_integration_statuses,
    load_prepared_candidates,
)
from services.content.primary_skill_correction import (
    SkillCorrectionClass,
    _chapter_index,
    apply_skill_corrections,
    load_curriculum_placements,
    repair_qcm_duplicate_choices,
    resolve_skill_code,
)

ROOT = Path(__file__).parents[1]


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Path:
    target = tmp_path / "learning_coach_v2_test.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def test_load_prepared_candidates_has_unique_codes() -> None:
    records, meta = load_prepared_candidates()
    assert meta["candidates"] == meta["unique_codes"]
    assert meta["candidates"] >= 1300
    assert all(record["grade"] in PRIMARY_GRADES for record in records)


def test_candidate_from_record_roundtrip() -> None:
    records, _ = load_prepared_candidates()
    candidate = candidate_from_record(records[0]["candidate_data"])
    assert candidate.code == records[0]["code"]
    assert candidate.target.grade_code in PRIMARY_GRADES


def test_prepared_resources_validate_against_curriculum(isolated_db: Path) -> None:
    factory = DuckDBContentFactoryRepository(isolated_db)
    records, _ = load_prepared_candidates()
    audit = audit_prepared_resources(factory, records[:50], integration_statuses=load_integration_statuses())
    assert audit["malformed_records"] == []
    assert audit["curriculum_mapping_errors"] == []


def test_import_is_idempotent(isolated_db: Path) -> None:
    factory = DuckDBContentFactoryRepository(isolated_db)
    records, _ = load_prepared_candidates()
    sample = [record for record in records if record["code"].endswith("-01")][:20]
    statuses = load_integration_statuses()
    first = import_prepared_candidates(factory, sample, integration_statuses=statuses)
    second = import_prepared_candidates(factory, sample, integration_statuses=statuses)
    assert first["counters"]["imported"] + first["counters"]["skipped_existing"] == len(sample)
    assert second["counters"]["imported"] == 0
    assert second["counters"]["skipped_existing"] == len(sample)


def test_imported_drafts_use_primary_author(isolated_db: Path) -> None:
    report = import_primary_drafts(isolated_db, execute=False, campaign=IMPORT_CAMPAIGN)
    assert report["already_present_identical"] == 1293
    mappings = load_version_mapping(
        ROOT / "resources/content/integration/lcai_0012e_isolated_to_production_version_mapping.jsonl"
    )
    assert len(mappings) == 1293


def test_draft_inventory_grade_filter_backward_compatible(isolated_db: Path) -> None:
    quality = DuckDBContentQualityRepository(isolated_db)
    college = quality.draft_inventory()
    primary = quality.draft_inventory(grade_codes=PRIMARY_GRADES)
    assert all(item["grade"] in {"FR-4E", "FR-3E"} for item in college)
    assert all(item["grade"] in PRIMARY_GRADES for item in primary)


def test_deterministic_frencm2_skill_resolution(isolated_db: Path) -> None:
    placements = load_curriculum_placements(isolated_db)
    ci = _chapter_index(placements)
    resolution = resolve_skill_code(
        program_code="FR-CYCLE3-CM2-2026",
        grade_code="FR-CM2",
        subject_code="FRENCH",
        chapter_code="CH-FRENCH-CM2-ORAL",
        primary_skill_code="SK-ENR-FRENCM2-ORAL-LISTEN",
        placements=placements,
        chapter_index=ci,
    )
    assert resolution.classification is SkillCorrectionClass.DETERMINISTIC_FIX
    assert resolution.corrected_skill_code == "SK-ENR-FRENCH-CM2-ORAL-LISTEN"


def test_skill_correction_preserves_original_trace(isolated_db: Path) -> None:
    records, _ = load_prepared_candidates()
    traced = next(
        (
            r
            for r in records
            if r["candidate_data"].get("metadata", {}).get("skill_correction", {}).get("original_primary_skill_code")
        ),
        None,
    )
    if traced is not None:
        meta = traced["candidate_data"]["metadata"]["skill_correction"]
        assert meta["original_primary_skill_code"] != meta["corrected_primary_skill_code"]
        return
    synthetic = {
        "code": "TEST-FRENCM2-TRACE",
        "skill": "SK-ENR-FRENCM2-ORAL-LISTEN",
        "candidate_data": {
            "target": {
                "program_code": "FR-CYCLE3-CM2-2026",
                "grade_code": "FR-CM2",
                "subject_code": "FRENCH",
                "chapter_code": "CH-FRENCH-CM2-ORAL",
                "primary_skill_code": "SK-ENR-FRENCM2-ORAL-LISTEN",
            },
            "metadata": {},
        },
    }
    corrected, report = apply_skill_corrections([synthetic], database_path=isolated_db)
    meta = corrected[0]["candidate_data"]["metadata"]["skill_correction"]
    assert meta["original_primary_skill_code"].startswith("SK-ENR-FRENCM2")
    assert meta["corrected_primary_skill_code"].startswith("SK-ENR-FRENCH-CM2")
    assert report["applied"]


def test_qcm_duplicate_repair(isolated_db: Path) -> None:
    candidate = {
        "answer": {
            "kind": "single_choice",
            "expected": "A",
            "options": ["A", "A", "B", "C"],
        }
    }
    repair = repair_qcm_duplicate_choices(candidate)
    assert repair["status"] == "DETERMINISTIC_FIX"
    assert len(set(repair["candidate_data"]["answer"]["options"])) == 4


def test_gap_formula_no_double_count() -> None:
    results = [
        {"skill": "S1", "content_type": "practice", "decision": "PASS", "confidence": 0.9, "code": "A", "version_id": 1},
        {"skill": "S2", "content_type": "assessment", "decision": "REVIEW", "confidence": 0.8, "code": "B", "version_id": 2},
    ]
    # Uses live curriculum rows — only assert formula structure on synthetic subset via generation_requirements keys
    payload = compute_skill_slot_coverage(results)
    gen = payload["generation_requirements"]
    assert gen["total_new_contents_required"] == (
        2 * gen["skills_missing_both"] + gen["skills_missing_practice_only"] + gen["skills_missing_assessment_only"]
    )


def test_corrected_records_increase_importable_pool(isolated_db: Path) -> None:
    corrected, prep = prepare_corrected_records(database_path=isolated_db)
    importable = filter_importable_records(corrected, database_path=isolated_db)
    counts = prep["skill_corrections"]["counts"]
    deterministic = counts.get("DETERMINISTIC_FIX", 0)
    already_valid = counts.get("ALREADY_VALID", 0)
    assert deterministic >= 200 or already_valid >= 1200
    assert len(importable) >= 1200


def test_integration_script_produces_audit_artifacts(isolated_db: Path) -> None:
    corrected, _ = prepare_corrected_records(database_path=isolated_db)
    factory = DuckDBContentFactoryRepository(isolated_db)
    audit = audit_prepared_resources(factory, corrected, integration_statuses=load_integration_statuses())
    assert len(corrected) >= 1300
    assert len(audit["curriculum_mapping_errors"]) <= 90


def test_5e_semantic_recovery_recovers_majority(isolated_db: Path) -> None:
    from services.content.primary_5e_curriculum_resolution import (
        analyze_unmapped_5e_records,
        filter_importable_records_extended,
        prepare_all_corrected_records,
        resolve_skill_code_semantic,
    )

    analysis = analyze_unmapped_5e_records(database_path=isolated_db)
    assert analysis["unmapped_before"] == 87
    assert analysis["counts_by_class"]["CONTENT_CAN_BE_MAPPED_TO_EXISTING_CLOSE_SKILL"] == 23
    assert analysis["counts_by_class"]["CURRICULUM_DECISION_REQUIRED"] == 5
    corrected, prep = prepare_all_corrected_records(database_path=isolated_db)
    importable = filter_importable_records_extended(corrected, database_path=isolated_db)
    assert len(prep["semantic_5e_corrections"]["applied"]) == 69
    assert len(prep["semantic_5e_corrections"]["exceptions"]) == 18
    assert len(importable) >= 1290

    hist = resolve_skill_code_semantic(
        program_code="FR-CYCLE4-5E-2026",
        grade_code="FR-5E",
        subject_code="HISTORY",
        chapter_code="CH-HISTORY-5E-SOCIETY",
        primary_skill_code="SK-ENR-HISTORY-5E-SOCIETY-CHURCH",
        prompt="place de l'Église",
    )
    assert hist.corrected_skill_code == "SK-ENR-HISTORY-5E-FEUDAL-CHURCH"
    assert hist.corrected_chapter_code == "CH-HISTORY-5E-FEUDAL"


def test_blocked_qcm_repair_allows_import(isolated_db: Path) -> None:
    from services.content.primary_5e_curriculum_resolution import _qcm_structurally_valid
    from services.content.primary_skill_correction import repair_qcm_duplicate_choices

    blocked = {
        "answer": {
            "kind": "single_choice",
            "expected": "beaucoup",
            "options": ["bocou", "beaucoup", "beaucoups", "beaucoup"],
        }
    }
    repair = repair_qcm_duplicate_choices(blocked)
    assert repair["status"] == "DETERMINISTIC_FIX"
    assert _qcm_structurally_valid(repair["candidate_data"])
