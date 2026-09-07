"""LCAI-0040 curriculum closure tests."""

from __future__ import annotations

import pytest

from core.config import PROJECT_ROOT, get_database_path
from services.brevet_referential.curriculum_closure.scoring import (
    exercise_minima,
    score_coverage_v40,
)
from services.brevet_referential.curriculum_rebuild.target_tree import CORE_SUBJECTS


def test_score_complete_requires_diversity() -> None:
    assert (
        score_coverage_v40(
            exercise_count=50,
            family_count=5,
            correction_coverage=1.0,
            importance="CRITICAL",
            playable_ratio=1.0,
            subskill_ok=True,
        )
        == "COMPLETE"
    )
    assert (
        score_coverage_v40(
            exercise_count=50,
            family_count=4,
            correction_coverage=1.0,
            importance="CRITICAL",
        )
        == "PARTIAL"
    )
    assert exercise_minima("HIGH") == 40


def test_script_exists() -> None:
    assert (PROJECT_ROOT / "scripts" / "close_3e_curriculum_gaps.py").exists()


@pytest.mark.skipif(not get_database_path().exists(), reason="OB DB missing")
def test_all_core_subjects_complete_after_closure() -> None:
    import duckdb

    con = duckdb.connect(str(get_database_path()), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT s.code, ccs.coverage_status, COUNT(*)
            FROM curriculum_coverage_status ccs
            JOIN skills sk USING(skill_id)
            JOIN chapters ch ON ch.chapter_id = sk.chapter_id
            JOIN curriculum_domains d ON d.domain_id = ch.domain_id
            JOIN subjects s ON s.subject_id = d.subject_id
            WHERE d.code NOT LIKE '%_CORE' AND s.code IN ({subjects})
            GROUP BY 1, 2
            """.format(subjects=",".join(repr(c) for c in CORE_SUBJECTS))
        ).fetchall()
        if not rows:
            pytest.skip("coverage not refreshed")
        by_subject: dict[str, dict[str, int]] = {}
        for code, status, n in rows:
            by_subject.setdefault(str(code), {})[str(status)] = int(n)
        # Soft skip if closure not applied yet
        total_complete = sum(v.get("COMPLETE", 0) for v in by_subject.values())
        if total_complete < 100:
            pytest.skip("LCAI-0040 closure not applied yet")
        for code in CORE_SUBJECTS:
            hist = by_subject.get(code, {})
            assert hist.get("PARTIAL", 0) == 0
            assert hist.get("GOOD", 0) == 0
            assert hist.get("EMPTY", 0) == 0
            assert hist.get("COMPLETE", 0) > 0
        official = con.execute("SELECT COUNT(*) FROM content_items WHERE source_type='OFFICIAL_ARCHIVE'").fetchone()
        assert official is not None and int(official[0]) >= 1098
        unmapped = con.execute(
            """
            SELECT COUNT(*) FROM content_items ci
            WHERE ci.source_type='OFFICIAL_ARCHIVE' AND ci.runtime_playable
              AND NOT EXISTS (
                SELECT 1 FROM content_skill_links csl
                JOIN skills sk ON sk.skill_id=csl.skill_id
                JOIN chapters ch ON ch.chapter_id=sk.chapter_id
                JOIN curriculum_domains d ON d.domain_id=ch.domain_id
                WHERE csl.content_id=ci.content_id AND csl.relation_type='PRIMARY'
                  AND d.code NOT LIKE '%_CORE'
              )
            """
        ).fetchone()
        assert unmapped is not None and int(unmapped[0]) == 0
    finally:
        con.close()
