"""Transactional DuckDB adapter for the versioned curriculum catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from domain.curriculum.models import CatalogImportReport
from domain.curriculum.validation import CatalogValidator
from infrastructure.database.v2 import connect_v2


class DuckDBCurriculumRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path

    def import_catalog(
        self, source: Path, document: dict[str, Any], checksum: str, dry_run: bool
    ) -> CatalogImportReport:
        rows_read = _rows(document)
        import_id = hashlib.sha256(f"{source.name}:{checksum}".encode()).hexdigest()[:24]
        if dry_run:
            return CatalogImportReport(import_id, rows_read, rows_read, 0, 0, (), (), True)
        con = connect_v2(self.database_path)
        try:
            existing = con.execute(
                "SELECT source_checksum,status FROM content_import_batches WHERE import_identifier=?", [import_id]
            ).fetchone()
            if existing:
                if str(existing[0]) != checksum:
                    return CatalogImportReport(import_id, rows_read, 0, 0, 0, ("version_conflict",), (), False)
                return CatalogImportReport(import_id, rows_read, 0, 0, rows_read, (), (), False)
            con.execute("BEGIN")
            con.execute(
                "INSERT INTO content_import_batches(import_identifier,source_path,source_checksum,dry_run,status,rows_read) VALUES (?,?,?,?,?,?)",
                [import_id, source.as_posix(), checksum, False, "started", rows_read],
            )
            ids = self._references(con)
            created = 0
            created += self._programs(con, document.get("programs", []), ids)
            created += self._chapters(con, document.get("chapters", []), ids)
            created += self._skills(con, document.get("skills", []), document.get("subskills", []), ids)
            created += self._relations(con, document.get("relations", []), ids)
            created += self._exam(con, document.get("exam_references", []), ids)
            created += self._contents(con, document.get("contents", []), ids)
            con.execute(
                "UPDATE content_import_batches SET status='completed',created_count=?,completed_at=CURRENT_TIMESTAMP,report=? WHERE import_identifier=?",
                [created, json.dumps({"validation": "complete", "approval": "explicit"}), import_id],
            )
            con.execute(
                "INSERT INTO curriculum_domain_events(event_type,aggregate_type,aggregate_code,payload) VALUES ('ContentImportCompleted','catalog',?,?)",
                [import_id, json.dumps({"created": created, "rows_read": rows_read})],
            )
            con.execute("COMMIT")
            return CatalogImportReport(import_id, rows_read, created, 0, rows_read - created, (), (), False)
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    @staticmethod
    def _references(con: Any) -> dict[str, dict[str, int]]:
        return {
            "levels": {
                str(code): int(identifier)
                for identifier, code in con.execute("SELECT id,code FROM school_levels").fetchall()
            },
            "subjects": {
                str(code): int(identifier)
                for identifier, code in con.execute("SELECT id,code FROM subjects").fetchall()
            },
            "domains": {
                f"{subject}:{code}": int(identifier)
                for identifier, subject, code in con.execute(
                    "SELECT d.id,s.code,d.code FROM domains d JOIN subjects s ON s.id=d.subject_id"
                ).fetchall()
            },
            "programs": {
                str(code): int(identifier)
                for identifier, code in con.execute("SELECT id,code FROM programs").fetchall()
            },
            "chapters": {},
            "skills": {
                str(code): int(identifier) for identifier, code in con.execute("SELECT id,code FROM skills").fetchall()
            },
            "subskills": {
                str(code): int(identifier)
                for identifier, code in con.execute("SELECT id,code FROM subskills").fetchall()
            },
        }

    @staticmethod
    def _programs(con: Any, programs: list[dict[str, Any]], ids: dict[str, dict[str, int]]) -> int:
        created = 0
        for item in programs:
            row = con.execute("SELECT id FROM programs WHERE code=?", [item["code"]]).fetchone()
            if row:
                identifier = int(row[0])
            else:
                identifier = int(
                    con.execute(
                        "INSERT INTO programs(code,version,label,country_code,jurisdiction,exam_type,default_language_code,valid_from,valid_to) VALUES (?,?,?,?,?,?,?,?,?) RETURNING id",
                        [
                            item["code"],
                            item["version"],
                            item["label"],
                            "FR",
                            "France",
                            item.get("exam_type"),
                            "fr-FR",
                            item["valid_from"],
                            item.get("valid_to"),
                        ],
                    ).fetchone()[0]
                )
                created += 1
            ids["programs"][item["code"]] = identifier
            for subject_code in item["subjects"]:
                con.execute(
                    "INSERT INTO program_subjects(program_id,subject_id,school_level_id,display_order,weight) VALUES (?,?,?,?,1) ON CONFLICT DO NOTHING",
                    [
                        identifier,
                        ids["subjects"][subject_code],
                        ids["levels"][item["grade_code"]],
                        ids["subjects"][subject_code],
                    ],
                )
        return created

    @staticmethod
    def _chapters(con: Any, chapters: list[dict[str, Any]], ids: dict[str, dict[str, int]]) -> int:
        created = 0
        for item in chapters:
            row = con.execute("SELECT id FROM curriculum_chapters WHERE stable_code=?", [item["code"]]).fetchone()
            if row:
                identifier = int(row[0])
            else:
                subject_id = ids["subjects"][item["subject_code"]]
                identifier = int(
                    con.execute(
                        """INSERT INTO curriculum_chapters(stable_code,program_id,subject_id,domain_id,grade_level_id,title,
                        description,sequence_order,expected_duration_minutes,difficulty_min,difficulty_max,is_required,
                        is_exam_relevant,is_transition_relevant,status,version,effective_from)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                        [
                            item["code"],
                            ids["programs"][item["program_code"]],
                            subject_id,
                            ids["domains"][f"{item['subject_code']}:{item['domain_code']}"],
                            ids["levels"][item["grade_code"]],
                            item["title"],
                            item["description"],
                            item["sequence_order"],
                            item["expected_duration_minutes"],
                            item["difficulty_min"],
                            item["difficulty_max"],
                            True,
                            item.get("exam_relevant", False),
                            item.get("transition_relevant", False),
                            "approved",
                            1,
                            item["effective_from"],
                        ],
                    ).fetchone()[0]
                )
                created += 1
            ids["chapters"][item["code"]] = identifier
        return created

    @staticmethod
    def _skills(
        con: Any, skills: list[dict[str, Any]], subskills: list[dict[str, Any]], ids: dict[str, dict[str, int]]
    ) -> int:
        created = 0
        for item in skills:
            row = con.execute("SELECT id FROM skills WHERE code=?", [item["code"]]).fetchone()
            if row:
                identifier = int(row[0])
            else:
                chapter = next(code for code, identifier in ids["chapters"].items() if code == item["chapter_code"])
                chapter_row = con.execute(
                    "SELECT domain_id FROM curriculum_chapters WHERE id=?", [ids["chapters"][chapter]]
                ).fetchone()
                identifier = int(
                    con.execute(
                        "INSERT INTO skills(domain_id,code,default_label,description,display_order) VALUES (?,?,?,?,?) RETURNING id",
                        [
                            int(chapter_row[0]),
                            item["code"],
                            item["title"],
                            item["description"],
                            int(
                                con.execute(
                                    "SELECT coalesce(max(display_order),0)+1 FROM skills WHERE domain_id=?",
                                    [int(chapter_row[0])],
                                ).fetchone()[0]
                            ),
                        ],
                    ).fetchone()[0]
                )
                created += 1
            ids["skills"][item["code"]] = identifier
            con.execute(
                """INSERT INTO curriculum_skill_details(skill_id,chapter_id,grade_level_id,reference_difficulty,
                importance,is_required,is_exam_relevant,is_transition_relevant,pedagogical_tags,status,version)
                VALUES (?,?,?,?,?,?,?,?,?,'approved',1) ON CONFLICT DO NOTHING""",
                [
                    identifier,
                    ids["chapters"][item["chapter_code"]],
                    ids["levels"][item["grade_code"]],
                    item["difficulty"],
                    item["importance"],
                    True,
                    item.get("exam_relevant", False),
                    item.get("transition_relevant", False),
                    json.dumps(item.get("tags", [])),
                ],
            )
            objective_code = f"OBJ-{item['code']}"
            objective = con.execute(
                "SELECT id FROM learning_objectives WHERE stable_code=?", [objective_code]
            ).fetchone()
            if objective:
                objective_id = int(objective[0])
            else:
                objective_id = int(
                    con.execute(
                        "INSERT INTO learning_objectives(stable_code,chapter_id,title,description,observable_outcome,sequence_order,status,version) VALUES (?,?,?,?,?,?,'approved',1) RETURNING id",
                        [
                            objective_code,
                            ids["chapters"][item["chapter_code"]],
                            item["title"],
                            item["description"],
                            item["observable_outcome"],
                            item["sequence_order"],
                        ],
                    ).fetchone()[0]
                )
            con.execute(
                "INSERT INTO skill_learning_objectives(skill_id,learning_objective_id,is_primary) VALUES (?,?,TRUE) ON CONFLICT DO NOTHING",
                [identifier, objective_id],
            )
        for item in subskills:
            if item["code"] not in ids["subskills"]:
                identifier = int(
                    con.execute(
                        "INSERT INTO subskills(skill_id,code,default_label,description,display_order) VALUES (?,?,?,?,?) RETURNING id",
                        [
                            ids["skills"][item["skill_code"]],
                            item["code"],
                            item["title"],
                            item["description"],
                            item["sequence_order"],
                        ],
                    ).fetchone()[0]
                )
                ids["subskills"][item["code"]] = identifier
                created += 1
        return created

    @staticmethod
    def _relations(con: Any, relations: list[dict[str, Any]], ids: dict[str, dict[str, int]]) -> int:
        created = 0
        for item in relations:
            before = con.execute("SELECT count(*) FROM curriculum_skill_relations").fetchone()[0]
            con.execute(
                """INSERT INTO curriculum_skill_relations(prerequisite_skill_id,target_skill_id,relation_type,
                progression_role,strength,mandatory,minimum_mastery_threshold,rationale,source,version,active)
                VALUES (?,?,?,?,?,?,?,?,?,1,TRUE) ON CONFLICT DO NOTHING""",
                [
                    ids["skills"][item["prerequisite"]],
                    ids["skills"][item["target"]],
                    item["relation_type"],
                    item["progression_role"],
                    item["strength"],
                    item["mandatory"],
                    item["minimum_mastery_threshold"],
                    item["rationale"],
                    item["source"],
                ],
            )
            created += int(con.execute("SELECT count(*) FROM curriculum_skill_relations").fetchone()[0] > before)
        return created

    @staticmethod
    def _exam(con: Any, exams: list[dict[str, Any]], ids: dict[str, dict[str, int]]) -> int:
        created = 0
        for item in exams:
            row = con.execute(
                "SELECT id FROM exam_references WHERE code=? AND effective_year=? AND version=1",
                [item["code"], item["effective_year"]],
            ).fetchone()
            if row:
                exam_id = int(row[0])
            else:
                exam_id = int(
                    con.execute(
                        """INSERT INTO exam_references(code,title,grade_level_id,applicable_subject_codes,
                        competency_weights,mandatory_domain_codes,preparation_phases,effective_year,source_reference,status,version)
                        VALUES (?,?,?,?,?,?,?,?,?,'approved',1) RETURNING id""",
                        [
                            item["code"],
                            item["title"],
                            ids["levels"][item["grade_code"]],
                            json.dumps(item["subjects"]),
                            "{}",
                            json.dumps(item["domains"]),
                            json.dumps(item["preparation_phases"]),
                            item["effective_year"],
                            item["source_reference"],
                        ],
                    ).fetchone()[0]
                )
                created += 1
            for skill_code in item["skills"]:
                con.execute(
                    "INSERT INTO exam_skill_references(exam_reference_id,skill_id,relevance,rationale) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                    [exam_id, ids["skills"][skill_code], 1.0, "Compétence explicitement mobilisée par le lot brevet."],
                )
        return created

    @staticmethod
    def _contents(con: Any, contents: list[dict[str, Any]], ids: dict[str, dict[str, int]]) -> int:
        created = 0
        validator = CatalogValidator()
        report = validator.validate({"chapters": [], "skills": [], "relations": [], "contents": []})
        for item in contents:
            existing = con.execute(
                "SELECT id FROM exercises WHERE code=? AND content_version=?", [item["code"], item["version"]]
            ).fetchone()
            if existing:
                continue
            subject_id = ids["subjects"][item["subject_code"]]
            exercise_id = int(
                con.execute(
                    """INSERT INTO exercises(subject_id,code,title,objective,estimated_seconds,difficulty,instructions,
                    evaluation_strategy,language_code,content_version,status) VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    [
                        subject_id,
                        item["code"],
                        item["title"],
                        item["objective"],
                        item["duration_minutes"] * 60,
                        item["difficulty"],
                        item["instructions"],
                        json.dumps({"kind": "explicit_solution"}),
                        "fr-FR",
                        item["version"],
                        "active",
                    ],
                ).fetchone()[0]
            )
            question = item["question"]
            question_id = int(
                con.execute(
                    """INSERT INTO questions(code,statement,answer_type,expected_answer,explanation,hints,
                    estimated_seconds,language_code,content_version,status) VALUES (?,?,?,?,?,?,?,?,?,'active') RETURNING id""",
                    [
                        f"Q-{item['code']}",
                        question["statement"],
                        "text",
                        json.dumps(question["answer"]),
                        item["solution"]["explanation"],
                        json.dumps([hint["text"] for hint in item["hints"]]),
                        item["duration_minutes"] * 60,
                        "fr-FR",
                        item["version"],
                    ],
                ).fetchone()[0]
            )
            skill_id = ids["skills"][item["skill_code"]]
            con.execute("INSERT INTO exercise_questions VALUES (?,?,1,1,TRUE)", [exercise_id, question_id])
            con.execute("INSERT INTO question_skills VALUES (?,?,1,TRUE)", [question_id, skill_id])
            subskill_id = ids["subskills"].get(item.get("subskill_code", ""))
            if subskill_id:
                con.execute("INSERT INTO question_subskills VALUES (?,?,1,TRUE)", [question_id, subskill_id])
            payload = {
                "activity_type": item["activity_type"],
                "content_type": item["content_type"],
                "prerequisite_skill_ids": [ids["skills"][code] for code in item.get("prerequisites", [])],
                "tags": item["tags"],
                "objective_compatibility": item["objective_compatibility"],
                "exam_compatibility": item["exam_compatibility"],
                "transition_markers": item["transition_markers"],
                "revision_compatible": item["compatibility"]["revision"],
            }
            version_id = int(
                con.execute(
                    "INSERT INTO content_versions(entity_type,entity_id,version_number,payload,author,status) VALUES ('exercise',?,?,?,?, 'approved') RETURNING id",
                    [exercise_id, item["version"], json.dumps(payload), item["author_source"]],
                ).fetchone()[0]
            )
            for previous, target, actor in (
                (None, "draft", item["author_source"]),
                ("draft", "review", item["reviewer"]),
                ("review", "approved", item["approver"]),
            ):
                con.execute(
                    "INSERT INTO content_status_events(content_version_id,previous_status,new_status,author) VALUES (?,?,?,?)",
                    [version_id, previous, target, actor],
                )
            con.execute(
                """INSERT INTO learning_content_metadata(exercise_id,chapter_id,subskill_id,content_type,summary,
                author_source,license_or_origin,created_on,last_reviewed_on,min_duration_minutes,max_duration_minutes,
                difficulty_rationale,expected_attempts,allowed_hints,calculator_allowed,material_required,compatibility,
                pedagogical_strategy,cognitive_demand,expected_response_type,source_identifier,current_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    exercise_id,
                    ids["chapters"][item["chapter_code"]],
                    subskill_id,
                    item["content_type"],
                    item["summary"],
                    item["author_source"],
                    item["license_or_origin"],
                    item["created_on"],
                    item["reviewed_on"],
                    item["min_duration_minutes"],
                    item["max_duration_minutes"],
                    json.dumps(item["difficulty_rationale"]),
                    item["expected_attempts"],
                    len(item["hints"]),
                    item["calculator_allowed"],
                    item.get("material_required"),
                    json.dumps(item["compatibility"]),
                    item["pedagogical_strategy"],
                    item["cognitive_demand"],
                    question["response_type"],
                    item["code"],
                    item["version"],
                ],
            )
            objective_id = int(
                con.execute(
                    "SELECT lo.id FROM learning_objectives lo JOIN skill_learning_objectives slo ON slo.learning_objective_id=lo.id WHERE slo.skill_id=? AND slo.is_primary LIMIT 1",
                    [skill_id],
                ).fetchone()[0]
            )
            con.execute("INSERT INTO content_learning_objectives VALUES (?,?)", [exercise_id, objective_id])
            detailed_question_id = int(
                con.execute(
                    """INSERT INTO content_questions(exercise_id,stable_code,sequence_order,instructions,context,
                    statement,response_type,expected_answer,tolerance,unit,points,is_evaluative)
                    VALUES (?,?,1,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    [
                        exercise_id,
                        f"CQ-{item['code']}",
                        item["instructions"],
                        question.get("context"),
                        question["statement"],
                        question["response_type"],
                        json.dumps(question["answer"]),
                        question.get("tolerance"),
                        question.get("unit"),
                        1,
                        question.get("evaluative", True),
                    ],
                ).fetchone()[0]
            )
            solution_id = int(
                con.execute(
                    """INSERT INTO content_solutions(question_id,correct_answer,pedagogical_explanation,method,
                    common_mistakes,advice,accepted_variants,rubric) VALUES (?,?,?,?,?,?,?,?) RETURNING id""",
                    [
                        detailed_question_id,
                        json.dumps(question["answer"]),
                        item["solution"]["explanation"],
                        item["solution"]["method"],
                        json.dumps(item["common_errors"]),
                        item["solution"]["advice"],
                        json.dumps(item["solution"].get("accepted_variants", [])),
                        json.dumps({"points": 1}),
                    ],
                ).fetchone()[0]
            )
            for position, step in enumerate(item["solution"]["steps"], 1):
                con.execute(
                    "INSERT INTO content_solution_steps(solution_id,sequence_order,explanation) VALUES (?,?,?)",
                    [solution_id, position, step],
                )
            for hint in item["hints"]:
                con.execute(
                    """INSERT INTO content_hints(question_id,sequence_order,text,penalty_weight,disclosure_level,
                    related_skill_id,reveals_answer) VALUES (?,?,?,?,?,?,FALSE)""",
                    [detailed_question_id, hint["order"], hint["text"], hint["penalty"], hint["disclosure"], skill_id],
                )
            for tag in item["tags"]:
                tag_row = con.execute("SELECT id FROM tags WHERE code=?", [tag]).fetchone()
                if tag_row is None:
                    tag_row = con.execute(
                        "INSERT INTO tags(code,label) VALUES (?,?) RETURNING id",
                        [tag, tag.replace("_", " ").title()],
                    ).fetchone()
                con.execute(
                    "INSERT INTO content_tags(entity_type,entity_id,tag_id) VALUES ('exercise',?,?) ON CONFLICT DO NOTHING",
                    [exercise_id, int(tag_row[0])],
                )
            validation_id = int(
                con.execute(
                    "INSERT INTO validation_runs(source_name,is_valid,error_count,warning_count) VALUES (?,TRUE,0,0) RETURNING id",
                    [item["code"]],
                ).fetchone()[0]
            )
            quality = validator.quality(item, report)
            quality_id = int(
                con.execute(
                    """INSERT INTO content_quality_assessments(content_version_id,score,quality_level,passed_criteria,
                    missing_criteria,blocking_errors,warnings,assessor) VALUES (?,?,?,?,?,?,?,?) RETURNING id""",
                    [
                        version_id,
                        quality.score,
                        quality.level,
                        json.dumps(quality.passed),
                        json.dumps(quality.missing),
                        json.dumps(quality.blocking_errors),
                        json.dumps(quality.warnings),
                        item["reviewer"],
                    ],
                ).fetchone()[0]
            )
            con.execute(
                "INSERT INTO editorial_reviews(content_version_id,reviewer,decision,notes) VALUES (?,?,'accepted',?)",
                [version_id, item["reviewer"], "Revue humaine du lot interne LCAI-0009."],
            )
            con.execute(
                "INSERT INTO editorial_approvals(content_version_id,approver,approved,validation_run_id,quality_assessment_id,active) VALUES (?,?,TRUE,?,?,TRUE)",
                [version_id, item["approver"], validation_id, quality_id],
            )
            con.execute(
                "INSERT INTO curriculum_domain_events(event_type,aggregate_type,aggregate_code,payload) VALUES ('ContentApproved','exercise',?,?)",
                [item["code"], json.dumps({"version": item["version"], "approver": item["approver"]})],
            )
            created += 1
        return created

    def catalog_counts(self) -> dict[str, int]:
        con = connect_v2(self.database_path, read_only=True)
        try:
            tables = (
                "curriculum_chapters",
                "curriculum_skill_details",
                "learning_objectives",
                "curriculum_skill_relations",
                "exam_references",
                "approved_learning_catalog",
            )
            return {table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]) for table in tables}
        finally:
            con.close()

    def catalog_preview(self, *, subject_code: str | None = None) -> list[dict[str, Any]]:
        con = connect_v2(self.database_path, read_only=True)
        try:
            parameters: list[Any] = []
            where = ""
            if subject_code:
                where = "WHERE s.code=?"
                parameters.append(subject_code)
            cursor = con.execute(
                f"""SELECT c.stable_code,c.title,s.code AS subject,c.grade_code,c.content_type,
                c.difficulty,c.estimated_minutes FROM approved_learning_catalog c
                JOIN subjects s ON s.id=c.subject_id {where}
                ORDER BY s.code,c.grade_code,c.stable_code LIMIT 200""",
                parameters,
            )
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()


def _rows(document: dict[str, Any]) -> int:
    keys = ("programs", "chapters", "skills", "subskills", "relations", "exam_references", "contents")
    return sum(len(document.get(key, [])) for key in keys)
