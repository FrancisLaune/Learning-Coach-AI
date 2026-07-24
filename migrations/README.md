# Migrations DuckDB

## V1 — application actuelle

La V7.0 applique encore ses colonnes complémentaires dans `core.database.init_db()`.
Cette base reste inchangée pendant la migration progressive.

## V2 — learning model foundation

Les migrations versionnées se trouvent dans `migrations/v2/` et ciblent uniquement
`data/learning_coach_v2.duckdb` ou le chemin fourni avec `--database`.

```console
python -m migrations --database data/learning_coach_v2.duckdb
```

Chaque migration est transactionnelle, journalisée dans `schema_versions` et vérifiée
par checksum. Une migration déjà appliquée ne doit jamais être modifiée.

La migration `005_content_management.sql` ajoute de façon additive le versionnement,
les médias, les tags et les rapports de validation de LCAI-0005.
La migration `006_content_media_links.sql` ajoute les associations ordonnées entre
les métadonnées média et les contenus, sans stockage de fichiers.
La migration `007_longitudinal_learning.sql` ajoute les parcours scolaires, les
preuves idempotentes, la maîtrise longitudinale, les événements et les projections
de préparation aux transitions et examens.
La migration `008_decision_engine.sql` ajoute les préférences du Journey, les objectifs
pédagogiques, les plans ordonnés et les snapshots de décisions explicables.
La migration `009_onboarding_content_recommendation.sql` ajoute les profils fonctionnels,
versions de Journey, audits d'onboarding, snapshots de candidats et séances personnalisées.
La migration `010_curriculum_approved_content.sql` ajoute chapitres, objectifs observables,
graphe curriculaire, références examen, questions/corrigés/indices structurés, qualité,
revues, approbations, imports et la vue stricte du catalogue Approved.
La migration `011_learning_session_domain.sql` complète de façon additive les sessions
historiques avec activités exécutables, réponses, évaluations déterministes, tentatives
liées, indices utilisés, événements, checkpoints, résumés et audit de maîtrise.
La migration `012_session_integration_security.sql` ajoute l'idempotence des commandes,
les autorisations parentales, le gel des versions, l'état de concurrence, la reprise
de rafraîchissement décisionnel et les vues de lecture des séances.
La migration `013_learning_intelligence_layer.sql` ajoute uniquement les exécutions
analytiques et résultats dérivés versionnés, explicables et reconstructibles.
# Migration 014 — platform extensibility foundation

`014_platform_extensibility_foundation.sql` adds only V2 platform runtime
records: explicit plugin status, non-secret configuration snapshots, local
event outbox and deliveries, append-only audit records, import/export run
traces, and notification requests. It does not modify educational tables or V1.

La migration `015_unified_learning_experience.sql` ajoute les profils
d'expérience, devoirs assignables, synthèses de résultats, propositions de
programme avec validation parentale et suivi d'efficacité. Elle est additive et
ne modifie aucune table V1.
La migration `016_supported_school_levels.sql` complète les niveaux de référence
du CM1 à la 5e et ajoute l'adresse e-mail facultative au profil d'expérience.
L'interface exige cette adresse lors de toute nouvelle création d'élève.
