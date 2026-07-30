"""Stateless deterministic orchestration for Learning Sessions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Protocol

from domain.learning_session.models import (
    ActivityStatus,
    LearningSession,
    SessionActivity,
    SessionCheckpoint,
    SessionEvent,
    SessionStatus,
    SessionSummary,
)
from domain.learning_session.repositories import LearningSessionRepository, SessionAuditRepository
from services.learning_session.models import (
    ActivityExecutionState,
    ActivityExecutionStatus,
    ExecutableActivity,
    ExecutionProposal,
)


class SessionSource(Protocol):
    def load_execution_proposal(self, proposal_id: int) -> ExecutionProposal: ...


class SessionFactory:
    def create(self, proposal: ExecutionProposal, now: datetime) -> LearningSession:
        if proposal.absence_code or not proposal.activities:
            raise ValueError("A session requires a non-empty valid recommendation")
        content_versions = sorted({str(item.content_version_id) for item in proposal.activities})
        planned_seconds = proposal.available_seconds
        if proposal.objective == "homework" or proposal.stable_id.startswith("homework:"):
            activity_seconds = sum(item.estimated_duration_seconds for item in proposal.activities)
            planned_seconds = max(planned_seconds, activity_seconds)
        return LearningSession(
            0,
            proposal.learner_id,
            proposal.journey_version_id,
            proposal.proposal_id,
            SessionStatus.CREATED,
            now,
            planned_seconds,
            "learning-coach-v2",
            "curriculum-v1",
            ",".join(content_versions),
            proposal.decision_engine_version,
            "deterministic-assessment-v1",
        )


class SessionScheduler:
    def schedule(self, proposal: ExecutionProposal) -> tuple[ExecutableActivity, ...]:
        if proposal.absence_code:
            raise ValueError(f"Recommendation cannot execute: {proposal.absence_code}")
        seen: set[tuple[int, int]] = set()
        elapsed = 0
        ordered: list[ExecutableActivity] = []
        for activity in sorted(proposal.activities, key=lambda item: item.order):
            identity = (activity.content_id, activity.content_version_id)
            if identity in seen:
                raise ValueError("Duplicate activity in recommendation")
            if not activity.approved or not activity.current_version:
                raise ValueError("Only current Approved content may execute")
            if not 1 <= activity.difficulty <= 5 or activity.estimated_duration_seconds <= 0:
                raise ValueError("Activity difficulty or duration is invalid")
            if not activity.question_ids or not activity.has_assessment:
                raise ValueError("Activity requires questions and an assessment")
            if not activity.objective_compatible or not activity.prerequisites_satisfied:
                raise ValueError("Activity objective or prerequisites are incompatible")
            elapsed += activity.estimated_duration_seconds
            is_homework = proposal.objective == "homework" or proposal.stable_id.startswith("homework:")
            if not is_homework and elapsed > proposal.available_seconds:
                raise ValueError("Recommendation exceeds the available duration")
            seen.add(identity)
            ordered.append(activity)
        if not ordered:
            raise ValueError("A session owns at least one activity")
        return tuple(ordered)


class ActivityPipelineBuilder:
    def build(self, session_id: int, activities: tuple[ExecutableActivity, ...]) -> tuple[SessionActivity, ...]:
        return tuple(
            SessionActivity(
                0,
                session_id,
                item.content_id,
                item.content_version_id,
                position,
                item.activity_type,
                item.difficulty,
                item.estimated_duration_seconds,
            )
            for position, item in enumerate(activities, 1)
        )


class SessionStateManager:
    _transitions = {
        ActivityExecutionStatus.NOT_STARTED: ActivityExecutionStatus.LOADING,
        ActivityExecutionStatus.LOADING: ActivityExecutionStatus.READY,
        ActivityExecutionStatus.READY: ActivityExecutionStatus.DISPLAYED,
        ActivityExecutionStatus.DISPLAYED: ActivityExecutionStatus.ANSWERING,
        ActivityExecutionStatus.ANSWERING: ActivityExecutionStatus.SUBMITTED,
        ActivityExecutionStatus.SUBMITTED: ActivityExecutionStatus.ASSESSED,
        ActivityExecutionStatus.ASSESSED: ActivityExecutionStatus.COMPLETED,
    }

    def advance(self, state: ActivityExecutionState) -> ActivityExecutionState:
        target = self._transitions.get(state.status)
        if target is None:
            raise ValueError("A completed activity cannot advance")
        return replace(
            state,
            status=target,
            answer_locked=target
            in {
                ActivityExecutionStatus.SUBMITTED,
                ActivityExecutionStatus.ASSESSED,
                ActivityExecutionStatus.COMPLETED,
            },
        )


class ActivityRunner:
    def __init__(self, repository: LearningSessionRepository) -> None:
        self.repository = repository

    def start(self, session: LearningSession, activity_id: int) -> SessionActivity:
        if session.status is not SessionStatus.RUNNING:
            raise ValueError("Activity execution requires a RUNNING session")
        activity = self._find(session.session_id, activity_id)
        if activity.status is not ActivityStatus.NOT_STARTED:
            raise ValueError("Only a NOT_STARTED activity can start")
        updated = replace(activity, status=ActivityStatus.RUNNING)
        self.repository.update_activity(updated)
        return updated

    def complete(
        self, session: LearningSession, activity_id: int, score: float, mastery_delta: float
    ) -> SessionActivity:
        if session.status is not SessionStatus.RUNNING:
            raise ValueError("Activity completion requires a RUNNING session")
        activity = self._find(session.session_id, activity_id)
        if activity.status is not ActivityStatus.RUNNING:
            raise ValueError("Only a RUNNING activity can complete")
        updated = replace(
            activity,
            status=ActivityStatus.COMPLETED,
            score=score,
            mastery_delta=mastery_delta,
        )
        self.repository.update_activity(updated)
        return updated

    def _find(self, session_id: int, activity_id: int) -> SessionActivity:
        for activity in self.repository.list_activities(session_id):
            if activity.activity_id == activity_id:
                return activity
        raise KeyError(f"Unknown activity {activity_id}")


class LearningSessionService:
    def __init__(
        self,
        source: SessionSource,
        repository: LearningSessionRepository,
        audit: SessionAuditRepository,
        factory: SessionFactory | None = None,
        scheduler: SessionScheduler | None = None,
        pipeline: ActivityPipelineBuilder | None = None,
    ) -> None:
        self.source = source
        self.repository = repository
        self.audit = audit
        self.factory = factory or SessionFactory()
        self.scheduler = scheduler or SessionScheduler()
        self.pipeline = pipeline or ActivityPipelineBuilder()

    def create_session(self, proposal_id: int, now: datetime) -> LearningSession:
        proposal = self.source.load_execution_proposal(proposal_id)
        scheduled = self.scheduler.schedule(proposal)
        session = self.repository.create(self.factory.create(proposal, now))
        for activity in self.pipeline.build(session.session_id, scheduled):
            self.repository.add_activity(activity)
        self.repository.transition(session.session_id, SessionStatus.CREATED, SessionStatus.READY, now)
        self.audit.save_checkpoint(
            SessionCheckpoint(0, session.session_id, None, None, session.planned_duration_seconds, None, now)
        )
        self.audit.save_event(
            SessionEvent(
                0, session.session_id, "SESSION_CREATED", now, {"proposal_id": proposal_id}, proposal.stable_id
            )
        )
        ready = self.repository.get(session.session_id)
        if ready is None:
            raise RuntimeError("Persisted session cannot be loaded")
        return ready

    def start_session(self, session_id: int, now: datetime) -> LearningSession:
        self.repository.transition(session_id, SessionStatus.READY, SessionStatus.RUNNING, now)
        return self._required(session_id)

    def pause_session(self, session_id: int, now: datetime) -> LearningSession:
        self.repository.transition(session_id, SessionStatus.RUNNING, SessionStatus.PAUSED, now)
        return self._required(session_id)

    def resume_session(self, session_id: int, now: datetime) -> LearningSession:
        self.repository.transition(session_id, SessionStatus.PAUSED, SessionStatus.RUNNING, now)
        return self._required(session_id)

    def ensure_running(self, session_id: int, now: datetime) -> LearningSession:
        session = self._required(session_id)
        if session.status is SessionStatus.READY:
            return self.start_session(session_id, now)
        if session.status is SessionStatus.PAUSED:
            return self.resume_session(session_id, now)
        return session

    def cancel_session(self, session_id: int, now: datetime) -> LearningSession:
        current = self._required(session_id)
        self.repository.transition(session_id, current.status, SessionStatus.ABANDONED, now)
        return self._required(session_id)

    def close_session(self, session_id: int, now: datetime) -> SessionSummary:
        self._required(session_id)
        activities = self.repository.list_activities(session_id)
        if not activities or any(item.status is not ActivityStatus.COMPLETED for item in activities):
            raise ValueError("Every activity must be completed before closing")
        score = sum(item.score for item in activities) / len(activities)
        gain = sum(item.mastery_delta for item in activities)
        summary = self.audit.save_summary(SessionSummary(0, session_id, 100, 0, score, gain, (), (), None))
        self.repository.transition(session_id, SessionStatus.RUNNING, SessionStatus.COMPLETED, now)
        self.audit.save_event(SessionEvent(0, session_id, "SESSION_COMPLETED", now, {"score": score}, str(session_id)))
        return summary

    def _required(self, session_id: int) -> LearningSession:
        session = self.repository.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session {session_id}")
        return session
