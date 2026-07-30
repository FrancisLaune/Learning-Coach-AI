# LCAI-0020-02 — Professeur IA accompagnateur continu

## 1. Objet

Généraliser l’utilisation du Professeur IA existant afin qu’il devienne un
accompagnateur pédagogique continu de l’élève, sans transformer l’application
en simple chatbot et sans remplacer les écrans métier existants.

Le Professeur IA intervient :

- dès la connexion de l’élève ;
- sur le Tableau de bord ;
- dans la liste des devoirs ;
- avant le démarrage d’un devoir ;
- pendant la réalisation d’un devoir ;
- après chaque réponse lorsque cela est pertinent ;
- à la fin d’un devoir ;
- lors de l’analyse des résultats ;
- dans la préparation des révisions ;
- lors du choix d’une matière, d’un chapitre ou d’une compétence à travailler.

## 2. Invariant essentiel

Le Professeur IA est une couche d’accompagnement ajoutée à l’application.

Il ne remplace jamais :

- le Tableau de bord ;
- les devoirs ;
- les notes ;
- les analyses de progression ;
- les matières ;
- les chapitres ;
- les fiches de révision ;
- les services déterministes ;
- les moteurs de correction ;
- les données persistées.

## 3. Connexion de l’élève

Après authentification, le système construit une synthèse déterministe du
contexte de l’élève :

- devoirs à faire ;
- devoirs en retard ;
- devoirs récemment terminés ;
- dernières notes ;
- progression récente ;
- compétences fortes ;
- compétences moyennes ;
- compétences fragiles ;
- chapitres à réviser ;
- recommandations existantes ;
- temps de travail récent ;
- échéances connues.

### Professeur IA actif

Le Professeur IA produit un accueil court, personnalisé et actionnable.

Exemple :

> Bonjour Aleksandre. Tu as un devoir de mathématiques à terminer. Tes fractions
> progressent bien, mais les équations restent fragiles. Je te propose de commencer
> par ton devoir, puis de faire une révision courte de 10 minutes.

Il propose une seule priorité principale et au maximum deux actions secondaires.

### Professeur IA inactif ou indisponible

Le moteur déterministe affiche une synthèse standard :

- priorité du jour ;
- devoirs à faire ;
- dernière note ;
- chapitre le plus fragile ;
- proposition de révision basée sur des règles.

Aucun écran vide n’est autorisé.

## 4. Accompagnement des devoirs

### Avant le devoir

Le Professeur IA :

- présente l’objectif ;
- rappelle les chapitres concernés ;
- estime la durée à partir des données disponibles ;
- donne un conseil méthodologique court ;
- ne révèle aucune réponse.

### Pendant le devoir

Le Professeur IA fonctionne selon une progression d’aide :

1. reformulation de la consigne ;
2. rappel de la notion ;
3. indice ciblé ;
4. première étape ;
5. exemple analogue ;
6. solution guidée ;
7. correction complète uniquement si la politique du devoir l’autorise.

Il doit utiliser le contexte de l’exercice courant et les données réelles de
l’élève. Il ne modifie jamais la note, la réponse attendue ou le résultat
déterministe.

### Après une réponse

À partir du résultat calculé par le moteur métier, le Professeur IA peut :

- expliquer l’erreur ;
- identifier une confusion probable ;
- proposer une méthode ;
- donner un mini-exercice analogue ;
- encourager de manière factuelle ;
- proposer une révision ciblée.

### Fin du devoir

Il produit une synthèse structurée :

- résultat ;
- réussites ;
- difficultés observées ;
- erreurs récurrentes ;
- compétences concernées ;
- prochaine action recommandée ;
- niveau de confiance de l’analyse.

La note et les indicateurs restent calculés par les services déterministes.

## 5. Accompagnement des résultats

Le Professeur IA explique les données visibles dans les tableaux de bord :

- évolution des notes ;
- réussite par matière ;
- maîtrise par chapitre ;
- vitesse ;
- difficulté ;
- usage des indices ;
- régularité ;
- progression dans le temps.

Il distingue toujours :

1. les faits ;
2. l’interprétation ;
3. la recommandation.

Il ne formule pas de diagnostic psychologique, médical ou définitif.

## 6. Accompagnement des révisions

Le Professeur IA propose des révisions à partir de :

- compétences fragiles ;
- erreurs répétées ;
- prérequis ;
- temps depuis la dernière réussite ;
- échéances ;
- devoirs à venir ;
- disponibilité ;
- contenus réellement disponibles.

Il peut recommander :

- une fiche ;
- une série d’exercices ;
- un QCM ;
- une séance ciblée ;
- une révision espacée ;
- un parcours progressif.

La sélection finale des objets pédagogiques doit passer par les services métier.

## 7. Présence dans l’interface

Le Professeur IA peut être présenté sous forme :

- d’un panneau latéral ;
- d’une carte contextuelle ;
- d’un bouton « Demander au Professeur IA » ;
- d’un message de mission du jour ;
- d’un panneau d’aide dans une séance.

Sa présence ne doit pas supprimer ou masquer la navigation principale.

## 8. Mémoire

Le Professeur IA conserve uniquement les informations pédagogiques utiles et
autorisées :

- préférences d’explication ;
- niveau d’aide habituel ;
- erreurs récurrentes confirmées ;
- objectifs ;
- séances récentes ;
- recommandations précédentes.

Les faits durables restent dans les tables métier. Une synthèse LLM n’est jamais
la seule source d’une progression ou d’une difficulté.

## 9. Sécurité et pédagogie

- scoping strict par `learner_id` ;
- aucune exposition inter-famille ;
- aucune clé fournisseur dans l’UI ou les logs ;
- pas de solution immédiate lorsque le devoir impose un mode indice ;
- ton adapté à l’âge ;
- minimisation des données ;
- traçabilité de chaque appel ;
- mode dégradé disponible.
