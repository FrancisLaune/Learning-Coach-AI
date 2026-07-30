"""LCAI-0018F 5e pipeline preparation tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.lcai_0018f_5e_pipeline import run_5e_publication
from services.content.primary_controlled_publication import load_primary_publication_bundles

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "phase3" / "exports" / "lcai_0018f_5e_publication_manifest.json"


def test_5e_publication_dry_run_builds_manifest(tmp_path: Path) -> None:
    database = tmp_path / "5e-pipeline.duckdb"
    source = ROOT / "data" / "learning_coach_v2.duckdb"
    database.write_bytes(source.read_bytes())
    report = run_5e_publication(execute=False, confirmed=False, database_path=database)
    assert report["scope"] == "FR-5E"
    assert MANIFEST_PATH.exists()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert all(row["grade"] == "FR-5E" for row in manifest)
    if report["execution_manifest_count_5e"] > 0:
        assert all(row["ai_decision"] == "AI_PREVALIDATED_HIGH" for row in manifest)
    else:
        assert report["execution_manifest_count_5e"] == 0


def test_production_mapping_sets_code_for_5e_publication() -> None:
    bundles, _meta = load_primary_publication_bundles()
    for bundle in bundles:
        for slot in ("practice", "assessment"):
            item = bundle.get(slot)
            if item is None or item.get("grade") != "FR-5E":
                continue
            assert item.get("code"), f"missing code on 5e {slot} version {item.get('version_id')}"
            return
    raise AssertionError("no 5e mapped bundle item found")
