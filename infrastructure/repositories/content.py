"""DuckDB adapters for the content-management ports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.content.models import ContentDocument, ValidationStatus
from domain.content.validation import Severity, ValidationReport
from infrastructure.database.v2 import connect_v2


def _dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


class ContentRepositoryBase:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def _one(self, sql: str, parameters: list[Any]) -> int:
        connection = connect_v2(self.database_path)
        try:
            row = connection.execute(sql, parameters).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return a content identifier")
            return int(row[0])
        finally:
            connection.close()


class ProgramRepository(ContentRepositoryBase):
    def upsert(self, payload: dict[str, Any]) -> int:
        return self._one(
            """
            INSERT INTO programs(code,version,label,country_code,default_language_code)
            VALUES (?,?,?,?,?) ON CONFLICT(code,version,country_code) DO UPDATE SET label=excluded.label
            RETURNING id
        """,
            [
                payload["code"],
                str(payload.get("version", "1")),
                payload["label"],
                payload["country_code"],
                payload.get("language_code", "fr-FR"),
            ],
        )

    def get(self, code: str) -> dict[str, Any] | None:
        return _get(self.database_path, "SELECT * FROM programs WHERE code=? ORDER BY created_at DESC LIMIT 1", code)


class SubjectRepository(ContentRepositoryBase):
    def upsert(self, payload: dict[str, Any]) -> int:
        return self._one(
            "INSERT INTO subjects(code,default_label) VALUES (?,?) ON CONFLICT(code) DO UPDATE SET default_label=excluded.default_label RETURNING id",
            [payload["code"], payload["label"]],
        )

    def get(self, code: str) -> dict[str, Any] | None:
        return _get(self.database_path, "SELECT * FROM subjects WHERE code=?", code)


class SkillRepository(ContentRepositoryBase):
    def upsert(self, payload: dict[str, Any]) -> int:
        return self._one(
            """
            INSERT INTO skills(domain_id,code,default_label,description,display_order)
            VALUES (?,?,?,?,?) ON CONFLICT(domain_id,code) DO UPDATE SET default_label=excluded.default_label,description=excluded.description
            RETURNING id
        """,
            [
                payload["domain_id"],
                payload["code"],
                payload["label"],
                payload.get("description", ""),
                payload.get("display_order", 1),
            ],
        )

    def get(self, code: str) -> dict[str, Any] | None:
        return _get(self.database_path, "SELECT * FROM skills WHERE code=? ORDER BY id LIMIT 1", code)


class ExerciseRepository(ContentRepositoryBase):
    def upsert(self, payload: dict[str, Any]) -> int:
        return self._one(
            """
            INSERT INTO exercises(subject_id,code,title,objective,estimated_seconds,difficulty,instructions,evaluation_strategy,language_code,content_version,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code,language_code,content_version) DO UPDATE SET title=excluded.title,objective=excluded.objective
            RETURNING id
        """,
            [
                payload["subject_id"],
                payload["code"],
                payload["title"],
                payload.get("objective", ""),
                payload.get("estimated_seconds", 300),
                payload.get("difficulty", 3),
                payload.get("instructions", ""),
                json.dumps(payload.get("evaluation_strategy", {"kind": "weighted_sum"})),
                payload.get("language_code", "fr-FR"),
                payload.get("content_version", 1),
                payload.get("status", "draft"),
            ],
        )

    def get(self, code: str) -> dict[str, Any] | None:
        return _get(
            self.database_path, "SELECT * FROM exercises WHERE code=? ORDER BY content_version DESC LIMIT 1", code
        )


class QuestionRepository(ContentRepositoryBase):
    def upsert(self, payload: dict[str, Any]) -> int:
        return self._one(
            """
            INSERT INTO questions(code,statement,answer_type,expected_answer,explanation,hints,estimated_seconds,language_code,content_version,status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code,language_code,content_version) DO UPDATE SET statement=excluded.statement,expected_answer=excluded.expected_answer,explanation=excluded.explanation,hints=excluded.hints
            RETURNING id
        """,
            [
                payload["code"],
                payload["statement"],
                payload.get("answer_type", "text"),
                json.dumps(payload.get("expected_answer")),
                payload.get("explanation", ""),
                json.dumps(payload.get("hints", [])),
                payload.get("estimated_seconds", 60),
                payload.get("language_code", "fr-FR"),
                payload.get("content_version", 1),
                payload.get("status", "draft"),
            ],
        )

    def get(self, code: str) -> dict[str, Any] | None:
        return _get(
            self.database_path, "SELECT * FROM questions WHERE code=? ORDER BY content_version DESC LIMIT 1", code
        )


class MediaRepository(ContentRepositoryBase):
    def upsert(self, payload: dict[str, Any]) -> int:
        return self._one(
            """
            INSERT INTO media_assets(code,media_type,uri,title,mime_type,metadata) VALUES (?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET uri=excluded.uri,title=excluded.title,mime_type=excluded.mime_type,metadata=excluded.metadata
            RETURNING id
        """,
            [
                payload["code"],
                payload["kind"],
                payload["uri"],
                payload.get("title", ""),
                payload.get("mime_type"),
                json.dumps(payload.get("metadata", {})),
            ],
        )

    def get(self, code: str) -> dict[str, Any] | None:
        return _get(self.database_path, "SELECT * FROM media_assets WHERE code=?", code)


class VersionRepository(ContentRepositoryBase):
    def create(
        self, entity_type: str, entity_id: int, payload: dict[str, Any], author: str, status: ValidationStatus
    ) -> int:
        connection = connect_v2(self.database_path)
        try:
            number = int(
                connection.execute(
                    "SELECT coalesce(max(version_number),0)+1 FROM content_versions WHERE entity_type=? AND entity_id=?",
                    [entity_type, entity_id],
                ).fetchone()[0]
            )
            row = connection.execute(
                "INSERT INTO content_versions(entity_type,entity_id,version_number,payload,author,status) VALUES (?,?,?,?,?,?) RETURNING id",
                [entity_type, entity_id, number, json.dumps(payload), author, status.value],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return a version identifier")
            version_id = int(row[0])
            connection.execute(
                "INSERT INTO content_status_events(content_version_id,previous_status,new_status,author) VALUES (?,NULL,?,?)",
                [version_id, status.value, author],
            )
            return version_id
        finally:
            connection.close()

    def history(self, entity_type: str, entity_id: int) -> list[dict[str, Any]]:
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return _dicts(
                connection.execute(
                    """
                    SELECT cv.* EXCLUDE(status), coalesce((
                        SELECT new_status FROM content_status_events cse
                        WHERE cse.content_version_id=cv.id ORDER BY changed_at DESC,id DESC LIMIT 1
                    ), cv.status) AS status
                    FROM content_versions cv WHERE entity_type=? AND entity_id=? ORDER BY version_number
                    """,
                    [entity_type, entity_id],
                )
            )
        finally:
            connection.close()

    def transition(self, version_id: int, status: ValidationStatus, author: str) -> None:
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                """
                SELECT coalesce((SELECT new_status FROM content_status_events
                    WHERE content_version_id=cv.id ORDER BY changed_at DESC,id DESC LIMIT 1),cv.status)
                FROM content_versions cv WHERE id=?
                """,
                [version_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown content version: {version_id}")
            connection.execute(
                "INSERT INTO content_status_events(content_version_id,previous_status,new_status,author) VALUES (?,?,?,?)",
                [version_id, row[0], status.value, author],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()


class ValidationRepository(ContentRepositoryBase):
    def save(self, source_name: str, report: ValidationReport) -> int:
        connection = connect_v2(self.database_path)
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                "INSERT INTO validation_runs(source_name,is_valid,error_count,warning_count) VALUES (?,?,?,?) RETURNING id",
                [source_name, report.valid, report.count(Severity.ERROR), report.count(Severity.WARNING)],
            ).fetchone()
            if row is None:
                raise RuntimeError("DuckDB did not return a validation identifier")
            run_id = int(row[0])
            for issue in report.issues:
                connection.execute(
                    "INSERT INTO validation_issues(validation_run_id,code,severity,message,entity_type,entity_code) VALUES (?,?,?,?,?,?)",
                    [run_id, issue.code, issue.severity.value, issue.message, issue.entity_type, issue.entity_code],
                )
            connection.execute("COMMIT")
            return run_id
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()


class ContentSearchRepository(ContentRepositoryBase):
    def search(
        self,
        *,
        subject: str | None = None,
        skill: str | None = None,
        level: str | None = None,
        keyword: str | None = None,
        tags: tuple[str, ...] = (),
        difficulty: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        filters = ((subject, "s.code=?"), (skill, "sk.code=?"), (level, "sl.code=?"), (difficulty, "e.difficulty=?"))
        for value, clause in filters:
            if value is not None:
                clauses.append(clause)
                params.append(value)
        if keyword:
            clauses.append("(lower(e.title) LIKE ? OR lower(q.statement) LIKE ?)")
            params.extend([f"%{keyword.lower()}%"] * 2)
        for tag in tags:
            clauses.append(
                "EXISTS (SELECT 1 FROM content_tags ct JOIN tags t ON t.id=ct.tag_id WHERE ct.entity_type='exercise' AND ct.entity_id=e.id AND t.code=?)"
            )
            params.append(tag)
        sql = (
            """SELECT DISTINCT e.id,e.code,e.title,e.difficulty,s.code AS subject_code
                 FROM exercises e JOIN subjects s ON s.id=e.subject_id
                 LEFT JOIN exercise_questions eq ON eq.exercise_id=e.id LEFT JOIN questions q ON q.id=eq.question_id
                 LEFT JOIN question_skills qs ON qs.question_id=q.id LEFT JOIN skills sk ON sk.id=qs.skill_id
                 LEFT JOIN program_subjects ps ON ps.subject_id=s.id LEFT JOIN school_levels sl ON sl.id=ps.school_level_id
                 WHERE """
            + " AND ".join(clauses)
            + " ORDER BY e.code"
        )
        connection = connect_v2(self.database_path, read_only=True)
        try:
            return _dicts(connection.execute(sql, params))
        finally:
            connection.close()


def _get(path: Path | None, sql: str, code: str) -> dict[str, Any] | None:
    connection = connect_v2(path, read_only=True)
    try:
        cursor = connection.execute(sql, [code])
        rows = _dicts(cursor)
        return rows[0] if rows else None
    finally:
        connection.close()


class ContentUnitOfWork(ContentRepositoryBase):
    """Transactional normalized import; never activates imported content."""

    def persist(self, document: ContentDocument, author: str) -> dict[str, int]:
        connection = connect_v2(self.database_path)
        counts = {"subjects": 0, "domains": 0, "skills": 0, "exercises": 0, "questions": 0}
        try:
            connection.execute("BEGIN")
            subject_ids: dict[str, int] = {}
            for subject_item in document.subjects:
                row = connection.execute(
                    "INSERT INTO subjects(code,default_label) VALUES (?,?) ON CONFLICT(code) DO UPDATE SET default_label=excluded.default_label RETURNING id",
                    [subject_item.code, subject_item.label],
                ).fetchone()
                subject_ids[subject_item.code] = int(row[0])
                counts["subjects"] += 1
            domain_ids: dict[str, int] = {}
            for domain_item in document.domains:
                row = connection.execute(
                    "INSERT INTO domains(subject_id,code,default_label,display_order) VALUES (?,?,?,?) ON CONFLICT(subject_id,code) DO UPDATE SET default_label=excluded.default_label RETURNING id",
                    [subject_ids[domain_item.subject_code], domain_item.code, domain_item.label, len(domain_ids) + 1],
                ).fetchone()
                domain_ids[domain_item.code] = int(row[0])
                counts["domains"] += 1
            skill_ids: dict[str, int] = {}
            for skill_item in document.skills:
                row = connection.execute(
                    "INSERT INTO skills(domain_id,code,default_label,description,display_order) VALUES (?,?,?,?,?) ON CONFLICT(domain_id,code) DO UPDATE SET default_label=excluded.default_label RETURNING id",
                    [domain_ids[skill_item.domain_code], skill_item.code, skill_item.label, "", len(skill_ids) + 1],
                ).fetchone()
                skill_ids[skill_item.code] = int(row[0])
                counts["skills"] += 1
            for exercise in document.exercises:
                version = exercise.version.number if exercise.version else 1
                row = connection.execute(
                    "INSERT INTO exercises(subject_id,code,title,objective,estimated_seconds,difficulty,instructions,evaluation_strategy,language_code,content_version,status) VALUES (?,?,?,?,300,?,'','{\"kind\":\"weighted_sum\"}','fr-FR',?,'draft') ON CONFLICT(code,language_code,content_version) DO UPDATE SET title=excluded.title RETURNING id",
                    [
                        subject_ids[exercise.subject_code],
                        exercise.code,
                        exercise.title,
                        exercise.objective,
                        exercise.difficulty.value,
                        version,
                    ],
                ).fetchone()
                exercise_id = int(row[0])
                counts["exercises"] += 1
                self._persist_labels(connection, "exercise", exercise_id, exercise.tags, exercise.media)
                for position, question in enumerate(exercise.questions, 1):
                    qversion = question.version.number if question.version else 1
                    row = connection.execute(
                        "INSERT INTO questions(code,statement,answer_type,expected_answer,explanation,hints,estimated_seconds,language_code,content_version,status) VALUES (?,?,?,?,?,?,60,'fr-FR',?,'draft') ON CONFLICT(code,language_code,content_version) DO UPDATE SET statement=excluded.statement RETURNING id",
                        [
                            question.code,
                            question.statement,
                            question.answer.kind,
                            json.dumps(question.answer.value),
                            question.explanation.text,
                            json.dumps([h.text for h in question.hints]),
                            qversion,
                        ],
                    ).fetchone()
                    question_id = int(row[0])
                    counts["questions"] += 1
                    self._persist_labels(connection, "question", question_id, question.tags, question.media)
                    connection.execute(
                        "INSERT INTO exercise_questions VALUES (?,?,?,1,TRUE) ON CONFLICT DO NOTHING",
                        [exercise_id, question_id, position],
                    )
                    for mapping in question.mappings:
                        connection.execute(
                            "INSERT INTO question_skills VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                            [question_id, skill_ids[mapping.skill_code], mapping.weight, mapping.primary],
                        )
                    payload = json.dumps({"code": question.code, "statement": question.statement})
                    connection.execute(
                        "INSERT INTO content_versions(entity_type,entity_id,version_number,payload,author,status) VALUES ('question',?,?,?,?, 'draft') ON CONFLICT DO NOTHING",
                        [question_id, qversion, payload, author],
                    )
                payload = json.dumps({"code": exercise.code, "title": exercise.title})
                connection.execute(
                    "INSERT INTO content_versions(entity_type,entity_id,version_number,payload,author,status) VALUES ('exercise',?,?,?,?, 'draft') ON CONFLICT DO NOTHING",
                    [exercise_id, version, payload, author],
                )
            connection.execute("COMMIT")
            return counts
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    @staticmethod
    def _persist_labels(connection: Any, entity_type: str, entity_id: int, tags: Any, media: Any) -> None:
        for tag in tags:
            row = connection.execute(
                "INSERT INTO tags(code,label) VALUES (?,?) ON CONFLICT(code) DO UPDATE SET label=excluded.label RETURNING id",
                [tag.code, tag.label],
            ).fetchone()
            connection.execute(
                "INSERT INTO content_tags(entity_type,entity_id,tag_id) VALUES (?,?,?) ON CONFLICT DO NOTHING",
                [entity_type, entity_id, int(row[0])],
            )
        for position, asset in enumerate(media, 1):
            row = connection.execute(
                """
                INSERT INTO media_assets(code,media_type,uri,title,mime_type) VALUES (?,?,?,?,?)
                ON CONFLICT(code) DO UPDATE SET uri=excluded.uri,title=excluded.title,mime_type=excluded.mime_type
                RETURNING id
                """,
                [asset.code, asset.kind, asset.uri, asset.title, asset.mime_type],
            ).fetchone()
            connection.execute(
                "INSERT INTO content_media(entity_type,entity_id,media_id,position) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                [entity_type, entity_id, int(row[0]), position],
            )
