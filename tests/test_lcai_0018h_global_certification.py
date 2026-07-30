"""LCAI-0018H — Global certification audit smoke tests."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"
AUDIT_SCRIPT = ROOT / "scripts" / "lcai_0018h_global_certification_audit.py"
REPORT_PATH = DOCS / "LCAI-0018H_GLOBAL_CERTIFICATION_REPORT.md"
JSON_PATH = EXPORTS / "LCAI-0018H_GLOBAL_CERTIFICATION.json"
CSV_PATH = EXPORTS / "LCAI-0018H_GRADE_CERTIFICATION.csv"

EXPECTED_GRADES = {"FR-CM1", "FR-CM2", "FR-6E", "FR-5E", "FR-4E", "FR-3E"}


def test_18h_global_certification_script_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert REPORT_PATH.exists()
    assert JSON_PATH.exists()
    assert CSV_PATH.exists()


def test_18h_certification_covers_all_primary_grades() -> None:
    if not JSON_PATH.exists():
        subprocess.run([sys.executable, str(AUDIT_SCRIPT)], cwd=ROOT, check=True)
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    grade_codes = {row["grade_code"] for row in payload["grades"]}
    assert grade_codes >= EXPECTED_GRADES


def test_18h_implemented_tickets_have_0000a_or_pending_documented() -> None:
    if not JSON_PATH.exists():
        subprocess.run([sys.executable, str(AUDIT_SCRIPT)], cwd=ROOT, check=True)
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for row in payload["grades"]:
        if row["ticket_status"] == "IMPLEMENTED":
            assert row["technical_validation_0000a"] in {"OK", "WARN", "NOT_RUN", "PENDING"}


def test_18h_grade_certification_csv_has_six_rows() -> None:
    if not CSV_PATH.exists():
        subprocess.run([sys.executable, str(AUDIT_SCRIPT)], cwd=ROOT, check=True)
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert {row["grade_code"] for row in rows} == EXPECTED_GRADES


def test_18h_report_documents_partial_certification() -> None:
    if not REPORT_PATH.exists():
        subprocess.run([sys.executable, str(AUDIT_SCRIPT)], cwd=ROOT, check=True)
    text = REPORT_PATH.read_text(encoding="utf-8")
    assert "CERTIFICATION PARTIELLE" in text
    assert "LCAI-0000A" in text
