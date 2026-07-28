"""Phase 2 production database integrity audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from infrastructure.database.v2 import connect_v2  # noqa: E402
from services.operational_health import OperationalHealthService  # noqa: E402
from services.session_integrity import SessionIntegrityService  # noqa: E402

DATABASE = ROOT / "data" / "learning_coach_v2.duckdb"


def main() -> int:
    report: dict[str, object] = {"database": str(DATABASE), "checks": [], "pass": True}
    checks: list[dict[str, object]] = []

    health = OperationalHealthService(DATABASE).check()
    checks.append(
        {
            "name": "operational_health",
            "pass": health.healthy,
            "details": [{"name": c.name, "healthy": c.healthy, "detail": c.detail} for c in health.checks],
        }
    )
    orphans = SessionIntegrityService(DATABASE).inspect()
    checks.append(
        {"name": "session_orphans", "pass": len(orphans) == 0, "details": [issue.__dict__ for issue in orphans]}
    )

    connection = connect_v2(DATABASE, read_only=True)
    try:
        table_count = connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'"
        ).fetchone()[0]
        view_count = connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main' AND table_type='VIEW'"
        ).fetchone()[0]
        index_count = connection.execute("SELECT COUNT(*) FROM duckdb_indexes()").fetchone()[0]
        checks.extend(
            [
                {"name": "tables_present", "pass": int(table_count) >= 100, "details": int(table_count)},
                {"name": "views_present", "pass": int(view_count) >= 5, "details": int(view_count)},
                {"name": "indexes_present", "pass": int(index_count) >= 10, "details": int(index_count)},
            ]
        )

        orphan_exercise_questions = connection.execute(
            """
            SELECT COUNT(*) FROM exercise_questions eq
            LEFT JOIN exercises e ON e.id = eq.exercise_id
            WHERE e.id IS NULL
            """
        ).fetchone()[0]
        orphan_question_skills = connection.execute(
            """
            SELECT COUNT(*) FROM question_skills qs
            LEFT JOIN questions q ON q.id = qs.question_id
            WHERE q.id IS NULL
            """
        ).fetchone()[0]
        orphan_content_versions = connection.execute(
            """
            SELECT COUNT(*) FROM content_versions cv
            LEFT JOIN exercises e ON cv.entity_type='exercise' AND cv.entity_id=e.id
            WHERE cv.entity_type='exercise' AND e.id IS NULL
            """
        ).fetchone()[0]
        checks.extend(
            [
                {
                    "name": "orphan_exercise_questions",
                    "pass": int(orphan_exercise_questions) == 0,
                    "details": int(orphan_exercise_questions),
                },
                {
                    "name": "orphan_question_skills",
                    "pass": int(orphan_question_skills) == 0,
                    "details": int(orphan_question_skills),
                },
                {
                    "name": "orphan_content_versions",
                    "pass": int(orphan_content_versions) == 0,
                    "details": int(orphan_content_versions),
                },
            ]
        )

        curriculum_chapters = connection.execute("SELECT COUNT(*) FROM curriculum_chapters").fetchone()[0]
        curriculum_skill_details = connection.execute("SELECT COUNT(*) FROM curriculum_skill_details").fetchone()[0]
        skills = connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        draft_versions = connection.execute("SELECT COUNT(*) FROM content_versions WHERE status='draft'").fetchone()[0]
        approved_versions = connection.execute(
            "SELECT COUNT(*) FROM content_versions WHERE status='approved'"
        ).fetchone()[0]
        checks.extend(
            [
                {
                    "name": "curriculum_chapters",
                    "pass": int(curriculum_chapters) > 0,
                    "details": int(curriculum_chapters),
                },
                {
                    "name": "curriculum_skill_details",
                    "pass": int(curriculum_skill_details) > 0,
                    "details": int(curriculum_skill_details),
                },
                {"name": "skills", "pass": int(skills) > 0, "details": int(skills)},
                {"name": "draft_versions", "pass": int(draft_versions) > 0, "details": int(draft_versions)},
                {"name": "approved_versions", "pass": int(approved_versions) > 0, "details": int(approved_versions)},
            ]
        )

        mapping_path = ROOT / "resources/content/integration/lcai_0012e_isolated_to_production_version_mapping.jsonl"
        if mapping_path.exists():
            mapping = [
                json.loads(line) for line in mapping_path.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            production_ids = {int(row["production_version_id"]) for row in mapping}
            found = connection.execute(
                f"SELECT COUNT(*) FROM content_versions WHERE id IN ({','.join(str(i) for i in sorted(production_ids))})"
            ).fetchone()[0]
            checks.append(
                {
                    "name": "publication_mapping_resolved",
                    "pass": int(found) == len(production_ids),
                    "details": {"expected": len(production_ids), "found": int(found)},
                }
            )
    finally:
        connection.close()

    report["checks"] = checks
    report["pass"] = all(bool(item["pass"]) for item in checks)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
