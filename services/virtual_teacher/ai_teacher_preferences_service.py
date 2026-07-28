"""Preference management for the Virtual Teacher."""

from __future__ import annotations

import re
from typing import Protocol

from domain.virtual_teacher.models import PreferencesPatch, VirtualTeacherPreferences
from services.auth.roles import AuthRole, normalize_auth_role
from services.virtual_teacher.authorization import (
    VirtualTeacherAccessError,
    authorize_parent_access,
)


class VirtualTeacherRepositoryProtocol(Protocol):
    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool: ...

    def learner_exists(self, learner_id: int) -> bool: ...

    def get_preferences(self, learner_id: int) -> VirtualTeacherPreferences | None: ...

    def ensure_preferences(self, learner_id: int) -> VirtualTeacherPreferences: ...

    def save_preferences(
        self,
        learner_id: int,
        *,
        teacher_profile: str | None = None,
        teacher_name: str | None = None,
        voice_id: str | None = None,
        tone: str | None = None,
        response_length: str | None = None,
        help_level: int | None = None,
        audio_enabled: bool | None = None,
        feature_enabled: bool | None = None,
        parent_locked: bool | None = None,
    ) -> VirtualTeacherPreferences: ...

    def delete_conversation_history(self, learner_id: int) -> None: ...


_PARENT_ONLY_FIELDS = frozenset({"feature_enabled", "parent_locked"})


class AITeacherPreferencesService:
    def __init__(self, repository: VirtualTeacherRepositoryProtocol) -> None:
        self.repository = repository

    def get_preferences(self, learner_id: int) -> VirtualTeacherPreferences:
        if not self.repository.learner_exists(learner_id):
            raise VirtualTeacherAccessError("LEARNER_NOT_FOUND")
        return self.repository.ensure_preferences(learner_id)

    def get_preferences_for_parent(
        self,
        *,
        user: dict,
        parent_ref: str,
        learner_id: int,
    ) -> VirtualTeacherPreferences:
        authorize_parent_access(
            user=user,
            parent_ref=parent_ref,
            learner_id=learner_id,
            parent_authorized=self.repository.parent_authorized(parent_ref, learner_id),
        )
        return self.get_preferences(learner_id)

    def get_preferences_for_student(
        self,
        *,
        user: dict,
        student_learner_id: int,
        learner_id: int,
    ) -> VirtualTeacherPreferences:
        if normalize_auth_role(user.get("role")) is not AuthRole.STUDENT:
            raise VirtualTeacherAccessError("STUDENT_ACCESS_DENIED")
        if int(student_learner_id) != int(learner_id):
            raise VirtualTeacherAccessError("CROSS_LEARNER_ACCESS_DENIED")
        return self.get_preferences(learner_id)

    def can_student_edit(self, preferences: VirtualTeacherPreferences, field: str) -> bool:
        if field in _PARENT_ONLY_FIELDS:
            return False
        return not preferences.parent_locked

    def save_for_parent(
        self,
        *,
        user: dict,
        parent_ref: str,
        learner_id: int,
        patch: PreferencesPatch,
    ) -> VirtualTeacherPreferences:
        authorize_parent_access(
            user=user,
            parent_ref=parent_ref,
            learner_id=learner_id,
            parent_authorized=self.repository.parent_authorized(parent_ref, learner_id),
        )
        return self._apply_patch(learner_id, patch, student_mode=False)

    def save_for_student(
        self,
        *,
        user: dict,
        student_learner_id: int,
        learner_id: int,
        patch: PreferencesPatch,
    ) -> VirtualTeacherPreferences:
        preferences = self.get_preferences_for_student(
            user=user,
            student_learner_id=student_learner_id,
            learner_id=learner_id,
        )
        if not preferences.feature_enabled:
            raise VirtualTeacherAccessError("FEATURE_DISABLED")
        if preferences.parent_locked:
            raise VirtualTeacherAccessError("PREFERENCES_LOCKED")
        for field in patch.fields:
            if field in _PARENT_ONLY_FIELDS:
                raise VirtualTeacherAccessError("PARENT_ONLY_FIELD")
            if not self.can_student_edit(preferences, field):
                raise VirtualTeacherAccessError("PREFERENCES_LOCKED")
        return self._apply_patch(learner_id, patch, student_mode=True)

    def reset_preferences(self, *, user: dict, parent_ref: str, learner_id: int) -> VirtualTeacherPreferences:
        authorize_parent_access(
            user=user,
            parent_ref=parent_ref,
            learner_id=learner_id,
            parent_authorized=self.repository.parent_authorized(parent_ref, learner_id),
        )
        return self.repository.save_preferences(
            learner_id,
            teacher_profile="TEACHER_FEMALE_01",
            teacher_name="Emma",
            voice_id="warm_female",
            tone="encouraging",
            response_length="normal",
            help_level=2,
            audio_enabled=True,
            parent_locked=False,
        )

    def delete_history(self, *, user: dict, parent_ref: str, learner_id: int) -> None:
        authorize_parent_access(
            user=user,
            parent_ref=parent_ref,
            learner_id=learner_id,
            parent_authorized=self.repository.parent_authorized(parent_ref, learner_id),
        )
        self.repository.delete_conversation_history(learner_id)

    def _apply_patch(
        self,
        learner_id: int,
        patch: PreferencesPatch,
        *,
        student_mode: bool,
    ) -> VirtualTeacherPreferences:
        if patch.teacher_name is not None:
            patch.teacher_name = _sanitize_teacher_name(patch.teacher_name)
        fields = {
            key: getattr(patch, key)
            for key in patch.fields
            if getattr(patch, key) is not None
        }
        if student_mode and any(key in _PARENT_ONLY_FIELDS for key in fields):
            raise VirtualTeacherAccessError("PARENT_ONLY_FIELD")
        return self.repository.save_preferences(learner_id, **fields)


def _sanitize_teacher_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\s\-'À-ÖØ-öø-ÿ]", "", value.strip())
    return cleaned[:32] if cleaned else "Professeur"
