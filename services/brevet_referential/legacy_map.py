"""Map V2 exercises onto OB canonical content without breaking histories."""

from __future__ import annotations

from typing import Any

import duckdb

from core.config import get_v2_database_path
from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.models import fingerprint_text


def map_v2_catalog_to_ob(store: BrevetContentStore, *, limit: int | None = None) -> dict[str, Any]:
    v2 = duckdb.connect(str(get_v2_database_path()), read_only=True)
    try:
        sql = """
            SELECT e.id, e.code, e.title, q.statement, q.expected_answer, e.difficulty, e.status
            FROM exercises e
            JOIN exercise_questions eq ON eq.exercise_id=e.id
            JOIN questions q ON q.id=eq.question_id
            WHERE e.archived_at IS NULL
            ORDER BY e.id
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = v2.execute(sql).fetchall()
    finally:
        v2.close()

    stats = {
        "audited": 0,
        "OB_EQUIVALENT": 0,
        "OB_DUPLICATE": 0,
        "MIGRATE_TO_OB": 0,
        "V2_ONLY": 0,
        "OUT_OF_SCOPE_3E": 0,
    }
    for exercise_id, code, title, statement, expected, difficulty, status in rows:
        stats["audited"] += 1
        fp = fingerprint_text(statement or "", expected or "")
        ob = store.fetchone(
            "SELECT content_id, fingerprint FROM content_items WHERE fingerprint=? OR semantic_fingerprint=?",
            [fp, fp],
        )
        # softer match on statement fingerprint alone
        if not ob:
            sfp = fingerprint_text(statement or "")
            ob = store.fetchone(
                "SELECT content_id, fingerprint FROM content_items WHERE semantic_fingerprint=? LIMIT 1",
                [sfp],
            )
        if ob:
            klass = "OB_EQUIVALENT"
            stats["OB_EQUIVALENT"] += 1
            ob_id = int(ob[0])
        else:
            # V2 content without OB twin — keep runtime via mapping class V2_ONLY
            klass = "V2_ONLY"
            stats["V2_ONLY"] += 1
            ob_id = None
        existing = store.fetchone(
            "SELECT mapping_id FROM legacy_content_mapping WHERE legacy_source='v2_exercises' AND legacy_id=?",
            [str(exercise_id)],
        )
        if existing:
            continue
        store.execute(
            """
            INSERT INTO legacy_content_mapping(
              canonical_content_id, legacy_source, legacy_id, content_fingerprint,
              migration_class, ob_content_id, notes
            ) VALUES (?, 'v2_exercises', ?, ?, ?, ?, ?)
            """,
            [
                f"ob:{ob_id}" if ob_id else f"v2:{exercise_id}",
                str(exercise_id),
                fp,
                klass,
                ob_id,
                f"title={title};status={status};difficulty={difficulty};code={code}",
            ],
        )
        store.execute(
            """
            INSERT INTO referential_events(event_type, entity_ref, detail)
            VALUES ('LegacyContentMapped', ?, ?)
            """,
            [str(exercise_id), klass],
        )
    return stats
