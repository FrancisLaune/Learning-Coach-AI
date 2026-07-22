# DuckDB V2 — modèle de données de référence

## Objectifs

Le modèle V2 remplace les libellés libres comme identifiants, sépare contenu et événements d'apprentissage, conserve l'historique et rend chaque recommandation explicable. Il reste pragmatique pour un fichier DuckDB local.

Conventions : clés `BIGINT` issues de séquences (ou UUID si une synchronisation multi-instance devient nécessaire), timestamps UTC, identifiants fonctionnels `code` stables, scores dans `[0,1]`, tables d'événements append-only. Les suppressions métier sont logiques (`archived_at`) lorsque l'historique les référence.

## Référentiel et identité

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `schema_versions` | `version PK`, `name`, `checksum`, `applied_at`, `execution_ms`, `status` | une ligne par migration; `status IN ('applied','failed','rolled_back')` |
| `users` | `id PK`, `display_name`, `credential_hash`, `role`, `created_at`, `archived_at` | `role IN ('learner','parent','admin')`; nom non utilisé comme identité |
| `learner_profiles` | `user_id PK/FK`, `school_level_id FK`, `timezone`, `preferences_json`, `created_at`, `updated_at` | profil administratif (`learner_profile` conceptuel), relation 1–0..1 avec `users` |
| `guardian_learners` | `guardian_user_id FK`, `learner_user_id FK`, `created_at` | PK composite; deux rôles différents; N–N |
| `school_levels` | `id PK`, `code UNIQUE`, `label`, `rank`, `active_from`, `active_to` | programme/niveau versionnable |
| `programs` | `id PK`, `code`, `version`, `label`, `country_code`, `jurisdiction`, `exam_type`, `valid_from`, `valid_to` | table `program`; `UNIQUE(code, version, country_code)` |
| `subjects` | `id PK`, `code UNIQUE`, `label`, `archived_at` | matière réutilisable entre programmes |
| `program_subjects` | `program_id FK`, `subject_id FK`, `school_level_id FK`, `display_order`, `weight` | PK composite; N–N versionné |

## Compétences et programmes

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `domains` | `id PK`, `subject_id FK`, `code`, `label`, `description`, `archived_at` | table `domain`; `UNIQUE(subject_id, code)` |
| `skills` | `id PK`, `domain_id FK`, `code`, `label`, `description`, `archived_at` | `UNIQUE(domain_id, code)` |
| `subskills` | `id PK`, `skill_id FK`, `code`, `label`, `description`, `archived_at` | `UNIQUE(skill_id, code)` |
| `program_skills` | `program_id FK`, `skill_id FK`, `expected_mastery`, `priority`, `display_order` | PK composite; valeurs `[0,1]` |
| `skill_prerequisites` | `skill_id FK`, `prerequisite_skill_id FK`, `weight` | PK composite; pas d'auto-boucle; graphe acyclique validé applicativement |

La hiérarchie physique suit `programs → program_subjects → subjects → domains → skills → subskills`. Les chapitres actuels doivent être mappés vers `Domain`, `Skill` ou regroupement éditorial après validation pédagogique; aucune conversion par libellé seul.

## Contenu, exercices et questions

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `exercises` | `id PK`, `subject_id FK`, `code`, `title`, `objective`, `estimated_seconds`, `difficulty`, `instructions`, `evaluation_strategy_json`, `content_version`, `status`, `created_at`, `archived_at` | table `exercise`; `UNIQUE(code, content_version)`; difficulté 1–5 |
| `questions` | `id PK`, `code`, `statement`, `answer_type`, `expected_answer_json`, `explanation`, `estimated_seconds`, `content_version`, `status` | item évaluable versionné; `UNIQUE(code, content_version)` |
| `exercise_questions` | `exercise_id FK`, `question_id FK`, `position`, `points`, `required` | table `exercise_question`; PK composite, `UNIQUE(exercise_id, position)`; exercice 1–N questions |
| `question_hints` | `id PK`, `question_id FK`, `position`, `content`, `penalty` | indices graduels, `UNIQUE(question_id, position)` |
| `question_skills` | `question_id FK`, `skill_id FK`, `weight`, `is_primary` | PK composite; poids positifs, au moins une compétence principale |
| `question_subskills` | `question_id FK`, `subskill_id FK`, `weight`, `is_primary` | PK composite; précision atomique optionnelle |
| `question_variants` | `id PK`, `question_id FK`, `variant_key`, `parameters_json`, `prompt`, `expected_answer_json` | `UNIQUE(question_id, variant_key)` |

Le JSON est réservé aux réponses structurées et paramètres dont le schéma est validé dans le code. Le texte d'une tentative garde aussi un snapshot pour rendre l'historique lisible après évolution du contenu.

## Sessions, tentatives et résultats

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `learning_sessions` | `id PK`, `learner_id FK`, `kind`, `status`, `started_at`, `finished_at`, `objective_id FK nullable`, `engine_version` | fin postérieure au début; statut contrôlé |
| `session_items` | `id PK`, `session_id FK`, `exercise_id FK`, `position`, `decision_id FK nullable`, `presented_at` | `UNIQUE(session_id, position)` |
| `attempts` | `id PK`, `learner_id FK`, `session_item_id FK nullable`, `question_id FK`, `attempt_no`, `submitted_at`, `answer_json`, `is_correct`, `score`, `elapsed_ms`, `difficulty_at_attempt`, `prompt_snapshot`, `expected_snapshot_json` | score `[0,1]`, durées positives, unicité par item/numéro |
| `attempt_skill_results` | `attempt_id FK`, `skill_id FK`, `evidence_score`, `weight`, `error_category_id FK nullable` | PK composite; scores `[0,1]` |
| `error_categories` | `id PK`, `code UNIQUE`, `label`, `description` | taxonomie administrée |
| `learner_gaps` | `id PK`, `learner_id FK`, `skill_id FK`, `status`, `severity`, `first_seen_at`, `last_seen_at`, `resolved_at` | un gap ouvert par apprenant/compétence (contrôle applicatif) |

Cardinalités essentielles : un apprenant a N sessions; une session a N items; une question a N tentatives; une tentative apporte des preuves sur N compétences; une compétence reçoit N preuves et N états historiques.

## Maîtrise, recommandations et objectifs

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `mastery_events` | `id PK`, `learner_id FK`, `skill_id FK`, `attempt_id FK nullable`, `event_at`, `previous_score`, `new_score`, `evidence`, `model_version`, `factors_json` | append-only, scores `[0,1]` |
| `mastery_current` | `learner_id FK`, `skill_id FK`, `score`, `confidence`, `last_evidence_at`, `next_review_at`, `half_life_days`, `model_version`, `updated_at` | PK composite; projection reconstructible |
| `objectives` | `id PK`, `learner_id FK`, `program_id FK nullable`, `kind`, `title`, `target_date`, `target_score`, `status`, `created_at`, `completed_at` | cible et statut contrôlés |
| `objective_skills` | `objective_id FK`, `skill_id FK`, `weight`, `target_mastery` | PK composite; poids positifs |
| `recommendations` | `id PK`, `learner_id FK`, `decision_id FK`, `kind`, `target_skill_id FK nullable`, `target_exercise_id FK nullable`, `priority_score`, `reason_code`, `explanation_json`, `status`, `created_at`, `expires_at` | dérivée d'une décision; cible compétence ou exercice |
| `learning_decisions` | `id PK`, `learner_id FK`, `session_id FK nullable`, `decision_type`, `engine_version`, `ruleset_version`, `context_hash`, `inputs_json`, `candidates_json`, `selected_entity_type`, `selected_entity_id`, `scheduled_for`, `difficulty`, `duration_seconds`, `scores_json`, `reason_codes_json`, `created_at`, `correlation_id` | table `learning_decisions`, append-only; décision complète et explicable |

`mastery_current` est une projection optimisée, jamais la seule preuve. `mastery_events` et `learning_decisions` permettent de reproduire ou expliquer le calcul.

## Learner Cognitive Profile

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `learner_cognitive_profiles` | `learner_id PK/FK`, dix indicateurs, dix confiances associées, `observation_window_start`, `observation_window_end`, `model_version`, `updated_at` | projection du `learner_profile` cognitif; valeurs `[0,1]` ou null si inconnues |
| `cognitive_profile_events` | `id PK`, `learner_id FK`, `indicator`, `previous_value`, `new_value`, `confidence`, `factors_json`, `model_version`, `calculated_at` | append-only; indicateur contrôlé |
| `cognitive_observations` | `id PK`, `learner_id FK`, `session_id FK nullable`, `attempt_id FK nullable`, `indicator`, `value`, `quality`, `observed_at` | preuve normalisée et traçable |

Les dix indicateurs et leurs calculs sont définis dans [Learner Cognitive Profile](learner-cognitive-profile.md). Les valeurs inconnues restent nulles et ne sont pas remplacées par zéro.

## AI Coach et audit

| Table | Colonnes principales | Contraintes et relations |
|---|---|---|
| `prompt_templates` | `id PK`, `name`, `version`, `template_hash`, `status`, `created_at` | `UNIQUE(name, version)`; contenu éventuellement en fichiers versionnés |
| `ai_interactions` | `id PK`, `learner_id FK`, `provider`, `model`, `prompt_template_id FK`, `context_hash`, `decision_id FK nullable`, `request_at`, `response_at`, `outcome`, `safety_flags_json`, `token_usage_json`, `correlation_id` | métadonnées; contenu brut selon politique de rétention |
| `pedagogical_memory_snapshots` | `id PK`, `learner_id FK`, `purpose`, `window_start`, `window_end`, `summary_json`, `source_refs_json`, `expires_at`, `model_version`, `created_at` | projection recalculable de Conversation Memory; jamais mémoire permanente du LLM |

## Index utiles

DuckDB bénéficie du zonemapping mais les parcours fréquents justifient d'évaluer :

- `attempts(learner_id, submitted_at)`, `attempts(question_id, submitted_at)`;
- `mastery_events(learner_id, skill_id, event_at)`;
- `mastery_current(learner_id, next_review_at)`;
- `learning_sessions(learner_id, started_at)`;
- `session_items(session_id, position)`;
- `recommendations(learner_id, status, created_at)`;
- `objectives(learner_id, status, target_date)`;
- `learning_decisions(learner_id, created_at)`, `learning_decisions(session_id, created_at)`;
- index sur toutes les FK si les plans de requête le justifient.

Les index doivent être confirmés par `EXPLAIN` sur des volumes représentatifs; ne pas les créer mécaniquement.

## Historisation et rétention

- `attempts`, `attempt_skill_results`, `mastery_events`, `cognitive_profile_events` et `learning_decisions` sont append-only.
- Les corrections d'erreur produisent un événement compensatoire ou une colonne d'annulation auditée, jamais une réécriture silencieuse.
- Les référentiels ont version/validité ou archivage logique.
- Les projections courantes sont recalculables et portent leur version de modèle.
- Les interactions IA suivent une durée de rétention configurable; par défaut, conserver métadonnées et hashes, pas les prompts contenant des données personnelles.
- Les timestamps sont UTC; le fuseau du profil sert seulement à l'affichage/planification.

## Stratégie de migration depuis l'existant

1. Décider l'autorité des trois bases; produire une copie de sauvegarde et leurs checksums.
2. Ajouter un exécuteur de migrations versionnées avec transaction, verrou, checksum et journal `schema_versions`.
3. Créer V2 à côté des tables actuelles dans une copie de travail; ne pas renommer ni supprimer V1.
4. Charger référentiels et table de correspondance `legacy_id_map(source_db, source_table, legacy_id, v2_table, v2_id)`.
5. Migrer utilisateurs en traitant séparément les credentials historiques; ne jamais copier un PIN clair comme credential valide.
6. Mapper les libellés matières/chapitres vers identifiants stables, avec rapport des valeurs inconnues.
7. Convertir examens/questions/tentatives; conserver snapshots et provenance (`source_system`, `legacy_id`).
8. Recalculer les preuves et projections de maîtrise avec une version de modèle dédiée à l'import.
9. Valider comptages, sommes, orphelins, distributions de notes, dates et échantillons anonymisés.
10. Faire un dry-run puis une répétition chronométrée; définir restauration atomique du fichier et période de double lecture avant bascule.

Les deux SQLite n'ont pas le même schéma et leur statut est incertain. Aucune fusion automatique ne doit se faire avant validation de leur provenance et détection des doublons utilisateurs/exercices.
