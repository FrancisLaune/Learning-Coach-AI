"""Home subject boards — averages and assignment cards."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from domain.unified_experience.models import ASSIGNMENT_KIND_EVALUATION, AssignmentStatus
from services.student_guidance.service import StudentGuidanceService


def _hw(
    homework_id: int,
    subject: str,
    *,
    status: AssignmentStatus = AssignmentStatus.COMPLETED,
    score: float | None = 80.0,
    is_evaluation: bool = False,
    session_id: int | None = 10,
) -> SimpleNamespace:
    return SimpleNamespace(
        homework_id=homework_id,
        subject_label=subject,
        status=status,
        exercise_count=5,
        session_id=session_id,
        is_evaluation=is_evaluation,
        assignment_kind=ASSIGNMENT_KIND_EVALUATION if is_evaluation else "HOMEWORK",
        target_duration_minutes=30,
        due_at=None,
        created_at=datetime.now(tz=UTC),
    )


def test_subject_boards_compute_overall_and_per_subject_averages() -> None:
    homework = MagicMock()
    scores = {1: 100.0, 2: 50.0, 3: 80.0}
    homework.repository.homework_overall_score.side_effect = lambda hid: scores.get(int(hid))
    service = StudentGuidanceService(
        experience=MagicMock(),
        homework=homework,
        coach=MagicMock(),
        orchestrator=MagicMock(),
        vt_repository=MagicMock(),
    )
    items = (
        _hw(1, "Mathématiques", score=100.0, is_evaluation=True),
        _hw(2, "Mathématiques", score=50.0),
        _hw(3, "Français", score=80.0, is_evaluation=True),
        _hw(4, "Français", status=AssignmentStatus.READY, score=None, session_id=None),
    )
    boards, overall = service._subject_boards(items)
    assert overall == 15.3  # (20 + 10 + 16) / 3
    assert [board.subject_label for board in boards] == ["Français", "Mathématiques"]
    maths = next(board for board in boards if board.subject_label == "Mathématiques")
    assert maths.average_out_of_20 == 15.0
    assert maths.assignment_count == 2
    ready = next(card for board in boards for card in board.assignments if card.homework_id == 4)
    assert ready.can_delete is True
    assert ready.can_retake is False
    assert ready.can_view_corrections is False
    done = next(card for board in boards for card in board.assignments if card.homework_id == 1)
    assert done.can_view_corrections is True
    assert done.can_retake is True
    assert done.score_out_of_20 == 20.0
