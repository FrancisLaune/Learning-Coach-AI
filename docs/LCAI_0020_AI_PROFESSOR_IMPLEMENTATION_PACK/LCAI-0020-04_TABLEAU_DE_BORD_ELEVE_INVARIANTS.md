# LCAI-0020-04 — Tableau de bord Élève : invariants fonctionnels

## 1. Règle absolue

L’option **« Tableau de bord » doit toujours être présente dans la navigation
Élève**.

Elle ne doit jamais être :

- remplacée par le Professeur IA ;
- supprimée lorsque l’IA est active ;
- masquée en cas d’erreur fournisseur ;
- conditionnée à une clé API ;
- conditionnée à un nombre minimal de données ;
- fusionnée dans un chat sans accès direct aux indicateurs.

## 2. Finalité

Le Tableau de bord permet à l’élève de vérifier de manière autonome :

- sa progression ;
- ses notes ;
- l’évolution de ses résultats ;
- ses devoirs ;
- les matières travaillées ;
- les chapitres connus ;
- les chapitres bien maîtrisés ;
- les chapitres moyennement maîtrisés ;
- les chapitres fragiles ou non maîtrisés ;
- les chapitres à réviser ;
- les recommandations ;
- ses prochaines actions.

## 3. Sections minimales

### 3.1 Synthèse

- dernière note ;
- moyenne ;
- meilleure note ;
- taux de réussite ;
- activités récentes ;
- temps de travail ;
- mission ou priorité du jour.

### 3.2 Devoirs

- à faire ;
- en cours ;
- terminés ;
- en retard ;
- prochaine échéance.

### 3.3 Progression

- courbe d’évolution des notes ;
- courbe de progression ;
- évolution par matière ;
- historique récent.

### 3.4 Matières et chapitres

Pour chaque matière :

- score global ;
- nombre d’activités ;
- état de maîtrise ;
- chapitres ;
- compétences ;
- dernière activité ;
- recommandation.

### 3.5 Catégories de maîtrise

Affichage lisible des groupes :

- très bien maîtrisé ;
- bien maîtrisé ;
- moyen / en cours d’acquisition ;
- fragile / peu maîtrisé ;
- à réviser ;
- non encore évalué.

### 3.6 Révisions recommandées

- matière ;
- chapitre ;
- compétence ;
- raison ;
- priorité ;
- durée estimée ;
- action disponible.

## 4. Interaction avec le Professeur IA

### IA active

Le Tableau de bord conserve toutes les données structurées et ajoute :

- un message du Professeur IA ;
- une explication de la priorité ;
- une synthèse narrative ;
- un bouton pour demander une explication ;
- un accompagnement vers le devoir ou la révision.

### IA inactive

Le Tableau de bord affiche :

- les mêmes indicateurs ;
- les mêmes notes ;
- les mêmes catégories de maîtrise ;
- les mêmes accès aux devoirs et révisions ;
- des recommandations déterministes ;
- des messages standards.

## 5. Aucun écran vide

Lorsque les données sont insuffisantes :

- afficher clairement « données insuffisantes » ;
- expliquer comment obtenir une première analyse ;
- proposer un diagnostic ou une activité courte ;
- ne pas inventer un niveau de maîtrise ;
- ne pas masquer les matières ou les chapitres disponibles.

## 6. Navigation attendue

La navigation Élève conserve au minimum :

1. Tableau de bord
2. Mes devoirs et mes notes
3. Analyse et progression
4. Révisions / fiches
5. Professeur IA ou accès contextuel au Professeur IA

Le nom exact peut suivre l’interface existante, mais le Tableau de bord reste
une entrée indépendante.

## 7. Critères d’acceptation

- le menu Tableau de bord est visible dans tous les modes ;
- un élève peut y revenir depuis toute page ;
- l’activation IA ne modifie pas les données affichées ;
- la désactivation IA ne retire aucun indicateur métier ;
- les états de maîtrise sont visibles par matière et chapitre ;
- les chapitres à réviser sont identifiables ;
- les notes et leur évolution sont accessibles ;
- les liens vers devoirs et révisions fonctionnent ;
- les autorisations reposent sur le `learner_id` connecté.
