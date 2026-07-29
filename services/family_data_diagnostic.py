"""Scan and safe repair for inconsistent family learner data (LCAI-0015B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from infrastructure.repositories.virtual_teacher import DuckDBVirtualTeacherRepository
from services.unified_experience import UnifiedExperienceRepository


class StudentAccountProbe(Protocol):
    def has_active(self, learner_external_ref: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class FamilyDataIssue:
    code: str
    learner_id: int
    learner_name: str
    external_ref: str
    message: str


class FamilyDataDiagnosticService:
    ISSUE_MISSING_ACCOUNT = "MISSING_STUDENT_ACCOUNT"
    ISSUE_MISSING_VT_PREFS = "MISSING_VT_PREFERENCES"
    ISSUE_ARCHIVED_ACTIVE_ACCOUNT = "ARCHIVED_WITH_ACTIVE_ACCOUNT"

    def __init__(
        self,
        repository: UnifiedExperienceRepository,
        *,
        virtual_teacher_repository: DuckDBVirtualTeacherRepository | None = None,
        account_probe: StudentAccountProbe | None = None,
    ) -> None:
        self.repository = repository
        self.virtual_teacher_repository = virtual_teacher_repository or DuckDBVirtualTeacherRepository()
        self.account_probe = account_probe

    def scan_for_parent(self, parent_ref: str) -> tuple[FamilyDataIssue, ...]:
        issues: list[FamilyDataIssue] = []
        for archived in (False, True):
            for learner_id, learner_name in self.repository.list_linked_learners(parent_ref, archived=archived):
                profile = self.repository.learner_management_profile(learner_id, include_archived=True)
                if self.account_probe is not None:
                    active = self.account_probe.has_active(profile.external_ref)
                    if not active and not archived:
                        issues.append(
                            FamilyDataIssue(
                                self.ISSUE_MISSING_ACCOUNT,
                                learner_id,
                                learner_name,
                                profile.external_ref,
                                "Compte élève manquant ou inactif.",
                            )
                        )
                    if active and archived:
                        issues.append(
                            FamilyDataIssue(
                                self.ISSUE_ARCHIVED_ACTIVE_ACCOUNT,
                                learner_id,
                                learner_name,
                                profile.external_ref,
                                "Élève archivé mais compte encore actif.",
                            )
                        )
                if self.virtual_teacher_repository.get_preferences(learner_id) is None:
                    issues.append(
                        FamilyDataIssue(
                            self.ISSUE_MISSING_VT_PREFS,
                            learner_id,
                            learner_name,
                            profile.external_ref,
                            "Préférences Professeur IA absentes.",
                        )
                    )
        return tuple(issues)

    def repair(self, parent_ref: str, issue: FamilyDataIssue) -> bool:
        if not self.repository.parent_authorized(parent_ref, issue.learner_id):
            raise PermissionError("PARENT_ACCESS_DENIED")
        if issue.code == self.ISSUE_MISSING_VT_PREFS:
            if self.virtual_teacher_repository.get_preferences(issue.learner_id) is not None:
                return False
            self.virtual_teacher_repository.ensure_preferences(issue.learner_id)
            return True
        if issue.code == self.ISSUE_ARCHIVED_ACTIVE_ACCOUNT and self.account_probe is not None:
            from infrastructure.database.legacy_gateway import deactivate_student_account

            parent_user_id = int(parent_ref)
            deactivate_student_account(parent_user_id, issue.external_ref)
            return True
        return False
