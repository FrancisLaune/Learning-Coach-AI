"""LCAI-0018D CM2 pipeline preparation tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.lcai_0018d_cm2_pipeline import run_cm2_publication
from services.content.primary_controlled_publication import load_primary_publication_bundles

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "phase3" / "exports" / "lcai_0018d_cm2_publication_manifest.json"


def test_cm2_publication_dry_run_builds_manifest(tmp_path: Path) -> None:
    database = tmp_path / "cm2-pipeline.duckdb"
    source = ROOT / "data" / "learning_coach_v2.duckdb"
    database.write_bytes(source.read_bytes())
    report = run_cm2_publication(execute=False, confirmed=False, database_path=database)
    assert report["scope"] == "FR-CM2"
    assert MANIFEST_PATH.exists()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert all(row["grade"] == "FR-CM2" for row in manifest)
    if report["execution_manifest_count_cm2"] > 0:
        assert all(row["ai_decision"] == "AI_PREVALIDATED_HIGH" for row in manifest)
    else:
        assert int(report.get("already_published", 0)) >= 44


def test_production_mapping_sets_code_for_cm2_publication() -> None:
    bundles, _meta = load_primary_publication_bundles()
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None or item.get("grade") != "FR-CM2":
                continue
            assert item.get("code"), f"missing code on CM2 {slot} version {item.get('version_id')}"
            return
    raise AssertionError("no CM2 mapped bundle item found")
