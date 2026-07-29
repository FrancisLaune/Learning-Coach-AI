"""Family-level learner listing, archive and restore orchestration (LCAI-0015B)."""

from __future__ import annotations

from typing import Protocol

from services.unified_experience import LearnerProfileManagementService, UnifiedExperienceRepository


class StudentAccountGateway(Protocol):
    def deactivate(self, parent_user_id: int, learner_external_ref: str) -> None: ...


class FamilyLearnerManagementService:
    def __init__(
        self,
        repository: UnifiedExperienceRepository,
        profile_manager: LearnerProfileManagementService,
        account_gateway: StudentAccountGateway | None = None,
    ) -> None:
        self.repository = repository
        self.profile_manager = profile_manager
        self.account_gateway = account_gateway

    def list_active_learners(self, parent_ref: str) -> tuple[tuple[int, str], ...]:
        return self.repository.list_linked_learners(parent_ref, archived=False)

    def list_archived_learners(self, parent_ref: str) -> tuple[tuple[int, str], ...]:
        return self.repository.list_linked_learners(parent_ref, archived=True)

    def learner_last_activity(self, learner_id: int) -> str | None:
        return self.repository.learner_last_activity_label(learner_id)

    def archive(self, parent_ref: str, learner_id: int, parent_user_id: int) -> None:
        profile = self.profile_manager.get(parent_ref, learner_id)
        self.repository.archive_learner(parent_ref, learner_id)
        if self.account_gateway is not None:
            self.account_gateway.deactivate(parent_user_id, profile.external_ref)

    def restore(self, parent_ref: str, learner_id: int) -> None:
        if not self.repository.learner_is_archived(learner_id):
            raise ValueError("Cet élève n'est pas archivé.")
        self.profile_manager._authorize(parent_ref, learner_id)
        self.repository.restore_learner(parent_ref, learner_id)
