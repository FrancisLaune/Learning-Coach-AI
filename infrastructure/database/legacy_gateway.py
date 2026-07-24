"""Compatibility API used by Streamlit while repositories replace direct DB imports."""

from __future__ import annotations

from infrastructure.database.repositories import (
    ExamRepository,
    PracticeRepository,
    ProgressRepository,
    UserRepository,
)

_users = UserRepository()
_exams = ExamRepository()
_practice = PracticeRepository()
_progress = ProgressRepository()

authenticate = _users.authenticate
create_parent = _users.create_parent
create_student_account = _users.create_student_account
deactivate_student_account = _users.deactivate_student_account
delete_student_account = _users.delete_student_account
has_active_student_account = _users.has_active_student_account
reactivate_student_account = _users.reactivate_student_account
reset_student_password = _users.reset_student_password
student_account_for_learner = _users.student_account_for_learner
create_user = _users.create_user
student_list = _users.student_list

create_exam = _exams.create_exam
finish_exam = _exams.finish_exam
get_exam = _exams.get_exam
list_exams = _exams.list_exams
save_exam_answers = _exams.save_exam_answers

practice_chapter_stats = _practice.practice_chapter_stats
save_practice_attempt = _practice.save_practice_attempt
weakest_chapters = _practice.weakest_chapters

activity_progression = _progress.activity_progression
advanced_learning_overview = _progress.advanced_learning_overview
chapter_performance = _progress.chapter_performance
dashboard_metrics = _progress.dashboard_metrics
exam_chapter_analysis = _progress.exam_chapter_analysis
learning_overview = _progress.learning_overview
note_history = _progress.note_history
practice_difficulty_stats = _progress.practice_difficulty_stats
subject_averages = _progress.subject_averages
time_progression = _progress.time_progression
