"""LCAI-0033 audit script tests — read-only guarantees and artefact generation."""
from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb
import pytest

from core.config import get_database_path, get_v2_database_path
from scripts.audit_lcai_0033 import run_audit, sha256_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def audit_result(tmp_path_factory: pytest.TempPathFactory) -> dict:
    if not get_database_path().exists() or not get_v2_database_path().exists():
        pytest.skip("runtime DBs not available")
    out = tmp_path_factory.mktemp("lcai0033")
    ob_before = sha256_file(get_database_path())
    v2_before = sha256_file(get_v2_database_path())
    manifest = run_audit(output_root=out)
    assert sha256_file(get_database_path()) == ob_before
    assert sha256_file(get_v2_database_path()) == v2_before
    manifest["_out"] = out
    return manifest


def test_sources_unmodified(audit_result: dict) -> None:
    assert audit_result["sources_unmodified"] is True


def test_required_exports_exist(audit_result: dict) -> None:
    out: Path = audit_result["_out"]
    exports = out / "exports"
    required = [
        "LCAI-0033_DATABASE_STATE.md",
        "LCAI-0033_DATABASE_SCHEMA.md",
        "LCAI-0033_DATA_SOURCE_INVENTORY.csv",
        "LCAI-0033_TABLE_INVENTORY.csv",
        "LCAI-0033_COLUMN_INVENTORY.csv",
        "LCAI-0033_CONTENT_BY_SUBJECT.csv",
        "LCAI-0033_CONTENT_BY_SKILL.csv",
        "LCAI-0033_EXERCISE_CATALOG.csv",
        "LCAI-0033_EDUSCOL_SOURCE_AUDIT.md",
        "LCAI-0033_DNB_ARCHIVE_COVERAGE.csv",
        "LCAI-0033_BREVET_DERIVATION_AUDIT.csv",
        "LCAI-0033_CODE_CONTENT_AUDIT.csv",
        "LCAI-0033_EXACT_DUPLICATES.csv",
        "LCAI-0033_NEAR_DUPLICATES.csv",
        "LCAI-0033_UNPLAYABLE_CONTENT.csv",
        "LCAI-0033_HOMEWORK_CAPACITY.csv",
        "LCAI-0033_CONTENT_SAMPLE.json",
        "LCAI-0033_SCHEMA_DUMP.sql",
        "LCAI-0033_AUDIT_MANIFEST.json",
    ]
    for name in required:
        assert (exports / name).exists(), name
    assert (out / "objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb").exists()
    assert (out / "LCAI-0033_AUDIT_PACKAGE.zip").exists()


def test_row_counts_positive(audit_result: dict) -> None:
    assert int(audit_result["indicators"]["Exercices/contenus totaux"]) > 0
    assert int(audit_result["indicators"]["Annales officielles enregistrées"]) > 0


def test_anonymization_redacts_users(audit_result: dict) -> None:
    anon = audit_result["_out"] / "objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb"
    con = duckdb.connect(str(anon), read_only=True)
    try:
        rows = con.execute("SELECT name, pin_hash, email FROM users").fetchall()
        assert rows
        for name, pin, email in rows:
            assert str(name).startswith("user_")
            assert pin == "REDACTED"
            if email is not None:
                assert str(email).endswith("@example.invalid")
    finally:
        con.close()


def test_package_zip_contains_core_files(audit_result: dict) -> None:
    zpath = audit_result["_out"] / "LCAI-0033_AUDIT_PACKAGE.zip"
    with zipfile.ZipFile(zpath) as zf:
        names = set(zf.namelist())
    assert "LCAI-0033_DATABASE_STATE.md" in names
    assert "objectif_brevet_2027_AUDIT_ANONYMIZED.duckdb" in names
    assert "LCAI-0033_EXERCISE_CATALOG.csv" in names


def test_determinism_indicators_stable(audit_result: dict, tmp_path: Path) -> None:
    second = run_audit(output_root=tmp_path)
    assert second["indicators"] == audit_result["indicators"]
