"""LCAI-0036 — human pedagogical decision services with audit trail."""

from __future__ import annotations

from typing import Any

from infrastructure.repositories.brevet_content.store import BrevetContentStore
from services.brevet_referential.pedagogical_validation import CURRICULUM_CODE, RULESET_VERSION, VALIDATOR_VERSION


def _record_history(
    store: BrevetContentStore,
    *,
    content_id: int,
    field_name: str,
    old_value: str | None,
    new_value: str | None,
    actor_type: str,
    actor_id: str | None,
    reason: str,
) -> None:
    store.execute(
        """
        INSERT INTO pedagogical_validation_history(
            content_id, field_name, old_value, new_value, actor_type, actor_id,
            reason, curriculum_version_code, validator_version, ruleset_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            content_id,
            field_name,
            old_value,
            new_value,
            actor_type,
            actor_id,
            reason,
            CURRICULUM_CODE,
            VALIDATOR_VERSION,
            RULESET_VERSION,
        ],
    )


def _current_assessment(store: BrevetContentStore, content_id: int) -> dict[str, Any] | None:
    row = store.fetchone(
        """
        SELECT pedagogical_validation_status, curriculum_2027_compatible, compatibility_reason,
               primary_skill_code
        FROM content_pedagogical_assessments WHERE content_id = ?
        """,
        [content_id],
    )
    if not row:
        return None
    return {
        "pedagogical_validation_status": row[0],
        "curriculum_2027_compatible": row[1],
        "compatibility_reason": row[2],
        "primary_skill_code": row[3],
    }


def approve_question(
    store: BrevetContentStore,
    content_id: int,
    *,
    actor_id: str,
    reason: str,
    set_compatible_true: bool = False,
) -> dict[str, Any]:
    current = _current_assessment(store, content_id) or {}
    if set_compatible_true and not reason:
        raise ValueError("compatibility TRUE requires an explicit reason")
    store.execute(
        """
        INSERT INTO content_validation_overrides(
            content_id, pedagogical_validation_status, curriculum_2027_compatible,
            compatibility_reason, reason, actor_type, actor_id
        ) VALUES (?, 'VALIDATED', ?, ?, ?, 'HUMAN_REVIEWER', ?)
        ON CONFLICT (content_id) DO UPDATE SET
          pedagogical_validation_status = 'VALIDATED',
          curriculum_2027_compatible = COALESCE(excluded.curriculum_2027_compatible, content_validation_overrides.curriculum_2027_compatible),
          compatibility_reason = COALESCE(excluded.compatibility_reason, content_validation_overrides.compatibility_reason),
          reason = excluded.reason,
          actor_id = excluded.actor_id
        """,
        [
            content_id,
            "TRUE" if set_compatible_true else current.get("curriculum_2027_compatible"),
            reason if set_compatible_true else current.get("compatibility_reason"),
            reason,
            actor_id,
        ],
    )
    _record_history(
        store,
        content_id=content_id,
        field_name="pedagogical_validation_status",
        old_value=str(current.get("pedagogical_validation_status")),
        new_value="VALIDATED",
        actor_type="HUMAN_REVIEWER",
        actor_id=actor_id,
        reason=reason,
    )
    return {"content_id": content_id, "status": "VALIDATED"}


def reject_question(
    store: BrevetContentStore,
    content_id: int,
    *,
    actor_id: str,
    reason: str,
) -> dict[str, Any]:
    current = _current_assessment(store, content_id) or {}
    store.execute(
        """
        INSERT INTO content_validation_overrides(
            content_id, pedagogical_validation_status, reason, actor_type, actor_id
        ) VALUES (?, 'REJECTED', ?, 'HUMAN_REVIEWER', ?)
        ON CONFLICT (content_id) DO UPDATE SET
          pedagogical_validation_status = 'REJECTED',
          reason = excluded.reason,
          actor_id = excluded.actor_id
        """,
        [content_id, reason, actor_id],
    )
    _record_history(
        store,
        content_id=content_id,
        field_name="pedagogical_validation_status",
        old_value=str(current.get("pedagogical_validation_status")),
        new_value="REJECTED",
        actor_type="HUMAN_REVIEWER",
        actor_id=actor_id,
        reason=reason,
    )
    return {"content_id": content_id, "status": "REJECTED"}


def change_compatibility(
    store: BrevetContentStore,
    content_id: int,
    *,
    compatible: str,
    reason: str,
    actor_id: str,
) -> dict[str, Any]:
    if compatible not in {"TRUE", "FALSE", "REVIEW"}:
        raise ValueError("compatible must be TRUE|FALSE|REVIEW")
    if compatible == "TRUE" and not reason:
        raise ValueError("TRUE requires reason")
    current = _current_assessment(store, content_id) or {}
    store.execute(
        """
        INSERT INTO content_validation_overrides(
            content_id, curriculum_2027_compatible, compatibility_reason, reason, actor_type, actor_id
        ) VALUES (?, ?, ?, ?, 'HUMAN_REVIEWER', ?)
        ON CONFLICT (content_id) DO UPDATE SET
          curriculum_2027_compatible = excluded.curriculum_2027_compatible,
          compatibility_reason = excluded.compatibility_reason,
          reason = excluded.reason,
          actor_id = excluded.actor_id
        """,
        [content_id, compatible, reason, reason, actor_id],
    )
    _record_history(
        store,
        content_id=content_id,
        field_name="curriculum_2027_compatible",
        old_value=str(current.get("curriculum_2027_compatible")),
        new_value=compatible,
        actor_type="HUMAN_REVIEWER",
        actor_id=actor_id,
        reason=reason,
    )
    return {"content_id": content_id, "curriculum_2027_compatible": compatible, "reason": reason}
