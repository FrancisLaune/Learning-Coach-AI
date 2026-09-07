"""LCAI-0039 curriculum rebuild tests."""

from __future__ import annotations

import json

import pytest

from core.config import PROJECT_ROOT, get_database_path
from services.brevet_referential.curriculum_rebuild.target_tree import (
    CORE_SUBJECTS,
    LEGACY_RECLASSIFY,
    TARGET_TREE,
)
from services.brevet_referential.curriculum_rebuild.thresholds import exercise_minima


def test_official_sources_frozen() -> None:
    path = PROJECT_ROOT / "data" / "curriculum" / "dnb_2027_curriculum_sources.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    statuses = {s["source_id"]: s.get("status_for_dnb_2027") for s in data["sources"]}
    assert statuses["MATH_CYCLE4_BO_2020"] == "APPLICABLE"
    assert statuses["MATH_CYCLE4_BO_2026_NOT_YET_3E"] == "NOT_APPLICABLE_YET"
    assert statuses["EMC_BO_2024_APPLICABLE_3E_2026"] == "APPLICABLE"


def test_target_tree_has_multi_domains_and_subskills() -> None:
    for code in CORE_SUBJECTS:
        domains = TARGET_TREE[code]
        assert len(domains) >= 1
        assert any(not d["code"].endswith("_CORE") for d in domains)
        skills = 0
        subskills = 0
        for domain in domains:
            for chapter in domain["chapters"]:
                assert chapter["skills"]
                for skill in chapter["skills"]:
                    skills += 1
                    subskills += len(skill.get("subskills") or [])
        assert skills >= 5
        assert subskills >= skills


def test_history_legacy_not_injected_as_canonical() -> None:
    legacy_names = {x["legacy_name"] for x in LEGACY_RECLASSIFY["HISTORY"]}
    assert "Révolution française" in legacy_names
    canonical_names = {ch["name"] for domain in TARGET_TREE["HISTORY"] for ch in domain["chapters"]}
    assert "Révolution française" not in canonical_names
    assert any("Première Guerre mondiale" in n or "guerre" in n.casefold() for n in canonical_names)


def test_exercise_minima_match_ticket() -> None:
    assert exercise_minima("CRITICAL") == 50
    assert exercise_minima("HIGH") == 40
    assert exercise_minima("STANDARD") == 30


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_structural_invariants_after_rebuild() -> None:
    import duckdb

    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        # Skip soft if rebuild not applied yet
        has_role = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'chapters' AND column_name = 'curriculum_role'
            """
        ).fetchone()
        if not has_role or int(has_role[0]) == 0:
            pytest.skip("LCAI-0039 migration not applied")
        active_subjects = CORE_SUBJECTS
        empty_active = con.execute(
            """
            SELECT COUNT(*) FROM skills sk
            JOIN chapters c ON c.chapter_id = sk.chapter_id
            JOIN curriculum_domains d ON d.domain_id = c.domain_id
            WHERE sk.active
              AND d.code NOT LIKE '%_CORE'
              AND NOT EXISTS (
                SELECT 1 FROM content_skill_links csl WHERE csl.skill_id = sk.skill_id
              )
            """
        ).fetchone()
        assert empty_active is not None and int(empty_active[0]) == 0
        official = con.execute("SELECT COUNT(*) FROM content_items WHERE source_type = 'OFFICIAL_ARCHIVE'").fetchone()
        assert official is not None and int(official[0]) >= 1098
        derived_orphan = con.execute(
            """
            SELECT COUNT(*) FROM v_content_items_effective ci
            WHERE ci.source_type = 'ARCHIVE_DERIVED'
              AND NOT EXISTS (
                SELECT 1 FROM content_derivations cd WHERE cd.derived_content_id = ci.content_id
              )
            """
        ).fetchone()
        assert derived_orphan is not None and int(derived_orphan[0]) == 0
        canonical_skills = con.execute(
            """
            SELECT COUNT(*) FROM skills sk
            JOIN chapters c ON c.chapter_id = sk.chapter_id
            JOIN curriculum_domains d ON d.domain_id = c.domain_id
            WHERE sk.active AND d.code NOT LIKE '%_CORE'
            """
        ).fetchone()
        assert canonical_skills is not None and int(canonical_skills[0]) >= 50
        chapter_without_skill = con.execute(
            """
            SELECT COUNT(*) FROM chapters c
            JOIN curriculum_domains d ON d.domain_id = c.domain_id
            WHERE c.active AND d.code NOT LIKE '%_CORE'
              AND NOT EXISTS (SELECT 1 FROM skills sk WHERE sk.chapter_id = c.chapter_id AND sk.active)
            """
        ).fetchone()
        assert chapter_without_skill is not None and int(chapter_without_skill[0]) == 0
        without_domain = con.execute(
            f"""
            SELECT COUNT(*) FROM subjects s
            WHERE s.code IN ({",".join(repr(c) for c in active_subjects)})
              AND NOT EXISTS (
                SELECT 1 FROM curriculum_domains d
                WHERE d.subject_id = s.subject_id
                  AND d.code NOT LIKE '%_CORE'
              )
            """
        ).fetchone()
        assert without_domain is not None and int(without_domain[0]) == 0
    finally:
        con.close()


def test_package_paths_documented() -> None:
    assert (PROJECT_ROOT / "scripts" / "rebuild_3e_curriculum.py").exists()
    assert (PROJECT_ROOT / "migrations" / "brevet_content" / "018_lcai_0039_curriculum_rebuild.sql").exists()
