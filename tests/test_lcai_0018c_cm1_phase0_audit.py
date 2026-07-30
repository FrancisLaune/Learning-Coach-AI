"""LCAI-0018C — CM1 phase C0 audit smoke tests."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"


def test_cm1_phase0_audit_script_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lcai_0018c_phase0_audit.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_cm1_phase0_exports_exist_and_cover_curriculum() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lcai_0018c_phase0_audit.py")],
        cwd=ROOT,
        check=True,
    )
    matrix_path = EXPORTS / "LCAI-0018C_CM1_COVERAGE_MATRIX.csv"
    gap_path = EXPORTS / "LCAI-0018C_CM1_GAP_BY_CHAPTER.csv"
    inventory_path = EXPORTS / "LCAI-0018C_CM1_CANDIDATE_INVENTORY.csv"
    baseline_path = DOCS / "LCAI-0018C_PHASE0_BASELINE.md"

    assert matrix_path.exists()
    assert gap_path.exists()
    assert inventory_path.exists()
    assert baseline_path.exists()

    with matrix_path.open(encoding="utf-8-sig", newline="") as handle:
        matrix_rows = list(csv.DictReader(handle))
    with gap_path.open(encoding="utf-8-sig", newline="") as handle:
        gap_rows = list(csv.DictReader(handle))
    with inventory_path.open(encoding="utf-8-sig", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))

    assert matrix_rows
    assert all(row["grade_code"] == "FR-CM1" for row in matrix_rows)
    assert gap_rows
    assert len({row["subject_code"] for row in gap_rows}) >= 8
    assert inventory_rows
    assert len(inventory_rows) >= 200
