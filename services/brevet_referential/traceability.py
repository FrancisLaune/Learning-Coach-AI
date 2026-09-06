"""LCAI-0034 — reclassify false ARCHIVE_DERIVED and enforce parent links."""

from __future__ import annotations

from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore


def count_archive_derived_without_parent(store: BrevetContentStore) -> int:
    row = store.fetchone(
        """
        SELECT COUNT(*) FROM v_content_items_effective c
        WHERE c.source_type = 'ARCHIVE_DERIVED'
          AND NOT EXISTS (
            SELECT 1 FROM content_derivations d
            WHERE d.derived_content_id = c.content_id
              AND d.parent_question_id IS NOT NULL
          )
        """
    )
    return int(row[0]) if row else 0


def reclassify_false_archive_derived(
    store: BrevetContentStore,
    *,
    target_source: str = "BREVET_STYLE",
) -> dict[str, Any]:
    """Reclassify via overrides table (DuckDB cannot UPDATE FK-parent content_items rows)."""
    before = count_archive_derived_without_parent(store)
    ids = [
        int(r[0])
        for r in store.fetchall(
            """
            SELECT c.content_id FROM v_content_items_effective c
            WHERE c.source_type = 'ARCHIVE_DERIVED'
              AND NOT EXISTS (
                SELECT 1 FROM content_derivations d
                WHERE d.derived_content_id = c.content_id
                  AND d.parent_question_id IS NOT NULL
              )
            ORDER BY c.content_id
            """
        )
    ]
    for content_id in ids:
        store.execute(
            """
            INSERT INTO content_source_overrides(content_id, source_type, reason)
            VALUES (?, ?, 'ARCHIVE_DERIVED_WITHOUT_PARENT')
            ON CONFLICT (content_id) DO UPDATE SET
              source_type = excluded.source_type,
              reason = excluded.reason
            """,
            [content_id, target_source],
        )
        store.execute(
            """
            INSERT INTO referential_events(event_type, entity_ref, detail)
            VALUES ('ContentSourceReclassified', ?, ?)
            """,
            [str(content_id), f"ARCHIVE_DERIVED->{target_source}:override"],
        )
    after = count_archive_derived_without_parent(store)
    remaining_derived = store.fetchone(
        "SELECT COUNT(*) FROM v_content_items_effective WHERE source_type='ARCHIVE_DERIVED'"
    )
    return {
        "without_parent_before": before,
        "reclassified": len(ids),
        "without_parent_after": after,
        "archive_derived_remaining": int(remaining_derived[0]) if remaining_derived else 0,
        "target_source": target_source,
        "mechanism": "content_source_overrides",
    }


def assert_no_orphan_archive_derived(store: BrevetContentStore) -> None:
    n = count_archive_derived_without_parent(store)
    if n > 0:
        raise AssertionError(f"ARCHIVE_DERIVED_WITHOUT_PARENT={n}")
