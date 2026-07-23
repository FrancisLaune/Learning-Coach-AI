"""DuckDB persistence for platform deliveries and append-only audit records."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from domain.platform_runtime.models import AuditRecord, EventHandlerResult, PlatformEvent
from infrastructure.database.v2 import connect_v2


class DuckDBPlatformRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def append_pending(self, event: PlatformEvent) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO platform_event_outbox
                (event_id,event_type,payload_version,occurred_at,correlation_id,causation_id,
                 aggregate_type,aggregate_id,payload,dispatch_status)
                VALUES (?,?,?,?,?,?,?,?,?,'PENDING') ON CONFLICT(event_id) DO NOTHING""",
                [
                    event.event_id,
                    event.event_type,
                    event.payload_version,
                    event.occurred_at,
                    event.correlation_id,
                    event.causation_id,
                    event.aggregate_type,
                    event.aggregate_id,
                    json.dumps(event.payload, default=str),
                ],
            )
        finally:
            connection.close()

    def create_or_get(self, event: PlatformEvent, handler_id: str) -> str | None:
        self.append_pending(event)
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(
                "SELECT status FROM platform_event_deliveries WHERE event_id=? AND handler_id=?",
                [event.event_id, handler_id],
            ).fetchone()
            if row:
                if str(row[0]) != "COMPLETED":
                    connection.execute(
                        """UPDATE platform_event_deliveries SET status='DISPATCHING',
                        attempt_count=attempt_count+1,last_attempt_at=now()
                        WHERE event_id=? AND handler_id=?""",
                        [event.event_id, handler_id],
                    )
                return str(row[0])
            connection.execute(
                """INSERT INTO platform_event_deliveries
                (event_id,handler_id,handler_version,status,attempt_count,first_attempt_at,last_attempt_at)
                VALUES (?,?,'1.0.0','DISPATCHING',1,now(),now())""",
                [event.event_id, handler_id],
            )
            return None
        finally:
            connection.close()

    def mark_success(self, event_id: str, handler_id: str, result: EventHandlerResult) -> None:
        self._mark(event_id, handler_id, result, "COMPLETED")

    def mark_failure(self, event_id: str, handler_id: str, result: EventHandlerResult) -> None:
        status = "FAILED_RETRYABLE" if result.retryable else "FAILED_PERMANENT"
        self._mark(event_id, handler_id, result, status)

    def _mark(self, event_id: str, handler_id: str, result: EventHandlerResult, status: str) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """UPDATE platform_event_deliveries SET status=?,completed_at=CASE WHEN ?='COMPLETED' THEN now() ELSE NULL END,
                last_error_code=?,result_reference=? WHERE event_id=? AND handler_id=?""",
                [status, status, result.error_code, ",".join(result.output_references), event_id, handler_id],
            )
            counts = connection.execute(
                """SELECT count(*),count(*) FILTER (WHERE status='COMPLETED'),
                count(*) FILTER (WHERE status LIKE 'FAILED%')
                FROM platform_event_deliveries WHERE event_id=?""",
                [event_id],
            ).fetchone()
            outbox_status = (
                "COMPLETED"
                if counts and counts[0] == counts[1]
                else ("PARTIALLY_COMPLETED" if counts and counts[1] else status)
            )
            connection.execute(
                """UPDATE platform_event_outbox SET dispatch_status=?,dispatch_attempt_count=dispatch_attempt_count+1,
                completed_at=CASE WHEN ?='COMPLETED' THEN now() ELSE NULL END,last_error_code=?
                WHERE event_id=?""",
                [outbox_status, outbox_status, result.error_code, event_id],
            )
        finally:
            connection.close()

    def append(self, record: AuditRecord) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute(
                """INSERT INTO platform_audit_records
                (audit_id,category,action,occurred_at,actor_type,actor_id,learner_id,
                 resource_type,resource_id,outcome,correlation_id,causation_id,summary_code,
                 metadata,sensitivity_level)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    record.audit_id,
                    record.category,
                    record.action,
                    record.occurred_at,
                    record.actor_type,
                    record.actor_id,
                    record.learner_id,
                    record.resource_type,
                    record.resource_id,
                    record.outcome,
                    record.correlation_id,
                    record.causation_id,
                    record.summary_code,
                    json.dumps(record.metadata, default=str),
                    record.sensitivity_level,
                ],
            )
        finally:
            connection.close()

    def list_by_correlation(self, correlation_id: str) -> tuple[AuditRecord, ...]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                """SELECT audit_id,category,action,occurred_at,actor_type,actor_id,outcome,
                correlation_id,resource_type,resource_id,learner_id,causation_id,summary_code,
                metadata,sensitivity_level FROM platform_audit_records
                WHERE correlation_id=? ORDER BY occurred_at,audit_id""",
                [correlation_id],
            ).fetchall()
            return tuple(self._audit(row) for row in rows)
        finally:
            connection.close()

    @staticmethod
    def _audit(row: tuple[Any, ...]) -> AuditRecord:
        occurred = row[3]
        assert isinstance(occurred, datetime)
        metadata = json.loads(str(row[13]))
        return AuditRecord(
            str(row[0]),
            str(row[1]),
            str(row[2]),
            occurred,
            str(row[4]),
            None if row[5] is None else str(row[5]),
            str(row[6]),
            str(row[7]),
            None if row[8] is None else str(row[8]),
            None if row[9] is None else str(row[9]),
            None if row[10] is None else int(row[10]),
            None if row[11] is None else str(row[11]),
            str(row[12]),
            metadata,
            str(row[14]),
        )

    def backlog_counts(self) -> dict[str, int]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            rows = connection.execute(
                "SELECT dispatch_status,count(*) FROM platform_event_outbox GROUP BY dispatch_status"
            ).fetchall()
            return {str(status): int(count) for status, count in rows}
        finally:
            connection.close()
