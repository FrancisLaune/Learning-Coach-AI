"""LCAI-0034 — exercise families and near-duplicate classification."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.models import fingerprint_text


def classify_near_duplicate_group(statements: list[str]) -> str:
    norms = [fingerprint_text(s) for s in statements]
    if len(set(norms)) == 1:
        return "TRUE_DUPLICATE"
    prefixes = {s[:40].casefold() for s in statements if s}
    if len(prefixes) == 1 and len(statements) > 1:
        return "PARAMETRIC_FAMILY"
    if len(statements) <= 3:
        return "SAME_SKILL_DIFFERENT_REASONING"
    return "LEGITIMATE_SIMILARITY"


class Counterish:
    def __init__(self) -> None:
        self._data: dict[str, int] = defaultdict(int)

    def incr(self, key: str) -> None:
        self._data[key] += 1

    def as_dict(self) -> dict[str, int]:
        return dict(self._data)


def build_exercise_families(store: BrevetContentStore) -> dict[str, Any]:
    rows = store.fetchall(
        """
        SELECT c.content_id, c.subject_id, l.skill_id, c.semantic_fingerprint, c.statement
        FROM content_items c
        LEFT JOIN content_skill_links l
          ON l.content_id = c.content_id AND l.relation_type = 'PRIMARY'
        WHERE c.semantic_fingerprint IS NOT NULL AND length(c.semantic_fingerprint) > 0
        ORDER BY c.semantic_fingerprint, c.content_id
        """
    )
    groups: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        groups[str(row[3])].append(row)

    families_created = 0
    classified = Counterish()
    links = 0
    for signature, members in groups.items():
        statements = [str(m[4] or "") for m in members]
        klass = classify_near_duplicate_group(statements) if len(members) > 1 else "SINGLETON"
        classified.incr(klass)
        subject_id = members[0][1]
        skill_id = members[0][2]
        existing = store.fetchone(
            "SELECT family_id FROM exercise_families WHERE semantic_signature = ?",
            [signature],
        )
        if existing:
            family_id = int(existing[0])
        else:
            store.execute(
                """
                INSERT INTO exercise_families(subject_id, skill_id, family_type, semantic_signature, canonical_pattern)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    subject_id,
                    skill_id,
                    "PARAMETRIC_FAMILY" if klass == "PARAMETRIC_FAMILY" else "SEMANTIC_CLUSTER",
                    signature,
                    statements[0][:120] if statements else None,
                ],
            )
            fam = store.fetchone(
                "SELECT family_id FROM exercise_families WHERE semantic_signature = ?",
                [signature],
            )
            family_id = int(fam[0]) if fam else 0
            families_created += 1
            store.execute(
                """
                INSERT INTO referential_events(event_type, entity_ref, detail)
                VALUES ('ExerciseFamilyCreated', ?, ?)
                """,
                [str(family_id), klass],
            )
        for member in members:
            cid = int(member[0])
            store.execute(
                """
                INSERT INTO content_family_links(content_id, family_id, near_duplicate_class, canonical_content_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (content_id) DO UPDATE SET
                  family_id = excluded.family_id,
                  near_duplicate_class = excluded.near_duplicate_class
                """,
                [
                    cid,
                    family_id,
                    klass if len(members) > 1 else None,
                    f"ob:{cid}",
                ],
            )
            links += 1
            if klass == "TRUE_DUPLICATE" and member != members[0]:
                store.execute(
                    """
                    INSERT INTO referential_events(event_type, entity_ref, detail)
                    VALUES ('DuplicateConsolidated', ?, ?)
                    """,
                    [str(cid), f"kept={members[0][0]};soft=family_cap"],
                )

        # Singletons without semantic fingerprint still get a canonical link
    orphans = store.fetchall(
        """
        SELECT content_id FROM content_items c
        WHERE NOT EXISTS (SELECT 1 FROM content_family_links f WHERE f.content_id=c.content_id)
        """
    )
    for (cid,) in orphans:
        store.execute(
            """
            INSERT INTO content_family_links(content_id, family_id, near_duplicate_class, canonical_content_id)
            VALUES (?, NULL, 'SINGLETON', ?)
            """,
            [int(cid), f"ob:{int(cid)}"],
        )
    return {
        "groups_seen": len(groups),
        "families_created": families_created,
        "classification": classified.as_dict(),
        "multi_member_groups": sum(1 for g in groups.values() if len(g) > 1),
        "links": links,
        "singleton_links": len(orphans),
    }
