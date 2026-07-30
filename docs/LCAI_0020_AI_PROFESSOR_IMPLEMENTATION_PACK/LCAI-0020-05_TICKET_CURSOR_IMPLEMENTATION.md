# LCAI-0020-05 — Généralisation du Professeur IA dans le parcours Élève

## Statut

READY FOR IMPLEMENTATION

## Contexte

Le Master Book Volume 4 définit déjà l’architecture IA de référence. Ce ticket
ne demande pas une nouvelle architecture globale.

L’objectif est d’intégrer le Professeur IA existant comme accompagnateur
permanent du parcours Élève, tout en maintenant un fonctionnement déterministe
complet lorsque l’IA est inactive ou indisponible.

L’application de révision fournie sert de référence fonctionnelle pour :

- le Tableau de bord ;
- les notes ;
- l’évolution ;
- la maîtrise des chapitres ;
- l’analyse et progression ;
- les recommandations déterministes ;
- les états « bien maîtrisé », « moyen », « fragile » et « à réviser ».

## Objectifs

1. Déclencher un accompagnement pédagogique dès la connexion.
2. Guider l’élève dans ses devoirs sans fournir immédiatement les réponses.
3. Expliquer les résultats calculés par les moteurs métier.
4. Proposer des révisions ciblées.
5. Généraliser le Professeur IA sur les pages pertinentes.
6. Maintenir le Tableau de bord comme entrée permanente.
7. Garantir un mode sans IA complet et non bloquant.

## Contraintes impératives

- respecter le Master Book ;
- réutiliser le Professor IA Orchestrator existant ;
- aucun appel LLM direct depuis Streamlit ;
- aucune logique de score ou de mastery dans l’UI ;
- utiliser les services et repositories existants ;
- utiliser `learner_id` comme portée canonique ;
- préserver l’isolation inter-famille ;
- conserver les corrections déterministes ;
- ne jamais faire du LLM la source de vérité des notes ou de la progression ;
- ne pas créer un second Tableau de bord ;
- ne pas supprimer « Tableau de bord » de la navigation ;
- ne pas commit/push avant autorisation explicite ;
- ne pas committer `data/*.duckdb`.

## Parcours à implémenter

### A. Après connexion

Construire un `StudentHomeContext` déterministe contenant :

- devoirs ;
- échéances ;
- notes ;
- progression ;
- maîtrise ;
- chapitres fragiles ;
- révisions ;
- activité récente.

Si l’IA est active, produire un `AIWelcomeGuidance`.
Sinon produire un `DeterministicWelcomeGuidance`.

### B. Tableau de bord

Conserver une page structurée et indépendante avec :

- synthèse ;
- devoirs ;
- notes ;
- progression ;
- matières ;
- chapitres ;
- catégories de maîtrise ;
- éléments à réviser ;
- actions recommandées.

Ajouter une carte Professeur IA sans remplacer les données.

### C. Devoir

Avant :
- objectif ;
- durée ;
- conseil.

Pendant :
- reformulation ;
- rappel ;
- indice ;
- première étape ;
- exemple analogue ;
- solution guidée selon politique.

Après :
- synthèse ;
- forces ;
- erreurs ;
- recommandation ;
- révision.

### D. Résultats

Le LLM reçoit uniquement les résultats déterministes et le contexte autorisé.
Il explique, mais ne recalcule ni ne modifie les notes.

### E. Révision

Proposer une matière, un chapitre, une compétence et une activité réellement
disponible. La sélection passe par les services métier.

## DTO attendus

Adapter les modèles existants si possible. Ne pas créer de doublons.

DTO fonctionnels suggérés :

- `StudentHomeContext`
- `StudentDashboardSnapshot`
- `MasteryBand`
- `RevisionPriority`
- `HomeworkGuidanceContext`
- `HomeworkGuidanceResponse`
- `ResultExplanationContext`
- `RevisionGuidanceContext`
- `AIAvailability`
- `GuidanceSource` (`AI` ou `DETERMINISTIC`)

## Service de façade attendu

Créer ou adapter une façade applicative du type :

```python
class StudentGuidanceService:
    def build_home_guidance(self, actor, learner_id): ...
    def build_dashboard_snapshot(self, actor, learner_id): ...
    def prepare_homework_guidance(self, actor, learner_id, homework_id): ...
    def guide_current_exercise(self, actor, learner_id, session_id, exercise_id, help_level): ...
    def explain_homework_result(self, actor, learner_id, homework_id): ...
    def recommend_revision(self, actor, learner_id): ...
```

Cette façade :

- autorise ;
- appelle les services métier ;
- construit le contexte ;
- sélectionne le mode IA ou déterministe ;
- appelle l’orchestrateur IA lorsque permis ;
- applique le fallback ;
- trace ;
- retourne un DTO prêt pour l’UI.

## Mode déterministe

Réutiliser les moteurs actuels de progression et de maîtrise.

Centraliser les seuils et règles hors UI.

Le fallback doit fournir :

- mission du jour ;
- catégories de maîtrise ;
- devoir prioritaire ;
- chapitre à réviser ;
- recommandation ;
- messages standards.

## Modifications UI attendues

- conserver « Tableau de bord » dans la navigation Élève ;
- ajouter le message du Professeur IA dans une carte dédiée ;
- ajouter un accès contextuel dans les devoirs ;
- ajouter une explication post-résultat ;
- ajouter une action de révision ciblée ;
- afficher clairement le mode dégradé sans bloquer le parcours ;
- empêcher les doubles soumissions Streamlit ;
- conserver les deep-links vers devoirs et révisions.

## Tests obligatoires

### Navigation

1. Tableau de bord visible avec IA active.
2. Tableau de bord visible avec IA inactive.
3. Tableau de bord visible sans clé fournisseur.
4. Retour au Tableau de bord depuis un devoir.
5. Aucun menu supprimé par un feature flag IA.

### Connexion

6. Synthèse IA lorsque disponible.
7. Synthèse déterministe lorsque désactivée.
8. Synthèse déterministe sur timeout.
9. Priorité basée sur les données réelles.
10. Aucun accès à un autre learner.

### Devoirs

11. Conseil avant devoir.
12. Indice progressif pendant devoir.
13. Pas de solution immédiate en mode indice.
14. Résultat expliqué après correction déterministe.
15. Aucun changement de note par le LLM.
16. Reprise de séance sans duplication.

### Tableau de bord

17. Notes visibles.
18. Progression visible.
19. Matières visibles.
20. Chapitres visibles.
21. Catégories de maîtrise visibles.
22. Chapitres à réviser visibles.
23. Données insuffisantes gérées sans invention.
24. Recommandations fonctionnelles sans IA.

### Révision

25. Proposition ciblée avec IA.
26. Proposition déterministe sans IA.
27. Activité proposée réellement disponible.
28. Respect des prérequis.
29. Traçabilité de la raison.

### Robustesse et sécurité

30. Timeout fournisseur.
31. Réponse invalide.
32. Budget dépassé.
33. Feature flag désactivé.
34. Clé absente.
35. isolation Parent/Élève.
36. scoping strict `learner_id`.
37. aucun secret dans les logs.
38. aucun appel fournisseur direct depuis l’UI.

### Régression

39. devoirs existants fonctionnels.
40. notes existantes inchangées.
41. analytics existants inchangés.
42. révisions existantes fonctionnelles.
43. suite complète verte.

## Auto-validation IA obligatoire

Cursor réalise lui-même :

- audit du code ;
- implémentation ;
- auto-revue ;
- corrections ;
- tests ciblés ;
- tests complets ;
- Ruff ;
- Mypy ;
- compileall ;
- démarrage Streamlit ;
- tests de services simulant les parcours Parent et Élève ;
- vérification des migrations ;
- contrôle de sécurité ;
- rapport final.

Ne demander à Francis qu’une validation fonctionnelle simple de l’expérience
visible. Ne pas lui demander de contrôler l’architecture, la base, les migrations,
les autorisations ou le code.

## Rapport attendu

Retourner :

- statut ;
- audit de l’existant ;
- architecture réutilisée ;
- fichiers créés/modifiés ;
- flux connexion ;
- flux devoir ;
- flux résultats ;
- flux révision ;
- comportement IA actif ;
- comportement IA inactif ;
- Tableau de bord préservé ;
- tests ciblés ;
- tests complets ;
- Ruff ;
- Mypy ;
- compileall ;
- démarrage ;
- limites ;
- blocages ;
- commit non effectué ;
- push non effectué ;
- verdict READY FOR REVIEW / REQUIRES CORRECTION / BLOCKED.

## Critères d’acceptation finaux

- Professeur IA présent dès la connexion lorsqu’il est actif.
- Guidance disponible avant, pendant et après les devoirs.
- Résultats expliqués à partir de faits déterministes.
- Révisions ciblées proposées.
- Tableau de bord toujours présent.
- Notes, progression, matières et chapitres toujours visibles.
- Catégories de maîtrise et éléments à réviser visibles.
- Mode sans IA pleinement fonctionnel.
- Aucune dépendance bloquante à un fournisseur.
- Aucun appel direct LLM dans l’UI.
- Aucune régression.
