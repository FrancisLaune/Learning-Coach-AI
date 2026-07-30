"""Composite notifier: decision queue + pedagogical refresh."""

from __future__ import annotations

from domain.learning.models import LearningEngineResult


class CompositePedagogicalNotifier:
    def __init__(self, decision_enqueue, pedagogical_refresh) -> None:
        self._decision_enqueue = decision_enqueue
        self._pedagogical_refresh = pedagogical_refresh

    def notify_mastery_updated(self, result: LearningEngineResult) -> None:
        self._decision_enqueue(result)
        parts = result.attempt_id.split(":")
        session_id: int | None = None
        if len(parts) >= 2 and parts[0] == "ui" and parts[1].isdigit():
            session_id = int(parts[1])
        if session_id is not None:
            try:
                self._pedagogical_refresh(
                    learner_id=result.mastery.current.learner_id,
                    session_id=session_id,
                    correlation_id=result.attempt_id,
                )
            except Exception:
                pass
