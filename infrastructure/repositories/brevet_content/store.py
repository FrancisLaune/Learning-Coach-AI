"""DuckDB access for brevet content referential."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from core.config import get_database_path


class BrevetContentStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or get_database_path())
        self._con: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            self._con = duckdb.connect(str(self.db_path))
        return self._con

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def __enter__(self) -> BrevetContentStore:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetchone(self, sql: str, params: list[Any] | None = None) -> tuple[Any, ...] | None:
        row = self.connect().execute(sql, params or []).fetchone()
        return tuple(row) if row is not None else None

    def fetchall(self, sql: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.connect().execute(sql, params or []).fetchall()]

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self.connect().execute(sql, params or [])

    def subject_id(self, code: str) -> int | None:
        row = self.fetchone("SELECT subject_id FROM subjects WHERE code = ?", [code])
        return int(row[0]) if row else None

    def insert_content(
        self,
        *,
        content_type: str,
        source_type: str,
        subject_id: int,
        chapter_id: int | None,
        title: str,
        statement: str,
        answer_type: str,
        expected_answer: str | None,
        accepted_answers_json: str | None,
        correction: str | None,
        hint: str | None,
        difficulty_score: float | None,
        difficulty_label: str | None,
        estimated_seconds: int | None,
        brevet_format: str | None,
        curriculum_2027_compatible: str,
        runtime_playable: bool,
        validation_status: str,
        quality_score: float | None,
        fingerprint: str,
        semantic_fingerprint: str | None,
        usage_policy: str,
        skill_id: int | None,
    ) -> tuple[int, bool]:
        con = self.connect()
        existing = con.execute(
            "SELECT content_id FROM content_items WHERE fingerprint = ?",
            [fingerprint],
        ).fetchone()
        created_new = False
        if existing:
            content_id = int(existing[0])
        else:
            created_new = True
            con.execute(
                """
                INSERT INTO content_items(
                    content_type, source_type, subject_id, chapter_id, title, statement,
                    answer_type, expected_answer, accepted_answers_json, correction, hint,
                    difficulty_score, difficulty_label, estimated_seconds, brevet_format,
                    curriculum_2027_compatible, runtime_playable, validation_status,
                    quality_score, fingerprint, semantic_fingerprint, usage_policy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    content_type,
                    source_type,
                    subject_id,
                    chapter_id,
                    title,
                    statement,
                    answer_type,
                    expected_answer,
                    accepted_answers_json,
                    correction,
                    hint,
                    difficulty_score,
                    difficulty_label,
                    estimated_seconds,
                    brevet_format,
                    curriculum_2027_compatible,
                    runtime_playable,
                    validation_status,
                    quality_score,
                    fingerprint,
                    semantic_fingerprint,
                    usage_policy,
                ],
            )
            content_id = int(
                con.execute(
                    "SELECT content_id FROM content_items WHERE fingerprint = ?",
                    [fingerprint],
                ).fetchone()[0]
            )
        if skill_id is not None:
            link = con.execute(
                """
                SELECT 1 FROM content_skill_links
                WHERE content_id = ? AND skill_id = ? AND relation_type = 'PRIMARY'
                """,
                [content_id, skill_id],
            ).fetchone()
            if link is None:
                con.execute(
                    """
                    INSERT INTO content_skill_links(content_id, skill_id, relation_type, weight)
                    VALUES (?, ?, 'PRIMARY', 1.0)
                    """,
                    [content_id, skill_id],
                )
        return content_id, created_new
