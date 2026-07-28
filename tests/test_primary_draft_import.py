from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from services.content.primary_controlled_publication import primary_coverage_rows, tier_counts_by_grade
from services.content.primary_draft_import import (
    IMPORT_CAMPAIGN,
    import_primary_drafts,
    load_authoritative_corpus,
    load_excluded_unresolved_codes,
    load_version_mapping,
    reconcile_corpus,
    reconcile_review_counts,
)

ROOT = Path(__file__).parents[1]


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Path:
    target = tmp_path / "learning_coach_v2_test.duckdb"
    shutil.copy2(ROOT / "data" / "learning_coach_v2.duckdb", target)
    return target


def test_authoritative_corpus_counts() -> None:
    importable, corrected, meta = load_authoritative_corpus(database_path=ROOT / "data" / "learning_coach_v2.duckdb")
    excluded = load_excluded_unresolved_codes(corrected, importable)
    assert len(importable) == 1293
    assert len(excluded) == 18
    assert meta["importable_count"] == 1293


def test_dry_run_writes_no_mapping(isolated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_path = tmp_path / "mapping.jsonl"
    monkeypatch.setattr("services.content.primary_draft_import.MAPPING_PATH", mapping_path)
    report = import_primary_drafts(isolated_db, execute=False, campaign=IMPORT_CAMPAIGN)
    assert report["new_drafts_imported"] == 0
    assert report["already_present_identical"] == 1293
    assert not mapping_path.exists()


def test_confirmation_gate_required_for_execute(isolated_db: Path) -> None:
    with pytest.raises(SystemExit):
        from scripts.run_primary_draft_import_0012e import run_import

        run_import(execute=True, confirmed=False, database_path=isolated_db, campaign=IMPORT_CAMPAIGN, skip_backup=True)


def test_execute_import_is_idempotent_on_post_import_clone(
    isolated_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping_path = tmp_path / "mapping.jsonl"
    ledger_path = tmp_path / "ledger.json"
    monkeypatch.setattr("services.content.primary_draft_import.MAPPING_PATH", mapping_path)
    monkeypatch.setattr("services.content.primary_draft_import.LEDGER_PATH", ledger_path)

    tier_before = tier_counts_by_grade(primary_coverage_rows(isolated_db))
    first = import_primary_drafts(isolated_db, execute=True, campaign=IMPORT_CAMPAIGN)
    tier_after = tier_counts_by_grade(primary_coverage_rows(isolated_db))
    assert tier_before == tier_after
    assert first["new_drafts_imported"] == 0
    assert first["already_present_identical"] == 1293
    assert first["failed_imports"] == 0
    assert mapping_path.exists()
    assert len(load_version_mapping(mapping_path)) == 1293

    second = import_primary_drafts(isolated_db, execute=True, campaign=IMPORT_CAMPAIGN)
    assert second["new_drafts_imported"] == 0
    assert second["already_present_identical"] == 1293
    assert len(load_version_mapping(mapping_path)) == 1293


def test_unresolved_curriculum_excluded_from_reconciliation(isolated_db: Path) -> None:
    importable, corrected, _ = load_authoritative_corpus(database_path=isolated_db)
    excluded = load_excluded_unresolved_codes(corrected, importable)
    reconciliation = reconcile_corpus(importable, database_path=isolated_db, excluded_codes=excluded)
    assert reconciliation["status_counts"].get("EXCLUDED_UNRESOLVED_CURRICULUM", 0) == 0
    assert len(excluded) == 18


def test_review_count_reconciliation_passes() -> None:
    counts = reconcile_review_counts()
    assert counts["pass"] is True
    assert counts["initial_candidates"] == 731
    assert counts["total_review_records"] == 949
    assert counts["alternate_reviews"] == 218


def test_campaign_validation_constant() -> None:
    assert IMPORT_CAMPAIGN == "LCAI-0012E-PRIMARY-IMPORT-V1"
