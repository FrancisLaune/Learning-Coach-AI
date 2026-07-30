# LCAI-0018B6 — Génération IA généralisée des devoirs et gestion des insuffisances de catalogue

## 1. Statut

**Statut :** READY FOR IMPLEMENTATION  
**Priorité :** HAUTE  
**Branche cible :** `develop`  
**Prérequis :** LCAI-0018B4 et LCAI-0018B5 terminés  
**Commit / push :** interdits avant validation explicite  
**Base de données locale :** ne pas committer `data/*.duckdb`

---

## 2. Constat

La création de devoirs ne doit jamais être limitée au seul nombre d’exercices déjà présents dans la base.

Exemple constaté :

- niveau : **4e** ;
- matière : **Espagnol** ;
- seulement **2 rubriques** disponibles dans l’interface ou le catalogue ;
- impossibilité de construire un devoir suffisamment riche et diversifié si le moteur reste catalogue-only.

Le comportement attendu est le suivant :

> Si le catalogue ne contient pas suffisamment d’exercices admissibles, le moteur IA ou le Professeur IA doit générer automatiquement les exercices manquants, les valider, les persister et les intégrer immédiatement au devoir courant.

Le système ne doit pas demander au parent ou à l’élève de relancer la création du devoir.

---

## 3. Objectif principal

Généraliser à toutes les classes et à toutes les matières le mécanisme de complément IA déjà amorcé sur la 4e.

Le moteur doit pouvoir créer un devoir complet même lorsque :

- le catalogue est vide ;
- le catalogue contient trop peu d’exercices ;
- la matière ne possède que peu de rubriques ;
- un chapitre possède peu de variantes ;
- le niveau de difficulté demandé n’est pas suffisamment couvert ;
- les exercices existants sont trop répétitifs ;
- les prérequis ou objectifs pédagogiques exigent davantage de diversité.

---

## 4. Principe produit

La base de données constitue la source de vérité pour :

- le curriculum ;
- les classes ;
- les matières ;
- les chapitres ;
- les compétences ;
- les prérequis ;
- les contenus approuvés ;
- les résultats ;
- les devoirs ;
- les tentatives ;
- la progression.

En revanche, **le stock d’exercices existants ne doit pas constituer une limite fonctionnelle**.

L’IA doit compléter le stock à la demande, sous contrôle des règles métier et des Quality Gates.

---

## 5. Flux cible

```text
Création d’un devoir
        ↓
Résolution classe / matière / chapitre / compétence
        ↓
Calcul du nombre et de la diversité d’exercices nécessaires
        ↓
Recherche dans le catalogue
        ↓
Mesure du déficit réel
        ↓
Catalogue suffisant ?
   ├── Oui → utiliser les exercices existants
   └── Non → générer uniquement les exercices manquants
                    ↓
              Validation automatique
                    ↓
              Persistance catalogue
                    ↓
              Intégration immédiate
                    ↓
              Création du devoir complet
                    ↓
              Séance élève jouable
```

---

## 6. Cas particulier : rubriques ou curriculum insuffisants

Le système doit distinguer deux situations.

### 6.1 Catalogue d’exercices insuffisant

Le chapitre et la compétence existent, mais il n’y a pas assez d’exercices.

**Action obligatoire :**

- générer les exercices manquants ;
- les valider ;
- les persister ;
- les utiliser immédiatement.

### 6.2 Structure curriculaire insuffisante

La matière ne contient que très peu de rubriques, chapitres ou compétences, comme le cas observé en Espagnol 4e.

Le moteur doit :

1. auditer les chapitres et compétences réellement présents ;
2. vérifier les placements curriculum existants ;
3. identifier si le manque vient :
   - de l’UI ;
   - d’un filtre ;
   - de contenus non publiés ;
   - d’un import incomplet ;
   - d’un curriculum réellement incomplet ;
4. ne pas inventer silencieusement une nouvelle structure officielle ;
5. utiliser en priorité les chapitres et compétences existants ;
6. générer plusieurs variantes d’exercices dans ces rubriques ;
7. produire un rapport de couverture ;
8. signaler séparément les lacunes curriculaires structurelles.

Une lacune de curriculum ne doit pas empêcher la génération d’un devoir si une cible pédagogique valide peut être résolue.

---

## 7. Généralisation obligatoire

Le fallback IA ne doit plus être codé uniquement pour :

- la 4e ;
- une matière ;
- un écran ;
- une feature flag spécifique à un seul niveau.

Il doit devenir un service générique utilisable pour :

- CM1 ;
- CM2 ;
- 6e ;
- 5e ;
- 4e ;
- 3e ;

et pour toutes les matières activées dans le projet :

- Mathématiques ;
- Français ;
- Anglais ;
- Espagnol ;
- Histoire ;
- Géographie ;
- SVT ;
- Physique-Chimie ;
- autres matières présentes dans le curriculum.

---

## 8. Service attendu

Créer ou généraliser un service unique du type :

```python
class HomeworkContentCompletionService:
    def complete_homework_selection(
        self,
        *,
        learner_id: str,
        grade_id: str,
        subject_id: str,
        requested_count: int,
        selected_exercises: list[ExerciseCandidate],
        pedagogical_targets: list[CurriculumTarget],
        constraints: HomeworkGenerationConstraints,
    ) -> HomeworkCompletionResult:
        ...
```

Le nom doit être adapté au code existant.

### Responsabilités

Le service doit :

- mesurer le déficit ;
- éviter les doublons ;
- décider combien d’exercices générer ;
- répartir les exercices entre chapitres et compétences ;
- imposer la diversité ;
- déclencher le générateur IA ;
- valider les résultats ;
- persister les contenus ;
- retourner les identifiants persistants ;
- compléter la proposition courante ;
- conserver la traçabilité.

---

## 9. Contrat de génération

Chaque demande de génération doit fournir au minimum :

- classe ;
- matière ;
- chapitre ;
- compétence ;
- sous-compétence si disponible ;
- prérequis ;
- difficulté ;
- type d’exercice ;
- durée cible ;
- langue ;
- réponse attendue ;
- format de correction ;
- contraintes de diversité ;
- historique récent de l’élève ;
- erreurs fréquentes ;
- nombre exact d’exercices manquants.

Exemple :

```python
GenerationSpec(
    grade="4e",
    subject="Espagnol",
    chapter_id="...",
    skill_id="...",
    difficulty="standard",
    content_type="short_answer",
    count=4,
    diversity_constraints={
        "avoid_same_statement_pattern": True,
        "vary_vocabulary": True,
        "vary_context": True,
        "avoid_recent_exercises": True,
    },
)
```

---

## 10. Règles de génération

Le moteur doit générer :

- uniquement le déficit ;
- des exercices conformes au niveau ;
- des exercices liés à une cible curriculum réelle ;
- des exercices jouables par le moteur actuel ;
- des réponses déterministes lorsque le type l’exige ;
- des corrections détaillées ;
- des variantes réellement distinctes ;
- des exercices compatibles avec la langue de la matière.

Pour l’Espagnol, il doit pouvoir générer notamment :

- vocabulaire ;
- conjugaison ;
- grammaire ;
- compréhension courte ;
- traduction encadrée ;
- phrases à compléter ;
- QCM ;
- production guidée courte ;

uniquement si ces formats sont supportés par le moteur de séance.

---

## 11. Répartition intelligente

Lorsque le parent demande un devoir sans sélectionner un chapitre précis, le système doit répartir les exercices selon :

- les faiblesses de l’élève ;
- les chapitres à réviser ;
- les devoirs à venir ;
- les prérequis ;
- la diversité ;
- les contenus réellement disponibles ;
- les objectifs du niveau.

Exemple pour 10 exercices :

```text
3 exercices sur une compétence fragile
2 exercices sur une compétence moyenne
2 exercices de consolidation
2 exercices de révision espacée
1 exercice de contrôle global
```

Cette répartition doit être calculée par les services métier, puis expliquée par le Professeur IA.

---

## 12. Rôle du Professeur IA

Le Professeur IA doit expliquer le complément de devoir.

Exemple :

> Le catalogue ne contenait que deux séries adaptées en Espagnol.  
> J’ai créé quatre exercices complémentaires pour travailler le vocabulaire,
> la conjugaison et la compréhension. Ton devoir contient maintenant six exercices.

Le Professeur IA ne doit pas :

- choisir librement une compétence inexistante ;
- inventer une note ;
- contourner la validation ;
- publier un exercice invalide ;
- modifier directement la progression.

---

## 13. Validation automatique maximale

La validation doit être effectuée au maximum par les moteurs automatiques et l’IA.

Chaque exercice généré doit passer :

1. validation du schéma ;
2. validation de la cible curriculum ;
3. validation du niveau ;
4. validation du type jouable ;
5. validation de la réponse attendue ;
6. contrôle des incohérences ;
7. contrôle des doublons ;
8. contrôle des quasi-doublons ;
9. contrôle de langue ;
10. contrôle de sécurité ;
11. contrôle de correction ;
12. validation finale de persistance.

L’IA doit corriger automatiquement un exercice invalide dans une boucle limitée.

Un contenu non réparable doit être rejeté et remplacé par une nouvelle génération.

---

## 14. Persistance

Les exercices générés doivent devenir des entités catalogue normales et réutilisables.

Ils doivent conserver :

- `source = ai_generated` ;
- fournisseur ;
- modèle ;
- prompt ;
- version du prompt ;
- date ;
- cible curriculum ;
- difficulté ;
- type ;
- hash ;
- résultat des validations ;
- identifiant du devoir d’origine ;
- `learner_id` d’origine lorsque la politique l’autorise ;
- statut de publication ou d’utilisation runtime.

Aucun exercice ne doit rester uniquement en mémoire de session.

---

## 15. Jouabilité immédiate

Les exercices générés doivent être :

- ajoutés au devoir courant ;
- affichés dans la séance ;
- répondables ;
- corrigibles ;
- historisés ;
- repris dans la progression ;
- réutilisables dans de futurs devoirs.

Aucun second lancement de création ne doit être nécessaire.

---

## 16. Déduplication et diversité

Le système doit empêcher :

- même `exercise_id` dans un devoir ;
- même énoncé ;
- même réponse avec simple reformulation ;
- génération répétée au rerun ;
- duplication lors d’un double clic ;
- répétition excessive entre deux devoirs récents.

Le contrôle doit utiliser :

- hash normalisé ;
- cible curriculum ;
- type ;
- réponse ;
- historique récent ;
- comparaison sémantique si déjà disponible.

---

## 17. Interface Parent

Lors de la création du devoir, afficher :

- nombre demandé ;
- nombre trouvé dans le catalogue ;
- nombre généré par IA ;
- nombre final ;
- matières et chapitres couverts ;
- message clair en cas de couverture limitée.

Exemple :

```text
Exercices demandés : 8
Exercices catalogue : 2
Exercices générés par IA : 6
Total du devoir : 8
```

Ne pas afficher une simple erreur « pas assez d’exercices ».

---

## 18. Interface Élève

L’élève doit voir un devoir normal.

L’origine IA peut être masquée ou affichée discrètement, mais ne doit pas modifier :

- le rendu ;
- la correction ;
- le score ;
- la progression ;
- l’historique.

---

## 19. Tableau de bord de couverture

Ajouter ou compléter un tableau de bord technique ou administrateur permettant de voir :

- couverture par classe ;
- couverture par matière ;
- couverture par chapitre ;
- nombre d’exercices ;
- nombre de variantes ;
- contenus catalogue ;
- contenus IA ;
- compétences sans exercice ;
- rubriques insuffisantes ;
- taux de génération ;
- taux de rejet ;
- taux de réutilisation.

Le cas **Espagnol 4e avec seulement 2 rubriques** doit être visible immédiatement dans ce tableau.

---

## 20. Configuration

Remplacer les flags trop spécifiques par une configuration générique, par exemple :

```env
HOMEWORK_AI_COMPLETION_ENABLED=true
HOMEWORK_AI_COMPLETION_GRADES=CM1,CM2,6E,5E,4E,3E
HOMEWORK_AI_COMPLETION_SUBJECTS=ALL
HOMEWORK_AI_MAX_GENERATED_PER_HOMEWORK=20
HOMEWORK_AI_MAX_REPAIR_ATTEMPTS=2
```

Les noms exacts doivent suivre les conventions existantes.

La configuration historique 4e doit rester compatible ou être migrée proprement.

---

## 21. Tests obligatoires

### Généralisation

1. génération en CM1 ;
2. génération en CM2 ;
3. génération en 6e ;
4. génération en 5e ;
5. génération en 4e ;
6. génération en 3e ;
7. génération en Mathématiques ;
8. génération en Français ;
9. génération en Anglais ;
10. génération en Espagnol.

### Espagnol 4e

11. catalogue avec seulement 2 rubriques ;
12. création d’un devoir de 6 exercices ;
13. génération uniquement des exercices manquants ;
14. variété réelle des exercices ;
15. langue espagnole correcte ;
16. correction disponible ;
17. exercice jouable ;
18. intégration immédiate au devoir ;
19. aucune seconde soumission ;
20. rapport de couverture signalant la faiblesse du catalogue.

### Robustesse

21. catalogue vide ;
22. catalogue partiel ;
23. type non jouable ;
24. génération invalide ;
25. réponse incohérente ;
26. doublon ;
27. quasi-doublon ;
28. timeout ;
29. absence de clé ;
30. fallback désactivé ;
31. double clic ;
32. rerun Streamlit ;
33. persistance échouée ;
34. création du devoir échouée après persistance.

### Sécurité

35. parent non lié ;
36. mauvais `learner_id` ;
37. accès inter-famille ;
38. secret absent des logs ;
39. prompt sans données inutiles ;
40. aucun appel direct LLM depuis l’UI.

### Régression

41. devoir catalogue classique ;
42. devoir mixte ;
43. devoir 100 % IA ;
44. correction ;
45. tentative ;
46. progression ;
47. tableau de bord ;
48. suite complète verte.

---

## 22. Auto-validation obligatoire par Cursor

Cursor doit :

- auditer le code ;
- identifier pourquoi l’Espagnol 4e n’affiche que 2 rubriques ;
- distinguer problème UI, filtre, contenu ou curriculum ;
- généraliser le fallback ;
- implémenter ;
- corriger automatiquement les anomalies ;
- exécuter les tests ciblés ;
- exécuter la suite complète ;
- exécuter Ruff ;
- exécuter Mypy ;
- exécuter compileall ;
- démarrer Streamlit ;
- simuler la création d’un devoir Espagnol 4e ;
- vérifier la jouabilité ;
- vérifier la progression ;
- produire le rapport final.

Ne pas demander à Francis d’effectuer une validation technique détaillée.

---

## 23. Rapport attendu

Créer :

```text
docs/phase3/LCAI-0018B_B6_IMPLEMENTATION_REPORT.md
```

Le rapport doit inclure :

- diagnostic des 2 rubriques Espagnol 4e ;
- cause réelle ;
- correction ;
- architecture réutilisée ;
- généralisation multi-niveaux ;
- généralisation multi-matières ;
- génération ;
- validation ;
- persistance ;
- jouabilité ;
- déduplication ;
- couverture ;
- fichiers créés ;
- fichiers modifiés ;
- tests ;
- qualité ;
- démarrage ;
- limites ;
- dette restante ;
- commit non effectué ;
- push non effectué ;
- verdict.

---

## 24. Critères d’acceptation

Le ticket est accepté lorsque :

- la création d’un devoir n’est plus limitée au catalogue ;
- le moteur génère automatiquement le déficit ;
- le mécanisme fonctionne pour toutes les classes et matières configurées ;
- le cas Espagnol 4e est corrigé ou clairement diagnostiqué ;
- un devoir peut être créé même avec seulement 2 rubriques disponibles ;
- les exercices générés sont validés ;
- ils sont persistés ;
- ils sont immédiatement jouables ;
- les réponses sont corrigées ;
- les tentatives sont historisées ;
- la progression est mise à jour ;
- aucun doublon n’est créé ;
- les tableaux de bord restent fonctionnels ;
- le mode sans IA reste stable ;
- la suite complète passe.

---

## 25. Instruction directe pour Cursor

```text
Implement LCAI-0018B6 completely.

Do not limit homework creation to exercises already stored in the database.

When the catalogue is insufficient, generate only the missing exercises through
the centralized AI generation service, validate them automatically, persist
them as normal catalogue entities and include them immediately in the current
homework.

Generalize the existing 4e fallback to all configured grades and subjects.

Audit the specific case where 4e Spanish exposes only two rubrics. Determine
whether the cause is UI filtering, missing placements, unpublished content,
incomplete imports or incomplete curriculum data. Fix the defect when it is an
implementation or data-placement issue. When the curriculum structure is truly
incomplete, report it explicitly but still create a complete homework using
valid existing curriculum targets.

Do not invent official curriculum entities silently.

Reuse the existing Learning Coach AI architecture, repositories, curriculum
services, homework services, AI gateway, validation pipeline, session engine,
correction engine, progression engine and learner_id authorization.

The generated exercises must be immediately playable, correctable, traceable,
deduplicated and reusable.

Perform the complete AI-driven technical validation yourself. Do not ask Francis
to review code, migrations, authorization, architecture or database internals.

Do not commit or push.
Do not commit data/*.duckdb.

Return the complete LCAI-0018B6 implementation report and a READY FOR REVIEW,
REQUIRES CORRECTION or BLOCKED verdict.
```
