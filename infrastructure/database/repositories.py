"""Repository adapters delegating to the unchanged DuckDB V1 implementation."""

from __future__ import annotations

from core import database as legacy


class UserRepository:
    """User operations backed by ``core.database`` during migration."""

    authenticate = staticmethod(legacy.authenticate)
    create_parent = staticmethod(legacy.create_parent)
    create_student_account = staticmethod(legacy.create_student_account)
    deactivate_student_account = staticmethod(legacy.deactivate_student_account)
    delete_student_account = staticmethod(legacy.delete_student_account)
    has_active_student_account = staticmethod(legacy.has_active_student_account)
    reactivate_student_account = staticmethod(legacy.reactivate_student_account)
    reset_student_password = staticmethod(legacy.reset_student_password)
    student_account_for_learner = staticmethod(legacy.student_account_for_learner)
    request_parent_password_reset = staticmethod(legacy.request_parent_password_reset)
    request_child_password_recovery = staticmethod(legacy.request_child_password_recovery)
    complete_password_reset = staticmethod(legacy.complete_password_reset)
    session_user_still_valid = staticmethod(legacy.session_user_still_valid)
    create_user = staticmethod(legacy.create_user)
    student_list = staticmethod(legacy.student_list)


class ExamRepository:
    """Exam operations backed by the existing schema and functions."""

    create_exam = staticmethod(legacy.create_exam)
    finish_exam = staticmethod(legacy.finish_exam)
    get_exam = staticmethod(legacy.get_exam)
    list_exams = staticmethod(legacy.list_exams)
    save_exam_answers = staticmethod(legacy.save_exam_answers)


class PracticeRepository:
    """Practice operations backed by the existing schema and functions."""

    practice_chapter_stats = staticmethod(legacy.practice_chapter_stats)
    save_practice_attempt = staticmethod(legacy.save_practice_attempt)
    weakest_chapters = staticmethod(legacy.weakest_chapters)


class ProgressRepository:
    """Read-only analytics queries backed by the existing implementation."""

    activity_progression = staticmethod(legacy.activity_progression)
    advanced_learning_overview = staticmethod(legacy.advanced_learning_overview)
    chapter_performance = staticmethod(legacy.chapter_performance)
    dashboard_metrics = staticmethod(legacy.dashboard_metrics)
    exam_chapter_analysis = staticmethod(legacy.exam_chapter_analysis)
    learning_overview = staticmethod(legacy.learning_overview)
    note_history = staticmethod(legacy.note_history)
    practice_difficulty_stats = staticmethod(legacy.practice_difficulty_stats)
    subject_averages = staticmethod(legacy.subject_averages)
    time_progression = staticmethod(legacy.time_progression)
