"""LCAI-0019 phase-0 audit — pedagogical intelligence platform readiness."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain.pedagogical_intelligence.paths import READINESS_PATHS
from infrastructure.database.v2 import connect_v2

REPORT_PATH = ROOT / "docs" / "phase3" / "exports" / "lcai_0019_phase0_audit.json"


def main() -> int:
    database = ROOT / "data" / "learning_coach_v2.duckdb"
    connection = connect_v2(database, read_only=True)
    try:
        table_exists = bool(
            connection.execute(
                """
                SELECT count(*) FROM information_schema.tables
                WHERE table_name='pedagogical_intelligence_diagnostic_runs'
                """
            ).fetchone()[0]
        )
        grade_rows = connection.execute(
            "SELECT code FROM school_levels WHERE code IN ('FR-CM1','FR-CM2','FR-4E','FR-3E') ORDER BY code"
        ).fetchall()
        cm2_chapters = connection.execute(
            """
            SELECT count(DISTINCT cc.stable_code)
            FROM curriculum_chapters cc
            JOIN school_levels sl ON sl.id=cc.grade_level_id
            WHERE sl.code='FR-CM2' AND cc.status='approved'
            """
        ).fetchone()[0]
        cm2_published = connection.execute(
            """
            SELECT count(DISTINCT cc.stable_code)
            FROM production_learning_catalog alc
            JOIN curriculum_chapters cc ON cc.id=alc.chapter_id
            WHERE alc.grade_code='FR-CM2'
            """
        ).fetchone()[0]
    finally:
        connection.close()

    report = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "ticket": "LCAI-0019",
        "readiness_paths": [path.code for path in READINESS_PATHS],
        "migration_022_applied": table_exists,
        "supported_grades": [str(row[0]) for row in grade_rows],
        "cm2_chapters": int(cm2_chapters),
        "cm2_published_chapters": int(cm2_published),
        "pass": table_exists and len(grade_rows) == 4 and int(cm2_published) >= int(cm2_chapters),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
