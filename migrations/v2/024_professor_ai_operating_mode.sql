-- LCAI-0022B — additive operating mode for Professor AI banner / modes
ALTER TABLE virtual_teacher_preferences
ADD COLUMN IF NOT EXISTS operating_mode VARCHAR DEFAULT 'MANUAL';

UPDATE virtual_teacher_preferences
SET operating_mode = 'MANUAL'
WHERE operating_mode IS NULL
   OR operating_mode NOT IN ('PROFESSOR', 'COMPANION', 'MANUAL');
