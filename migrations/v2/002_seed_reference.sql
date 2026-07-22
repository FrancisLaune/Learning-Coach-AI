-- Stable reference identifiers stay below the generated-ID range (100000+).
INSERT INTO school_levels(id, code, label, rank, country_code) VALUES
    (1, 'FR-3E', 'Troisième', 3, 'FR');

INSERT INTO programs(
    id, code, version, label, country_code, jurisdiction, exam_type,
    default_language_code, valid_from, valid_to
) VALUES
    (1, 'BREVET', '2027', 'Brevet 2027', 'FR', 'Éducation nationale', 'DNB', 'fr-FR', DATE '2026-09-01', DATE '2027-08-31');

INSERT INTO subjects(id, code, default_label) VALUES
    (1, 'MATHEMATICS', 'Mathématiques'),
    (2, 'FRENCH', 'Français'),
    (3, 'ENGLISH', 'Anglais'),
    (4, 'SPANISH', 'Espagnol'),
    (5, 'HISTORY', 'Histoire'),
    (6, 'GEOGRAPHY', 'Géographie'),
    (7, 'SVT', 'SVT'),
    (8, 'PHYSICS_CHEMISTRY', 'Physique-Chimie'),
    (9, 'EMC', 'EMC'),
    (10, 'TECHNOLOGY', 'Technologie');

INSERT INTO program_subjects(program_id, subject_id, school_level_id, display_order, weight)
SELECT 1, id, 1, id, 1 FROM subjects ORDER BY id;

INSERT INTO domains(id, subject_id, code, default_label, display_order) VALUES
    (101, 1, 'NUMBERS', 'Nombres et calculs', 1),
    (102, 1, 'ALGEBRA', 'Algèbre et fonctions', 2),
    (103, 1, 'GEOMETRY', 'Géométrie', 3),
    (104, 1, 'DATA', 'Données et probabilités', 4),
    (201, 2, 'LANGUAGE_STUDY', 'Étude de la langue', 1),
    (202, 2, 'READING', 'Lecture et interprétation', 2),
    (203, 2, 'WRITING', 'Écriture', 3),
    (301, 3, 'COMMUNICATION', 'Communication', 1),
    (302, 3, 'LANGUAGE', 'Langue', 2),
    (401, 4, 'COMMUNICATION', 'Communication', 1),
    (402, 4, 'LANGUAGE', 'Langue', 2),
    (501, 5, 'MODERN_HISTORY', 'Histoire moderne', 1),
    (502, 5, 'CONTEMPORARY_HISTORY', 'Histoire contemporaine', 2),
    (601, 6, 'TERRITORIES', 'Territoires', 1),
    (602, 6, 'GLOBALIZATION', 'Mondialisation', 2),
    (701, 7, 'LIVING_WORLD', 'Le vivant', 1),
    (702, 7, 'EARTH', 'La planète Terre', 2),
    (801, 8, 'MATTER', 'Matière et transformations', 1),
    (802, 8, 'ENERGY', 'Énergie et mouvements', 2),
    (901, 9, 'CITIZENSHIP', 'Citoyenneté et République', 1),
    (1001, 10, 'TECHNICAL_SYSTEMS', 'Systèmes techniques', 1);

INSERT INTO skills(id, domain_id, code, default_label, display_order) VALUES
    (10001, 101, 'CALCULATE_NUMBERS', 'Calculer avec les nombres', 1),
    (10002, 101, 'USE_PROPORTIONS', 'Utiliser proportionnalité et pourcentages', 2),
    (10003, 102, 'SOLVE_EQUATIONS', 'Résoudre des équations', 1),
    (10004, 102, 'USE_FUNCTIONS', 'Utiliser les fonctions', 2),
    (10005, 103, 'APPLY_PYTHAGORAS', 'Appliquer le théorème de Pythagore', 1),
    (10006, 103, 'APPLY_THALES', 'Appliquer le théorème de Thalès', 2),
    (10007, 104, 'ANALYZE_DATA', 'Analyser des données', 1),
    (10008, 104, 'CALCULATE_PROBABILITY', 'Calculer une probabilité', 2),
    (11001, 201, 'ANALYZE_GRAMMAR', 'Analyser la grammaire', 1),
    (11002, 202, 'INTERPRET_TEXT', 'Interpréter un texte', 1),
    (11003, 203, 'WRITE_ARGUMENT', 'Rédiger un texte argumenté', 1),
    (12001, 301, 'UNDERSTAND_ENGLISH', 'Comprendre un message en anglais', 1),
    (12002, 302, 'USE_ENGLISH_GRAMMAR', 'Utiliser la grammaire anglaise', 1),
    (13001, 401, 'UNDERSTAND_SPANISH', 'Comprendre un message en espagnol', 1),
    (13002, 402, 'USE_SPANISH_GRAMMAR', 'Utiliser la grammaire espagnole', 1),
    (14001, 501, 'LOCATE_HISTORICAL_PERIODS', 'Situer les périodes historiques', 1),
    (14002, 502, 'EXPLAIN_CONTEMPORARY_EVENTS', 'Expliquer les événements contemporains', 1),
    (15001, 601, 'ANALYZE_TERRITORY', 'Analyser un territoire', 1),
    (15002, 602, 'EXPLAIN_GLOBALIZATION', 'Expliquer la mondialisation', 1),
    (16001, 701, 'EXPLAIN_LIVING_SYSTEMS', 'Expliquer les systèmes vivants', 1),
    (16002, 702, 'EXPLAIN_EARTH_SYSTEMS', 'Expliquer les systèmes terrestres', 1),
    (17001, 801, 'DESCRIBE_MATTER', 'Décrire la matière et ses transformations', 1),
    (17002, 802, 'ANALYZE_ENERGY', 'Analyser énergie et mouvement', 1),
    (18001, 901, 'EXERCISE_CITIZENSHIP', 'Exercer sa citoyenneté', 1),
    (19001, 1001, 'ANALYZE_TECHNICAL_SYSTEM', 'Analyser un système technique', 1);

INSERT INTO subskills(id, skill_id, code, default_label, display_order) VALUES
    (20001, 10005, 'DIRECT_CASE', 'Cas direct', 1),
    (20002, 10005, 'CONVERSE_CASE', 'Réciproque', 2),
    (20003, 10006, 'DIRECT_CASE', 'Cas direct', 1),
    (20004, 10006, 'CONVERSE_CASE', 'Réciproque', 2),
    (20005, 11001, 'IDENTIFY_SUBORDINATE_CLAUSES', 'Identifier les propositions subordonnées', 1),
    (20006, 10003, 'ONE_VARIABLE_EQUATION', 'Équation à une inconnue', 1);

INSERT INTO program_skills(program_id, skill_id, expected_mastery, priority, display_order)
SELECT 1, id, 0.8, 1, row_number() OVER (ORDER BY id) FROM skills ORDER BY id;

INSERT INTO skill_prerequisites(skill_id, prerequisite_skill_id, weight) VALUES
    (10003, 10001, 1),
    (10004, 10003, 1),
    (10005, 10001, 0.8),
    (10006, 10002, 0.8),
    (10008, 10001, 0.7);

INSERT INTO error_categories(id, code, label, description) VALUES
    (1, 'NO_ANSWER', 'Réponse absente', 'Aucune réponse exploitable.'),
    (2, 'CALCULATION', 'Erreur de calcul', 'La méthode est pertinente mais le calcul est incorrect.'),
    (3, 'METHOD', 'Erreur de méthode', 'La stratégie choisie ne permet pas de résoudre la question.'),
    (4, 'MISREAD', 'Consigne mal interprétée', 'La réponse ne traite pas la demande formulée.');

INSERT INTO reference_translations(entity_type, entity_id, language_code, label) VALUES
    ('program', 1, 'fr-FR', 'Brevet 2027'),
    ('program', 1, 'en-GB', 'French National Diploma 2027'),
    ('school_level', 1, 'fr-FR', 'Troisième'),
    ('school_level', 1, 'en-GB', 'Year 10 equivalent'),
    ('subject', 1, 'fr-FR', 'Mathématiques'),
    ('subject', 1, 'en-GB', 'Mathematics'),
    ('subject', 2, 'fr-FR', 'Français'),
    ('subject', 2, 'en-GB', 'French'),
    ('subject', 3, 'fr-FR', 'Anglais'),
    ('subject', 3, 'en-GB', 'English'),
    ('subject', 4, 'fr-FR', 'Espagnol'),
    ('subject', 4, 'en-GB', 'Spanish'),
    ('subject', 5, 'fr-FR', 'Histoire'),
    ('subject', 5, 'en-GB', 'History'),
    ('subject', 6, 'fr-FR', 'Géographie'),
    ('subject', 6, 'en-GB', 'Geography'),
    ('subject', 7, 'fr-FR', 'SVT'),
    ('subject', 7, 'en-GB', 'Life and Earth Sciences'),
    ('subject', 8, 'fr-FR', 'Physique-Chimie'),
    ('subject', 8, 'en-GB', 'Physics and Chemistry'),
    ('subject', 9, 'fr-FR', 'EMC'),
    ('subject', 9, 'en-GB', 'Civic Education'),
    ('subject', 10, 'fr-FR', 'Technologie'),
    ('subject', 10, 'en-GB', 'Technology');
