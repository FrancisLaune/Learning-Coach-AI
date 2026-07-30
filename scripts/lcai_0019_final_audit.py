"""Final audit for LCAI-0019 Phase 2."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain.pedagogical_intelligence.paths import READINESS_PATHS
from infrastructure.database.v2 import connect_v2, reset_v2_connections

REPORT = ROOT / "docs" / "phase3" / "exports" / "lcai_0019_final_audit.json"


def main() -> int:
    database = ROOT / "data" / "learning_coach_v2.duckdb"
    connection = connect_v2(database, read_only=True)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        diag_content = connection.execute(
            """
            SELECT count(*) FROM production_learning_catalog
            WHERE content_type IN ('diagnostic_activity','exercise','exam_practice')
            """
        ).fetchone()[0]
    finally:
        connection.close()
        reset_v2_connections()

    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_pedagogical_intelligence.py",
            "tests/test_pedagogical_readiness.py",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    ui_text = (ROOT / "ui" / "pedagogical_intelligence.py").read_text(encoding="utf-8")
    report = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "ticket": "LCAI-0019-PHASE2",
        "migration_022": "pedagogical_intelligence_diagnostic_runs" in tables,
        "migration_023": "pedagogical_intelligence_refresh_runs" in tables,
        "readiness_paths": [path.code for path in READINESS_PATHS],
        "diagnostic_catalog_items": int(diag_content),
        "simulation_slider_removed": "simulation V1" not in ui_text,
        "tests_pass": tests.returncode == 0,
        "verdict": "PASS",
    }
    if not all(
        [
            report["migration_022"],
            report["migration_023"],
            report["simulation_slider_removed"],
            report["tests_pass"],
            report["diagnostic_catalog_items"] > 0,
        ]
    ):
        report["verdict"] = "FAIL"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
