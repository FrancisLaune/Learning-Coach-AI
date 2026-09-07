"""Apply canonical curriculum structure (domains/chapters/skills/subskills)."""

from __future__ import annotations

from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.curriculum_rebuild.target_tree import (
    CORE_SUBJECTS,
    LEGACY_RECLASSIFY,
    TARGET_TREE,
)
from services.brevet_referential.curriculum_rebuild.thresholds import normalize_importance
from services.brevet_referential.models import slugify


def _version_id(store: BrevetContentStore) -> int:
    row = store.fetchone("SELECT curriculum_version_id FROM curriculum_versions WHERE code = 'FR_3E_DNB_2027_V1'")
    if row is None:
        raise RuntimeError("curriculum version FR_3E_DNB_2027_V1 missing")
    return int(row[0])


def _ensure_domain(
    store: BrevetContentStore,
    *,
    version_id: int,
    subject_id: int,
    code: str,
    name: str,
    sort_order: int,
    description: str,
) -> tuple[int, bool]:
    existing = store.fetchone(
        """
        SELECT domain_id FROM curriculum_domains
        WHERE curriculum_version_id = ? AND subject_id = ? AND code = ?
        """,
        [version_id, subject_id, code],
    )
    if existing:
        return int(existing[0]), False
    store.execute(
        """
        INSERT INTO curriculum_domains(
            curriculum_version_id, subject_id, code, name, description, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [version_id, subject_id, code, name, description, sort_order],
    )
    row = store.fetchone(
        """
        SELECT domain_id FROM curriculum_domains
        WHERE curriculum_version_id = ? AND subject_id = ? AND code = ?
        """,
        [version_id, subject_id, code],
    )
    assert row is not None
    return int(row[0]), True


def _ensure_chapter(
    store: BrevetContentStore,
    *,
    domain_id: int,
    code: str,
    name: str,
    importance: str,
    role: str,
) -> tuple[int, bool]:
    existing = store.fetchone(
        "SELECT chapter_id FROM chapters WHERE domain_id = ? AND code = ?",
        [domain_id, code],
    )
    imp = normalize_importance(importance)
    if existing:
        # DuckDB FK limitation: do not UPDATE parent chapter rows.
        return int(existing[0]), False
    store.execute(
        """
        INSERT INTO chapters(
            domain_id, code, name, description, brevet_importance, active,
            curriculum_role, curriculum_status
        ) VALUES (?, ?, ?, ?, ?, TRUE, ?, 'ACTIVE')
        """,
        [domain_id, code, name, name, imp, role],
    )
    row = store.fetchone(
        "SELECT chapter_id FROM chapters WHERE domain_id = ? AND code = ?",
        [domain_id, code],
    )
    assert row is not None
    return int(row[0]), True


def _ensure_skill(
    store: BrevetContentStore,
    *,
    chapter_id: int,
    code: str,
    name: str,
    importance: str,
    role: str,
) -> tuple[int, bool]:
    existing = store.fetchone(
        "SELECT skill_id FROM skills WHERE chapter_id = ? AND code = ?",
        [chapter_id, code],
    )
    imp = normalize_importance(importance)
    if existing:
        # DuckDB FK limitation: do not UPDATE parent skill rows.
        return int(existing[0]), False
    store.execute(
        """
        INSERT INTO skills(
            chapter_id, code, name, description, expected_level,
            brevet_importance, auto_gradable, active, curriculum_role, coverage_status
        ) VALUES (?, ?, ?, ?, '3E', ?, TRUE, TRUE, ?, 'EMPTY')
        """,
        [chapter_id, code, name, name, imp, role],
    )
    row = store.fetchone(
        "SELECT skill_id FROM skills WHERE chapter_id = ? AND code = ?",
        [chapter_id, code],
    )
    assert row is not None
    return int(row[0]), True


def _ensure_subskill(
    store: BrevetContentStore,
    *,
    skill_id: int,
    code: str,
    name: str,
    role: str,
) -> tuple[int, bool]:
    existing = store.fetchone(
        "SELECT subskill_id FROM subskills WHERE skill_id = ? AND code = ?",
        [skill_id, code],
    )
    if existing:
        return int(existing[0]), False
    store.execute(
        """
        INSERT INTO subskills(skill_id, code, name, description, active, curriculum_role)
        VALUES (?, ?, ?, ?, TRUE, ?)
        """,
        [skill_id, code, name, name, role],
    )
    row = store.fetchone(
        "SELECT subskill_id FROM subskills WHERE skill_id = ? AND code = ?",
        [skill_id, code],
    )
    assert row is not None
    return int(row[0]), True


def _upsert_mapping(
    store: BrevetContentStore,
    *,
    legacy_type: str,
    legacy_id: int,
    canonical_type: str,
    canonical_id: int,
    mapping_type: str,
    reason: str,
    subject_code: str,
) -> None:
    existing = store.fetchone(
        """
        SELECT mapping_id FROM curriculum_node_mappings
        WHERE legacy_node_type = ? AND legacy_curriculum_node_id = ?
          AND canonical_node_type = ? AND canonical_curriculum_node_id = ?
          AND mapping_type = ?
        """,
        [legacy_type, legacy_id, canonical_type, canonical_id, mapping_type],
    )
    if existing:
        return
    store.execute(
        """
        INSERT INTO curriculum_node_mappings(
            legacy_node_type, legacy_curriculum_node_id,
            canonical_node_type, canonical_curriculum_node_id,
            mapping_type, mapping_reason, subject_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [legacy_type, legacy_id, canonical_type, canonical_id, mapping_type, reason, subject_code],
    )


def apply_structure(
    store: BrevetContentStore,
    *,
    subject_filter: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    version_id = _version_id(store)
    subjects = [subject_filter] if subject_filter else list(CORE_SUBJECTS)
    plan = {
        "domains_to_create": 0,
        "chapters_to_create": 0,
        "skills_to_create": 0,
        "subskills_to_create": 0,
        "chapters_to_reclassify": 0,
        "legacy_mappings": 0,
        "created_ids": {"domains": [], "chapters": [], "skills": [], "subskills": []},
    }
    if dry_run:
        for subject_code in subjects:
            for domain in TARGET_TREE.get(subject_code, []):
                plan["domains_to_create"] += 1
                for chapter in domain["chapters"]:
                    plan["chapters_to_create"] += 1
                    for skill in chapter["skills"]:
                        plan["skills_to_create"] += 1
                        plan["subskills_to_create"] += len(skill.get("subskills") or [])
            plan["chapters_to_reclassify"] += len(LEGACY_RECLASSIFY.get(subject_code, []))
        return plan

    for subject_code in subjects:
        subject_id = store.subject_id(subject_code)
        if subject_id is None:
            continue
        for domain in TARGET_TREE.get(subject_code, []):
            role = "TRANSVERSAL" if str(domain["code"]).endswith("_TRANSVERSAL") else "CANONICAL_3E"
            domain_id, created = _ensure_domain(
                store,
                version_id=version_id,
                subject_id=subject_id,
                code=domain["code"],
                name=domain["name"],
                sort_order=int(domain.get("sort_order") or 0),
                description=f"Domaine officiel / pédagogique — {domain['name']}",
            )
            if created:
                plan["domains_to_create"] += 1
                plan["created_ids"]["domains"].append(domain_id)
            for chapter in domain["chapters"]:
                chapter_id, created_ch = _ensure_chapter(
                    store,
                    domain_id=domain_id,
                    code=chapter["code"],
                    name=chapter["name"],
                    importance=chapter.get("importance") or "MEDIUM",
                    role=role,
                )
                if created_ch:
                    plan["chapters_to_create"] += 1
                    plan["created_ids"]["chapters"].append(chapter_id)
                for skill in chapter["skills"]:
                    skill_id, created_sk = _ensure_skill(
                        store,
                        chapter_id=chapter_id,
                        code=skill["code"],
                        name=skill["name"],
                        importance=chapter.get("importance") or "MEDIUM",
                        role=role,
                    )
                    if created_sk:
                        plan["skills_to_create"] += 1
                        plan["created_ids"]["skills"].append(skill_id)
                    for sub in skill.get("subskills") or []:
                        sub_id, created_ss = _ensure_subskill(
                            store,
                            skill_id=skill_id,
                            code=sub["code"],
                            name=sub["name"],
                            role=role,
                        )
                        if created_ss:
                            plan["subskills_to_create"] += 1
                            plan["created_ids"]["subskills"].append(sub_id)

                # Map legacy chapters by alias / slugify name
                aliases = list(chapter.get("legacy_aliases") or [])
                aliases.append(chapter["name"])
                for alias in aliases:
                    legacy = store.fetchone(
                        """
                        SELECT c.chapter_id, sk.skill_id
                        FROM chapters c
                        JOIN curriculum_domains d ON d.domain_id = c.domain_id
                        JOIN subjects s ON s.subject_id = d.subject_id
                        LEFT JOIN skills sk ON sk.chapter_id = c.chapter_id
                        WHERE s.code = ? AND (c.name = ? OR c.code = ?)
                        ORDER BY sk.skill_id
                        LIMIT 1
                        """,
                        [subject_code, alias, slugify(alias)[:80]],
                    )
                    if legacy is None:
                        continue
                    legacy_chapter_id = int(legacy[0])
                    if legacy_chapter_id == chapter_id:
                        continue
                    _upsert_mapping(
                        store,
                        legacy_type="CHAPTER",
                        legacy_id=legacy_chapter_id,
                        canonical_type="CHAPTER",
                        canonical_id=chapter_id,
                        mapping_type="ALIAS_MATCH",
                        reason=f"alias:{alias}",
                        subject_code=subject_code,
                    )
                    plan["legacy_mappings"] += 1
                    if legacy[1] is not None:
                        # Map old flat skill to first canonical skill of chapter
                        first_skill = store.fetchone(
                            """
                            SELECT skill_id FROM skills
                            WHERE chapter_id = ? AND active
                            ORDER BY skill_id LIMIT 1
                            """,
                            [chapter_id],
                        )
                        if first_skill:
                            _upsert_mapping(
                                store,
                                legacy_type="SKILL",
                                legacy_id=int(legacy[1]),
                                canonical_type="SKILL",
                                canonical_id=int(first_skill[0]),
                                mapping_type="CHAPTER_PRIMARY",
                                reason=f"alias:{alias}",
                                subject_code=subject_code,
                            )
                            plan["legacy_mappings"] += 1

        # Reclassify non-3e legacy chapters (mapping only — no UPDATE on FK parents)
        for item in LEGACY_RECLASSIFY.get(subject_code, []):
            legacy_name = item["legacy_name"]
            reason = item.get("reason") or "reclassified"
            row = store.fetchone(
                """
                SELECT c.chapter_id
                FROM chapters c
                JOIN curriculum_domains d ON d.domain_id = c.domain_id
                JOIN subjects s ON s.subject_id = d.subject_id
                WHERE s.code = ? AND c.name = ?
                """,
                [subject_code, legacy_name],
            )
            if row is None:
                continue
            chapter_id = int(row[0])
            plan["chapters_to_reclassify"] += 1
            _upsert_mapping(
                store,
                legacy_type="CHAPTER",
                legacy_id=chapter_id,
                canonical_type="CHAPTER",
                canonical_id=chapter_id,
                mapping_type="RECLASSIFY",
                reason=reason,
                subject_code=subject_code,
            )

        # Old *_CORE chapters stay preserved; canonical queries exclude *_CORE domains.

    return plan
