# Structure cible du projet

## Principe

La cible est un monolithe modulaire installable sous `src/learning_coach/`. Chaque couche possède un sens précis; il n'est pas nécessaire de créer tous les fichiers immédiatement. Les extractions doivent être verticales et couvertes par des tests.

```text
Learning-Coach-AI/
├── pyproject.toml
├── README.md
├── src/
│   └── learning_coach/
│       ├── bootstrap.py
│       ├── config.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── value_objects.py
│       │   ├── policies.py
│       │   └── errors.py
│       ├── application/
│       │   ├── dto.py
│       │   ├── ports.py
│       │   └── use_cases/
│       │       ├── authenticate_user.py
│       │       ├── start_practice.py
│       │       ├── submit_attempt.py
│       │       ├── start_exam.py
│       │       ├── finish_exam.py
│       │       └── get_progress.py
│       ├── decision_engine/
│       │   ├── service.py
│       │   ├── scheduler.py
│       │   ├── selector.py
│       │   ├── prioritizer.py
│       │   └── explanations.py
│       ├── learning_engine/
│       │   ├── mastery.py
│       │   ├── forgetting.py
│       │   ├── cognitive_profile.py
│       │   └── evidence.py
│       ├── content/
│       │   ├── registry.py
│       │   ├── contracts.py
│       │   └── subjects/
│       ├── ai_coach/
│       │   ├── service.py
│       │   ├── context_builder.py
│       │   ├── conversation_memory.py
│       │   ├── grounding.py
│       │   ├── prompts.py
│       │   └── providers.py
│       ├── analytics/
│       │   ├── queries.py
│       │   ├── metrics.py
│       │   └── reporting.py
│       ├── infrastructure/
│       │   ├── db/
│       │   │   ├── connection.py
│       │   │   ├── repositories.py
│       │   │   ├── unit_of_work.py
│       │   │   └── migrations/
│       │   ├── llm/
│       │   ├── logging.py
│       │   └── clock.py
│       └── ui/
│           └── streamlit/
│               ├── app.py
│               ├── session.py
│               ├── components/
│               └── pages/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── ui/
│   └── fixtures/
├── data/                  # bases locales ignorées ou jeux anonymisés dédiés
├── docs/architecture/
└── scripts/               # commandes explicites de migration/maintenance
```

## Responsabilités et règles de dépendance

| Package | Responsabilité | Peut dépendre de |
|---|---|---|
| `domain` | Entités, valeurs, invariants pédagogiques | Bibliothèque standard uniquement |
| `application` | Orchestration des cas d'usage et transactions | `domain`, ports abstraits |
| `learning_engine` | Mastery, oubli, profil cognitif et transformation des preuves | `domain` |
| `decision_engine` | Arbitrage du quoi/pourquoi/quand/ordre/difficulté/durée; orchestration du Scheduler et du Selector | `domain`, `learning_engine`, ports abstraits |
| `content` | Référentiel `Program/Subject/Domain/Skill/SubSkill` et contenu `Exercise/Question` | `domain` |
| `ai_coach` | Construction de contexte et mémoire pédagogique, génération contrôlée | DTO/ports, jamais SQL direct |
| `analytics` | Projections et rapports, sans mutation métier | ports de lecture, domaine |
| `infrastructure` | DuckDB, fournisseurs LLM, logs, horloge | interfaces internes + bibliothèques externes |
| `ui.streamlit` | Affichage et collecte d'entrées | cas d'usage et DTO uniquement |

`bootstrap.py` est la racine de composition : il lit la configuration, construit repositories/services/cas d'usage et les transmet à l'UI. Aucun module de domaine ne doit importer Streamlit, DuckDB, pandas, Plotly ou un SDK LLM.

## Contrats recommandés

- Entités/dataclasses typées : `Learner`, `Program`, `Subject`, `Domain`, `Skill`, `SubSkill`, `Exercise`, `Question`, `Attempt`, `Mastery`, `Objective`, `Decision`, `Recommendation`.
- Value objects/enums : `LearnerId`, `SkillId`, `ExerciseId`, `Difficulty`, `MasteryScore`, `ExerciseStatus`.
- Ports : `LearnerRepository`, `ExerciseRepository`, `AttemptRepository`, `MasteryRepository`, `DecisionRepository`, `LLMProvider`, `Clock`.
- DTO immuables aux frontières de l'UI; aucun DataFrame comme contrat de cas d'usage.
- DataFrames réservés aux adaptateurs analytics/présentation.

## Migration progressive du code

1. Ajouter des tests de caractérisation autour de `core.engine`, `analytics` et des parcours DuckDB.
2. Extraire la connexion et les repositories sans changer le schéma.
3. Extraire un premier cas d'usage vertical, par exemple `submit_attempt`, et faire appeler celui-ci par Streamlit.
4. Déplacer progressivement les vues de `app.py` vers `ui/streamlit/pages`.
5. Introduire le domaine de compétences et les repositories V2 derrière ports.
6. Basculer les lectures/écritures vers V2 après migration validée; conserver une compatibilité temporaire explicite.
7. Ajouter le Learning Engine, puis seulement le service AI Coach.

## Standards de développement

### Outils et configuration

Centraliser dans `pyproject.toml` : Python `>=3.14,<3.15`, Ruff pour lint/imports, Black pour formatage, MyPy en mode progressivement strict, Pytest et couverture. Verrouiller les dépendances dans un lockfile généré après validation Python 3.14. Ne pas mettre les outils de développement dans les dépendances d'exécution.

### Style et typage

- annotations sur toute API publique; interdire progressivement `Any` aux frontières du domaine;
- dataclasses ou modèles immuables pour les données structurées;
- docstrings courtes sur modules/classes/fonctions publiques lorsque le contrat n'est pas évident;
- fonctions ciblées, noms anglais cohérents dans le code et libellés français dans la présentation;
- SQL paramétré et isolé dans l'infrastructure.

### Erreurs, logs, configuration et secrets

- erreurs métier explicites (`AuthenticationFailed`, `InvalidAttempt`, `MigrationError`), traduites en messages utilisateur dans l'UI;
- ne capturer que les exceptions attendues; conserver cause et stack dans les logs;
- logs structurés avec `request_id/session_id`, `user_id` pseudonymisé, cas d'usage, durée et résultat; jamais PIN, réponse LLM brute sensible ou secret;
- configuration typée chargée au démarrage, avec valeurs non sensibles par défaut;
- secrets uniquement via variables d'environnement ou gestionnaire de secrets Streamlit, jamais versionnés;
- hash de PIN par algorithme dédié aux mots de passe avec sel et paramètre de coût lors du ticket sécurité.

### Git

- branche courte `codex/LCAI-####-description` (ou convention d'équipe équivalente);
- commits atomiques sous forme `LCAI-####: verbe et objet`, par exemple `LCAI-0003: add attempt repository contract`;
- pull request liée au ticket, avec migration/rollback, tests et captures UI si pertinent;
- `main` toujours publiable; pas de base locale ni secret dans les commits futurs.

### Tests

- unitaires : normalisation/correction, score, oubli, sélection, règles et cas limites;
- intégration : repositories contre un DuckDB temporaire, contraintes, transactions et migrations de copies anonymisées;
- contrat : chaque fournisseur LLM/repository respecte le même port;
- UI : smoke tests de démarrage et tests des parcours critiques; limiter les assertions visuelles fragiles;
- non-régression : fixtures déterministes avec générateur aléatoire injecté;
- migration : idempotence, comptages, correspondances, orphelins, rollback/restauration.
