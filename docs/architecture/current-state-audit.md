# Audit de l'existant

## Méthode et périmètre

Tous les fichiers hors `.git` et secrets Streamlit ont été inventoriés. Les 26 fichiers Python ont été analysés; les README, `requirements.txt` et `.gitignore` ont été lus. Les trois bases ont été ouvertes en lecture seule pour examiner schémas, contraintes, séquences, index et nombres de lignes. Aucune donnée métier, valeur de PIN ou secret n'a été affiché et aucune base n'a été modifiée.

## Inventaire fonctionnel

| Élément | Rôle observé |
|---|---|
| `app.py` | Point d'entrée Streamlit; CSS, session, connexion, comptes, navigation parent/élève, fiches, entraînements, devoirs, correction, graphiques et analyses. |
| `core/database.py` | Chemin et connexion DuckDB, hash des PIN, création/mise à niveau du schéma, authentification, écritures de devoir/tentative, requêtes de tableaux de bord et analytics. |
| `core/engine.py` | Normalisation/correction, contrat de question sous forme de dictionnaire, génération, variantes, séries progressives et examens. |
| `core/registry.py` | Importe et expose les dix matières par libellé. |
| `analytics/mastery.py` | Calcule un score de maîtrise à partir de réussite, temps, difficulté et nombre de tentatives. |
| `analytics/adaptive.py` | Recommande un niveau et génère un message à seuils. |
| `subjects/mathematics.py` | 15 chapitres, fiches et génération procédurale spécifique. |
| 9 autres `subjects/*.py` | Fiches et banques statiques, génération via `_helpers.generate_from_bank`. |
| `subjects/_helpers.py` | Sélection aléatoire dans une banque et préfixe selon difficulté. |
| `ui`, `ai`, `reports` | Seulement `__init__.py` vide; aucune responsabilité implémentée. |
| `migrations/README.md` | Indique que les évolutions V7 sont appliquées par `ALTER TABLE` dans `init_db()`. |

Les dix matières enregistrées sont mathématiques, français, anglais, espagnol, histoire, géographie, SVT, physique-chimie, EMC et technologie. Elles exposent toutes `SUBJECT_NAME`, `CHAPTERS` et `generate_question`; neuf exposent aussi `BANK`.

## Flux d'exécution

### Démarrage et authentification

`app.py` exécute `init_db()` à l'import, initialise `st.session_state`, puis affiche la connexion. `init_db()` crée séquences/tables/colonnes et crée un compte parent par défaut s'il est absent. `authenticate()` compare un SHA-256 simple du PIN. Après connexion, le rôle choisit `parent_app()` ou `student_app()`.

### Entraînement

L'UI sélectionne matière, chapitres, taille et mode. `core.registry` fournit le module; `core.engine` appelle son générateur et décore les questions. La correction est locale, exacte après normalisation pour le texte et avec tolérance relative de 0,1 % pour les nombres. Chaque résultat est immédiatement inséré dans `practice_attempts`. Les statistiques et recommandations sont recalculées par requêtes et fonctions analytics.

### Devoir

`build_exam()` génère une série; `create_exam()` écrit `exams` puis `exam_questions`. L'élève peut sauvegarder ou terminer. `save_exam_answers()` met à jour les questions; `finish_exam()` calcule pourcentage et note sur 20. Les vues lisent ensuite les tables via des DataFrames pandas.

### Analytics

Les requêtes sont synchrones et relues à chaque rendu. Elles agrègent examens et entraînements par matière, chapitre, difficulté et date. `compute_mastery()` pondère réussite (68 %), vitesse (17 %) et difficulté (15 %), puis applique une confiance fonction du volume. La recommandation de niveau utilise d'autres seuils dans `adaptive.py`.

## Bases observées

### DuckDB actif

`core/database.py` référence uniquement `data/objectif_brevet_2027.duckdb` (environ 4,3 Mio lors de l'audit).

| Table | Lignes observées | Contraintes déclarées |
|---|---:|---|
| `users` | 2 | PK `id`, unique `name`, NOT NULL |
| `exams` | 3 | PK `id`, plusieurs NOT NULL |
| `exam_questions` | 40 | PK `id`, plusieurs NOT NULL |
| `practice_attempts` | 97 | PK `id`, plusieurs NOT NULL |
| `learning_sessions` | 0 | PK `id`, plusieurs NOT NULL |

Cinq séquences sont présentes. Aucun index explicite n'est déclaré. Aucune clé étrangère n'est déclarée, notamment `exams.user_id → users.id`, `exam_questions.exam_id → exams.id` et `practice_attempts.user_id → users.id`. `learning_sessions` existe mais aucune fonction auditée ne l'écrit.

### SQLite historiques

- `objectif_brevet_2027.db` : `users` (2), `exercises` (32), `goals` (1), `attempts` (0), `exams` (0), `exam_questions` (0).
- `revision_3e.db` : `users` (2), `exercises` (9).

Elles stockent notamment des PIN dans une colonne `pin`, mais leur format exact n'a pas été exposé. Elles n'ont ni clés étrangères déclarées ni usage trouvé dans le code actuel. Leur relation avec DuckDB reste incertaine; elles doivent être conservées jusqu'à décision de migration/archivage.

## Dépendances et couplages

La dépendance principale est descendante depuis `app.py`. Il n'y a pas de cycle d'import Python détecté. Un couplage conceptuel existe toutefois : les matières importent `core.engine.create_question`, tandis que le moteur traite des modules de matières par introspection; `core.registry` importe toutes les matières. Une évolution du format de question traverse donc moteur, matières, base et UI sans type partagé.

Autres couplages :

- libellés de matière/chapitre/difficulté utilisés comme identifiants persistés;
- dictionnaires non typés pour utilisateurs, questions et examens;
- SQL et noms de colonnes connus directement par les vues via DataFrames;
- règles de maîtrise réparties entre SQL, `mastery.py`, `adaptive.py` et messages dans `app.py`;
- migration et démarrage fonctionnel indissociables dans `init_db()`.

## Dette et risques

### Priorité haute

- Compte parent par défaut `Parent / 1234` indiqué dans l'UI et créé automatiquement; SHA-256 sans sel ni facteur de coût n'est pas adapté au stockage de secrets.
- Absence de clés étrangères et de contraintes de domaine : orphelins et valeurs invalides possibles.
- `app.py` et `core/database.py` cumulent trop de responsabilités, rendant les tests isolés difficiles.
- Aucun test, configuration Ruff/Black/MyPy/Pytest, CI ou fichier de projet n'est présent.
- Écritures multi-étapes sans transaction explicite ni rollback applicatif; une création de devoir peut rester partielle.

### Priorité moyenne

- `create_user()` capture toute exception et la traduit en « nom existe déjà », masquant les pannes réelles.
- Connexions ouvertes/fermées manuellement, sans context manager; une exception peut laisser une ressource ouverte.
- SQL dynamique par f-string dans `learning_overview()`; les fragments sont internes, donc pas d'injection utilisateur actuelle, mais le patron est fragile.
- `build_question_set()` déclare `attempts`/`max_attempts` sans les exploiter pour régénérer; la déduplication ajoute seulement un préfixe.
- `random.shuffle(result[:...])` dans `build_progressive_set()` mélange une copie et n'a donc aucun effet.
- `learning_sessions` est du code/schéma dormant; `date` est un import inutilisé dans `core/database.py`.
- L'erreur est catégorisée en seulement « réponse absente » ou « inattention ou méthode », ce qui surinterprète les données.
- Les textes de difficulté ajoutés aux banques ne modifient souvent pas la complexité réelle de la question.

### Maintenabilité et produit

- Les banques pédagogiques sont du code Python volumineux; versionner et valider le contenu indépendamment est difficile.
- Aucune identité stable de question/compétence : le texte est dupliqué dans chaque tentative, ce qui complique l'historisation.
- Le calcul de maîtrise n'intègre pas réellement récence, oubli ou objectifs; aucune projection n'est persistée.
- Les packages annoncés dans le README ne correspondent pas encore à des modules actifs (`ui`, `ai`, `reports`).
- DuckDB limite les scénarios d'écriture concurrente; le mode de déploiement cible n'est pas documenté.

## Analyse de `requirements.txt`

| Dépendance | Usage observé | État |
|---|---|---|
| `streamlit>=1.36,<2` | UI entière | Nécessaire, plage large non verrouillée. |
| `duckdb>=1.0,<2` | Persistance active | Nécessaire, plage très large. |
| `pandas>=2.0,<3` | DataFrames et dates | Nécessaire, plage large. |
| `plotly>=5.20,<7` | Graphiques | Nécessaire, autorise deux majeures. |

Aucune dépendance d'exécution listée n'est manifestement inutilisée et aucun import tiers observé ne manque. En revanche, les outils demandés pour le futur standard (`ruff`, `black`, `pytest`, `mypy`) ne sont pas déclarés; ils devront aller dans un groupe de développement, pas être ajoutés à ce ticket. Il n'existe pas de lockfile : les installations ne sont pas reproductibles au patch près. Python 3.14 peut aussi révéler des incompatibilités selon les versions effectivement résolues; une matrice de compatibilité doit précéder le verrouillage.

## Conclusion de l'audit

L'application est cohérente pour un prototype local et ne nécessite pas de réécriture. La séquence sûre est : figer le comportement par des tests, sécuriser configuration/authentification, extraire des cas d'usage et repositories, introduire les identifiants et le schéma V2, puis ajouter moteur de maîtrise et AI Coach. Les bases historiques et les données actives doivent rester intactes jusqu'à une migration répétable et contrôlée.

