"""Remap existing content and official archive questions onto canonical skills."""

from __future__ import annotations

import contextlib
import re
import unicodedata
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.curriculum_rebuild.target_tree import CORE_SUBJECTS


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _skill_keywords(store: BrevetContentStore, subject_code: str) -> list[tuple[int, int, str, set[str]]]:
    rows = store.fetchall(
        """
        SELECT sk.skill_id, ch.chapter_id, sk.name || ' ' || ch.name
        FROM skills sk
        JOIN chapters ch ON ch.chapter_id = sk.chapter_id
        JOIN curriculum_domains d ON d.domain_id = ch.domain_id
        JOIN subjects s ON s.subject_id = d.subject_id
        WHERE s.code = ?
          AND sk.active
          AND d.code NOT LIKE '%_CORE'
        """,
        [subject_code],
    )
    out: list[tuple[int, int, str, set[str]]] = []
    for skill_id, chapter_id, blob in rows:
        tokens = {t for t in _norm(str(blob)).split() if len(t) > 2}
        out.append((int(skill_id), int(chapter_id), str(blob), tokens))
    return out


def _best_skill(
    statement: str,
    catalog: list[tuple[int, int, str, set[str]]],
    fallback: tuple[int, int] | None,
) -> tuple[int, int] | None:
    tokens = {t for t in _norm(statement).split() if len(t) > 2}
    best: tuple[int, int] | None = fallback
    best_score = 0
    for skill_id, chapter_id, _blob, keys in catalog:
        score = len(tokens & keys)
        if score > best_score:
            best_score = score
            best = (skill_id, chapter_id)
    return best


def remap_content(
    store: BrevetContentStore,
    *,
    subject_filter: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    subjects = [subject_filter] if subject_filter else list(CORE_SUBJECTS)
    stats = {
        "content_remapped": 0,
        "official_remapped": 0,
        "links_created": 0,
        "unmapped_official": 0,
        "rows": [],
    }
    mappings = store.fetchall(
        """
        SELECT legacy_curriculum_node_id, canonical_curriculum_node_id, subject_code
        FROM curriculum_node_mappings
        WHERE legacy_node_type = 'SKILL' AND canonical_node_type = 'SKILL'
          AND mapping_type IN ('CHAPTER_PRIMARY', 'ALIAS_MATCH')
        """
    )
    skill_map = {(int(a), str(c)): int(b) for a, b, c in mappings}

    chapter_map_rows = store.fetchall(
        """
        SELECT legacy_curriculum_node_id, canonical_curriculum_node_id, subject_code
        FROM curriculum_node_mappings
        WHERE legacy_node_type = 'CHAPTER' AND canonical_node_type = 'CHAPTER'
          AND mapping_type = 'ALIAS_MATCH'
        """
    )
    chapter_map = {(int(a), str(c)): int(b) for a, b, c in chapter_map_rows}

    for subject_code in subjects:
        catalog = _skill_keywords(store, subject_code)
        fallback = (catalog[0][0], catalog[0][1]) if catalog else None
        contents = store.fetchall(
            """
            SELECT ci.content_id, ci.chapter_id, ci.statement, ci.source_type,
                   csl.skill_id, csl.relation_type
            FROM content_items ci
            JOIN subjects s ON s.subject_id = ci.subject_id
            LEFT JOIN content_skill_links csl
              ON csl.content_id = ci.content_id AND csl.relation_type = 'PRIMARY'
            WHERE s.code = ?
            """,
            [subject_code],
        )
        for content_id, chapter_id, statement, source_type, skill_id, _rel in contents:
            target_skill: int | None = None
            target_chapter: int | None = None
            if skill_id is not None and (int(skill_id), subject_code) in skill_map:
                target_skill = skill_map[(int(skill_id), subject_code)]
                row = store.fetchone("SELECT chapter_id FROM skills WHERE skill_id = ?", [target_skill])
                target_chapter = int(row[0]) if row else None
            elif chapter_id is not None and (int(chapter_id), subject_code) in chapter_map:
                target_chapter = chapter_map[(int(chapter_id), subject_code)]
                row = store.fetchone(
                    """
                    SELECT skill_id FROM skills
                    WHERE chapter_id = ? AND active
                    ORDER BY skill_id LIMIT 1
                    """,
                    [target_chapter],
                )
                target_skill = int(row[0]) if row else None
            else:
                matched = _best_skill(str(statement or ""), catalog, fallback)
                if matched:
                    target_skill, target_chapter = matched

            if target_skill is None or target_chapter is None:
                if source_type == "OFFICIAL_ARCHIVE":
                    stats["unmapped_official"] += 1
                continue

            if dry_run:
                stats["content_remapped"] += 1
                if source_type == "OFFICIAL_ARCHIVE":
                    stats["official_remapped"] += 1
                continue

            # Avoid UPDATE on content_items (FK parent). Remap via skill links only.
            existing = store.fetchone(
                """
                SELECT 1 FROM content_skill_links
                WHERE content_id = ? AND skill_id = ? AND relation_type = 'PRIMARY'
                """,
                [int(content_id), target_skill],
            )
            if not existing:
                if skill_id is not None and int(skill_id) != target_skill:
                    # Prefer insert SECONDARY for legacy pointer if absent
                    legacy_sec = store.fetchone(
                        """
                        SELECT 1 FROM content_skill_links
                        WHERE content_id = ? AND skill_id = ? AND relation_type = 'SECONDARY'
                        """,
                        [int(content_id), int(skill_id)],
                    )
                    if not legacy_sec:
                        with contextlib.suppress(Exception):
                            store.execute(
                                """
                                INSERT INTO content_skill_links(
                                    content_id, skill_id, subskill_id, relation_type, weight
                                ) VALUES (?, ?, NULL, 'SECONDARY', 0.25)
                                """,
                                [int(content_id), int(skill_id)],
                            )
                    # Replace PRIMARY by delete+insert on link table (child), not content_items
                    with contextlib.suppress(Exception):
                        store.execute(
                            """
                            DELETE FROM content_skill_links
                            WHERE content_id = ? AND skill_id = ? AND relation_type = 'PRIMARY'
                            """,
                            [int(content_id), int(skill_id)],
                        )
                store.execute(
                    """
                    INSERT INTO content_skill_links(content_id, skill_id, subskill_id, relation_type, weight)
                    VALUES (?, ?, NULL, 'PRIMARY', 1.0)
                    """,
                    [int(content_id), target_skill],
                )
                stats["links_created"] += 1
            stats["content_remapped"] += 1
            if source_type == "OFFICIAL_ARCHIVE":
                stats["official_remapped"] += 1
            stats["rows"].append(
                {
                    "content_id": int(content_id),
                    "subject": subject_code,
                    "from_skill": int(skill_id) if skill_id is not None else None,
                    "to_skill": target_skill,
                    "to_chapter": target_chapter,
                    "source_type": source_type,
                }
            )
    return stats
