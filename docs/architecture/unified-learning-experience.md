# Expérience unifiée LCAI-0010B

`app.py` est l'unique entrée produit. Il initialise l'authentification
historique, applique les migrations V2 additives, puis route selon le rôle.
L'ancienne interface reste accessible uniquement avec
`LCAI_ENABLE_LEGACY_UI=true`.

## Étudiant

Le shell expose Accueil, séance IA, devoirs, révision, progrès, résultats,
planning et profil. L'onboarding collecte identité, naissance, classe, classe
cible, objectif, matières issues du catalogue Approved, disponibilité,
préférences d'apprentissage et choix du diagnostic.

Les devoirs ciblés et globaux utilisent exclusivement
`approved_learning_catalog`. La difficulté adaptative repose sur la dernière
difficulté longitudinale observée ; sans historique elle utilise le niveau
standard. Un devoir est matérialisé en proposition puis en `LearningSession`
par le scheduler existant.

La soumission interactive réutilise `DeterministicAssessmentEngine`,
`SubmissionService` et `LearningEngineService`. Une réponse validée produit
l'évaluation, la tentative, la mise à jour longitudinale et une entrée dans
`decision_refresh_queue`. Aucun LLM ne note ou ne modifie la maîtrise.

## Parent

Les lectures nécessitent `learner_guardian_links`. Le parent autorisé peut
créer et rattacher ses enfants, consulter leur suivi, modifier leur profil,
assigner un devoir et décider d'une proposition de niveau 3. Une modification
du profil réutilise l'onboarding, crée une version du parcours et recalcule la
recommandation.

La suppression exige une confirmation de compréhension puis la saisie exacte du
prénom. Les données propres à l'élève sont supprimées physiquement des feuilles
vers la ligne `learners`. Chaque niveau utilise une transaction courte car les
index de clés étrangères DuckDB n'autorisent pas la suppression d'un enfant et
de son parent référencé dans une même transaction. Le curriculum et le contenu
Approved partagé ne font jamais partie de la suppression.

Les décisions de programme possibles sont accepter, modifier ou refuser. Une
proposition majeure n'est jamais appliquée automatiquement.

## Initialisation Streamlit

L'initialisation V1 et les migrations V2 s'exécutent une seule fois par
processus Python derrière un verrou. Les reruns Streamlit réutilisent ensuite le
runtime initialisé et ne rouvrent pas le runner de migrations à chaque
interaction.

## Migration progressive

Les modules V1, leurs générateurs et leurs données restent présents. Ils ne sont
pas supprimés tant que les scénarios d'équivalence ne sont pas tous validés.
Le contenu V1 n'est pas présenté comme Approved et n'est pas copié
automatiquement dans V2.
