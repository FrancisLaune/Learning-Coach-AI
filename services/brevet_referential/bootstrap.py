"""Bootstrap full LCAI-0032 referential on objectif_brevet_2027.duckdb."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.archives import import_manifest_discovered, write_manifest
from services.brevet_referential.coverage import measure_coverage
from services.brevet_referential.materialize import materialize_bank_coverage
from services.brevet_referential.migrate_legacy import migrate_duckdb_exam_questions, migrate_sqlite_exercises
from services.brevet_referential.migrations import apply_brevet_content_migrations
from services.brevet_referential.seed_curriculum import seed_curriculum_from_banks


def bootstrap_referential(db_path: Path | None = None) -> dict[str, Any]:
    store = BrevetContentStore(db_path)
    store.connect()
    try:
        applied = apply_brevet_content_migrations(store.db_path)
        curriculum = seed_curriculum_from_banks(store)
        sqlite_stats = migrate_sqlite_exercises(store)
        exam_stats = migrate_duckdb_exam_questions(store)
        manifest_path = write_manifest()
        archive_stats = import_manifest_discovered(store)
        materialize_stats = materialize_bank_coverage(store)
        coverage = measure_coverage(store)
        by_status: dict[str, int] = {}
        for row in coverage:
            by_status[row.coverage_status] = by_status.get(row.coverage_status, 0) + 1
        content_count = store.fetchone("SELECT COUNT(*) FROM content_items")
        return {
            "db_path": str(store.db_path),
            "migrations_applied": applied,
            "curriculum": curriculum,
            "sqlite_migration": sqlite_stats,
            "exam_questions_migration": exam_stats,
            "manifest_path": str(manifest_path),
            "archives": archive_stats,
            "materialize": materialize_stats,
            "content_items": int(content_count[0] if content_count else 0),
            "coverage_skills": len(coverage),
            "coverage_by_status": by_status,
        }
    finally:
        store.close()
