"""LCAI-0018G — 3e certification (audit + homework readiness, hors pipeline 0012E)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from core.config import get_v2_database_path
from services.content.primary_integration import PRIMARY_GRADES

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "phase3"
EXPORTS = DOCS / "exports"
GRADE = "FR-3E"
REPORT_PATH = EXPORTS / "lcai_0018g_3e_certification_report.json"


def run_3e_certification() -> dict[str, object]:
    if GRADE in PRIMARY_GRADES:
        raise RuntimeError(f"{GRADE} should not be in PRIMARY_GRADES for 18G model")

    audit = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lcai_0018g_phase0_audit.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if audit.returncode != 0:
        raise RuntimeError(audit.stderr[-2000:])

    connection = duckdb.connect(str(get_v2_database_path()), read_only=True)
    try:
        production_total = int(
            connection.execute(
                "SELECT COUNT(*) FROM production_learning_catalog WHERE grade_code=?",
                [GRADE],
            ).fetchone()[0]
        )
        chapters_published = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT cc.stable_code)
                FROM production_learning_catalog alc
                JOIN curriculum_chapters cc ON cc.id = alc.chapter_id
                WHERE alc.grade_code = ?
                """,
                [GRADE],
            ).fetchone()[0]
        )
        subjects_with_prod = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT sub.code)
                FROM production_learning_catalog alc
                JOIN subjects sub ON sub.id = alc.subject_id
                WHERE alc.grade_code = ?
                """,
                [GRADE],
            ).fetchone()[0]
        )
    finally:
        connection.close()

    report: dict[str, object] = {
        "ticket": "LCAI-0018G",
        "grade": GRADE,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "publication_model": "EXISTING_PRODUCTION_CATALOG",
        "note": "3e hors périmètre LCAI-0012E PRIMARY_GRADES — pas de publication AI batch",
        "production_total": production_total,
        "chapters_published": chapters_published,
        "subjects_with_production": subjects_with_prod,
        "0012e_eligible_remaining": 0,
        "certification_status": "CERTIFIE_EXISTANT" if production_total > 0 else "NON_CERTIFIE",
    }
    EXPORTS.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def main() -> None:
    run_3e_certification()


if __name__ == "__main__":
    main()
