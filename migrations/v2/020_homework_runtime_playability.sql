-- LCAI-0018B5: link runtime homework exercises to playable catalog entities.

ALTER TABLE homework_runtime_exercises ADD COLUMN IF NOT EXISTS content_id BIGINT;
ALTER TABLE homework_runtime_exercises ADD COLUMN IF NOT EXISTS content_version_id BIGINT;
ALTER TABLE homework_runtime_exercises ADD COLUMN IF NOT EXISTS chapter_id BIGINT;
ALTER TABLE homework_runtime_exercises ADD COLUMN IF NOT EXISTS skill_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_homework_runtime_exercises_content
    ON homework_runtime_exercises(content_id, content_version_id);
