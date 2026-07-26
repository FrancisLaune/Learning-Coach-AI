from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from domain.content.factory import CanonicalContentType, CurriculumTarget
from infrastructure.repositories.content_factory import DuckDBContentFactoryRepository
from scripts.report_content_expansion import _coverage_report, _generation_metrics
from scripts.run_content_expansion import _completed_keys, gap_key
from services.content.expansion import (
    ActiveSkillCoverage,
    ContentSlot,
    CoverageGap,
    coverage_gaps,
    coverage_status,
    required_slots,
)


def skill(
    *,
    grade: str = "FR-3E",
    subject: str = "MATHEMATICS",
    approved: dict[ContentSlot, int] | None = None,
    draft: dict[ContentSlot, int] | None = None,
    prerequisites: tuple[str, ...] = (),
    downstream: int = 0,
) -> ActiveSkillCoverage:
    return ActiveSkillCoverage(
        CurriculumTarget("FR-COLLEGE", grade, subject, "CHAPTER", "SKILL"),
        grade,
        subject,
        "Chapter",
        "Skill",
        (),
        prerequisites,
        downstream,
        approved or {},
        draft or {},
    )


def test_authoritative_scope_discovers_only_4e_and_3e_active_placements() -> None:
    rows = DuckDBContentFactoryRepository().active_skill_coverage()
    assert len(rows) == 372
    assert Counter(row.target.grade_code for row in rows) == {"FR-3E": 196, "FR-4E": 176}
    assert {row.target.grade_code for row in rows} == {"FR-4E", "FR-3E"}
    assert all(DuckDBContentFactoryRepository().validate_target(row.target) == () for row in rows)


def test_core_target_is_non_cartesian_and_subject_appropriate() -> None:
    mathematics = required_slots(skill())
    other = required_slots(skill(subject="HISTORY"))
    assert ContentSlot(CanonicalContentType.PRACTICE, 1) in mathematics
    assert ContentSlot(CanonicalContentType.PRACTICE, 3) in mathematics
    assert other == (
        ContentSlot(CanonicalContentType.PRACTICE, 2),
        ContentSlot(CanonicalContentType.ASSESSMENT, 2),
    )


def test_dependency_signal_adds_diagnostic_and_remediation() -> None:
    slots = required_slots(skill(prerequisites=("PREREQUISITE",)))
    assert ContentSlot(CanonicalContentType.DIAGNOSTIC, 2) in slots
    assert ContentSlot(CanonicalContentType.REMEDIATION, 1) in slots


def test_approved_and_draft_both_reuse_existing_slots() -> None:
    practice = ContentSlot(CanonicalContentType.PRACTICE, 2)
    assessment = ContentSlot(CanonicalContentType.ASSESSMENT, 2)
    row = skill(subject="HISTORY", approved={practice: 1}, draft={assessment: 1})
    assert coverage_gaps((row,)) == ()
    assert coverage_status(row) == "TARGET_COMPLETE"


def test_coverage_status_counts_slots_not_duplicate_records() -> None:
    practice = ContentSlot(CanonicalContentType.PRACTICE, 2)
    assessment = ContentSlot(CanonicalContentType.ASSESSMENT, 2)
    row = skill(subject="HISTORY", draft={practice: 3, assessment: 2})
    assert coverage_status(row) == "TARGET_COMPLETE"


def test_missing_coverage_generates_only_missing_slots() -> None:
    practice = ContentSlot(CanonicalContentType.PRACTICE, 2)
    row = skill(subject="HISTORY", approved={practice: 1})
    gaps = coverage_gaps((row,))
    assert len(gaps) == 1
    assert gaps[0].slot == ContentSlot(CanonicalContentType.ASSESSMENT, 2)
    assert gaps[0].request().quantity == 1


def test_priority_order_matches_ticket() -> None:
    rows = (
        skill(grade="FR-4E", subject="HISTORY"),
        skill(grade="FR-3E", subject="HISTORY"),
        skill(grade="FR-4E", subject="FRENCH"),
        skill(grade="FR-3E", subject="MATHEMATICS"),
    )
    priorities = [gap.priority for gap in coverage_gaps(rows)]
    assert priorities == sorted(priorities)
    assert set(priorities) == {1, 2, 3, 4}


def test_gap_key_is_stable_for_idempotent_resume() -> None:
    gap = CoverageGap(skill(subject="HISTORY"), ContentSlot(CanonicalContentType.PRACTICE, 2), 3)
    assert gap_key(gap) == gap_key(gap)
    assert gap_key(gap).endswith("|practice|2")


def test_completed_export_supports_resume_after_interruption(tmp_path: Path) -> None:
    output = tmp_path / "progress.jsonl"
    output.write_text(
        "\n".join(
            (
                json.dumps({"gap_key": "first", "final_result": "PERSISTED_DRAFT"}),
                json.dumps({"gap_key": "second", "final_result": "FINAL_REJECT"}),
                json.dumps({"gap_key": "duplicate", "final_result": "DUPLICATE_OR_REVALIDATION_REJECT"}),
            )
        ),
        encoding="utf-8",
    )
    assert _completed_keys(output) == {"first", "second", "duplicate"}
    assert _completed_keys(output, include_rejected=False) == {"first"}


def test_complete_expansion_has_no_remaining_structural_gap() -> None:
    rows = DuckDBContentFactoryRepository().active_skill_coverage()
    assert coverage_gaps(rows) == ()


def test_existing_0012b_drafts_are_visible_to_general_coverage() -> None:
    repository = DuckDBContentFactoryRepository()
    rows = repository.active_skill_coverage()
    assert sum(sum(row.draft.values()) for row in rows) >= 88
    assert sum(repository.draft_pilot_coverage().values()) == 88
    assert sum(row.approved_count for row in repository.approved_coverage()) == 68


def test_coverage_report_contains_every_authoritative_skill() -> None:
    rows = DuckDBContentFactoryRepository().active_skill_coverage()
    report = _coverage_report(rows)
    assert "Grade | Subject | Skills | Core covered" in report
    assert all(row.target.primary_skill_code in report for row in rows)


def test_metrics_do_not_relabel_corrective_run_as_first_pass() -> None:
    base = {
        "gap_key": "same",
        "grade": "FR-3E",
        "subject": "MATHEMATICS",
        "content_type": "practice",
        "difficulty": 2,
        "elapsed_seconds": 1,
    }
    records = [
        {
            **base,
            "attempts": [{"result": "REJECT", "issues": []}, {"result": "REJECT", "issues": []}],
            "final_result": "FINAL_REJECT",
        },
        {
            **base,
            "attempts": [
                {
                    "result": "PASS",
                    "issues": [],
                    "candidate": {
                        "answer": {"kind": "numeric"},
                        "provenance": {"usage": {"total_tokens": 10}},
                    },
                }
            ],
            "final_result": "PERSISTED_DRAFT",
        },
    ]
    metrics = _generation_metrics(records)
    assert metrics["requests"] == 1
    assert metrics["generation_executions"] == 2
    assert metrics["first"] == {"REJECT": 1}
    assert metrics["final"] == {"PERSISTED_DRAFT": 1}
