"""DuckDB persistence for the Virtual Teacher feature."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from domain.virtual_teacher.models import (
    VirtualTeacherMessage,
    VirtualTeacherPreferences,
    VirtualTeacherSession,
    VirtualTeacherSummary,
)
from infrastructure.database.v2 import connect_v2


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)


class DuckDBVirtualTeacherRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def parent_authorized(self, parent_ref: str, learner_id: int) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT 1 FROM learner_guardian_links
                WHERE guardian_external_ref=? AND learner_id=? AND active AND revoked_at IS NULL""",
                [parent_ref, learner_id],
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def learner_exists(self, learner_id: int) -> bool:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute("SELECT 1 FROM learners WHERE id=?", [learner_id]).fetchone()
            return row is not None
        finally:
            connection.close()

    def get_preferences(self, learner_id: int) -> VirtualTeacherPreferences | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT id,learner_id,teacher_profile,teacher_name,voice_id,tone,response_length,
                help_level,audio_enabled,feature_enabled,parent_locked,created_at,updated_at
                FROM virtual_teacher_preferences WHERE learner_id=?""",
                [learner_id],
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return self._preferences_from_row(row)

    def ensure_preferences(self, learner_id: int) -> VirtualTeacherPreferences:
        existing = self.get_preferences(learner_id)
        if existing is not None:
            return existing
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """INSERT INTO virtual_teacher_preferences
                (learner_id,teacher_profile,teacher_name,voice_id,tone,response_length,help_level,
                 audio_enabled,feature_enabled,parent_locked)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                RETURNING id,learner_id,teacher_profile,teacher_name,voice_id,tone,response_length,
                help_level,audio_enabled,feature_enabled,parent_locked,created_at,updated_at""",
                [
                    learner_id,
                    "TEACHER_FEMALE_01",
                    "Emma",
                    "warm_female",
                    "encouraging",
                    "normal",
                    2,
                    True,
                    False,
                    False,
                ],
            ).fetchone()
        finally:
            connection.close()
        return self._preferences_from_row(row)

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
    ) -> VirtualTeacherPreferences:
        self.ensure_preferences(learner_id)
        updates: list[str] = ["updated_at=now()"]
        params: list[Any] = []
        mapping = {
            "teacher_profile": teacher_profile,
            "teacher_name": teacher_name,
            "voice_id": voice_id,
            "tone": tone,
            "response_length": response_length,
            "help_level": help_level,
            "audio_enabled": audio_enabled,
            "feature_enabled": feature_enabled,
            "parent_locked": parent_locked,
        }
        for column, value in mapping.items():
            if value is not None:
                updates.append(f"{column}=?")
                params.append(value)
        params.append(learner_id)
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                f"UPDATE virtual_teacher_preferences SET {', '.join(updates)} WHERE learner_id=?",
                params,
            )
        finally:
            connection.close()
        saved = self.get_preferences(learner_id)
        if saved is None:
            raise RuntimeError("VIRTUAL_TEACHER_PREFERENCES_SAVE_FAILED")
        return saved

    def create_session(
        self,
        *,
        learner_id: int,
        actor_type: str,
        actor_ref: str,
        subject_id: int | None = None,
        skill_id: int | None = None,
        exercise_ref: str | None = None,
    ) -> VirtualTeacherSession:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """INSERT INTO virtual_teacher_sessions
                (learner_id,actor_type,actor_ref,subject_id,skill_id,exercise_ref,status)
                VALUES (?,?,?,?,?,?,'ACTIVE')
                RETURNING id,learner_id,actor_type,actor_ref,subject_id,skill_id,exercise_ref,
                status,started_at,ended_at""",
                [learner_id, actor_type, actor_ref, subject_id, skill_id, exercise_ref],
            ).fetchone()
        finally:
            connection.close()
        return self._session_from_row(row)

    def get_session(self, session_id: int) -> VirtualTeacherSession | None:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            row = connection.execute(
                """SELECT id,learner_id,actor_type,actor_ref,subject_id,skill_id,exercise_ref,
                status,started_at,ended_at FROM virtual_teacher_sessions WHERE id=?""",
                [session_id],
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return self._session_from_row(row)

    def complete_session(self, session_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """UPDATE virtual_teacher_sessions
                SET status='COMPLETED', ended_at=now(), updated_at=now()
                WHERE id=? AND status='ACTIVE'""",
                [session_id],
            )
        finally:
            connection.close()

    def append_message(
        self,
        *,
        session_id: int,
        message_role: str,
        content: str,
        response_type: str | None = None,
    ) -> VirtualTeacherMessage:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """INSERT INTO virtual_teacher_messages
                (session_id,message_role,response_type,content)
                VALUES (?,?,?,?)
                RETURNING id,session_id,message_role,response_type,content,created_at""",
                [session_id, message_role, response_type, content],
            ).fetchone()
        finally:
            connection.close()
        return VirtualTeacherMessage(
            id=int(row[0]),
            session_id=int(row[1]),
            message_role=str(row[2]),
            response_type=row[3],
            content=str(row[4]),
            created_at=_parse_ts(row[5]),
        )

    def list_messages(self, session_id: int) -> tuple[VirtualTeacherMessage, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT id,session_id,message_role,response_type,content,created_at
                FROM virtual_teacher_messages WHERE session_id=? ORDER BY created_at,id""",
                [session_id],
            ).fetchall()
        finally:
            connection.close()
        return tuple(
            VirtualTeacherMessage(
                id=int(row[0]),
                session_id=int(row[1]),
                message_role=str(row[2]),
                response_type=row[3],
                content=str(row[4]),
                created_at=_parse_ts(row[5]),
            )
            for row in rows
        )

    def save_summary(
        self,
        *,
        session_id: int,
        skills_worked: tuple[str, ...],
        difficulties: tuple[str, ...],
        successful_elements: tuple[str, ...],
        next_action: str | None,
    ) -> VirtualTeacherSummary:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                """INSERT INTO virtual_teacher_summaries
                (session_id,skills_worked,difficulties,successful_elements,next_action)
                VALUES (?,?,?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET
                skills_worked=excluded.skills_worked,
                difficulties=excluded.difficulties,
                successful_elements=excluded.successful_elements,
                next_action=excluded.next_action,
                created_at=now()
                RETURNING session_id,skills_worked,difficulties,successful_elements,next_action,created_at""",
                [
                    session_id,
                    json.dumps(list(skills_worked)),
                    json.dumps(list(difficulties)),
                    json.dumps(list(successful_elements)),
                    next_action,
                ],
            ).fetchone()
        finally:
            connection.close()
        return VirtualTeacherSummary(
            session_id=int(row[0]),
            skills_worked=tuple(json.loads(row[1])),
            difficulties=tuple(json.loads(row[2])),
            successful_elements=tuple(json.loads(row[3])),
            next_action=row[4],
            created_at=_parse_ts(row[5]),
        )

    def record_event(
        self,
        *,
        learner_id: int,
        event_type: str,
        session_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO virtual_teacher_events
                (learner_id,session_id,event_type,metadata_json)
                VALUES (?,?,?,?)""",
                [learner_id, session_id, event_type, json.dumps(metadata or {})],
            )
        finally:
            connection.close()

    def delete_conversation_history(self, learner_id: int) -> None:
        connection = connect_v2(self.database_path)
        try:
            session_ids = [
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM virtual_teacher_sessions WHERE learner_id=?",
                    [learner_id],
                ).fetchall()
            ]
            for session_id in session_ids:
                connection.execute("DELETE FROM virtual_teacher_messages WHERE session_id=?", [session_id])
                connection.execute("DELETE FROM virtual_teacher_summaries WHERE session_id=?", [session_id])
            connection.execute("DELETE FROM virtual_teacher_sessions WHERE learner_id=?", [learner_id])
            connection.execute(
                "DELETE FROM virtual_teacher_events WHERE learner_id=? AND session_id IS NOT NULL",
                [learner_id],
            )
        finally:
            connection.close()

    @staticmethod
    def _preferences_from_row(row: tuple[Any, ...]) -> VirtualTeacherPreferences:
        return VirtualTeacherPreferences(
            id=int(row[0]),
            learner_id=int(row[1]),
            teacher_profile=str(row[2]),
            teacher_name=row[3],
            voice_id=str(row[4]),
            tone=str(row[5]),
            response_length=str(row[6]),
            help_level=int(row[7]),
            audio_enabled=bool(row[8]),
            feature_enabled=bool(row[9]),
            parent_locked=bool(row[10]),
            created_at=_parse_ts(row[11]),
            updated_at=_parse_ts(row[12]),
        )

    @staticmethod
    def _session_from_row(row: tuple[Any, ...]) -> VirtualTeacherSession:
        return VirtualTeacherSession(
            id=int(row[0]),
            learner_id=int(row[1]),
            actor_type=str(row[2]),
            actor_ref=str(row[3]),
            subject_id=int(row[4]) if row[4] is not None else None,
            skill_id=int(row[5]) if row[5] is not None else None,
            exercise_ref=row[6],
            status=str(row[7]),
            started_at=_parse_ts(row[8]),
            ended_at=_parse_ts(row[9]) if row[9] is not None else None,
        )
