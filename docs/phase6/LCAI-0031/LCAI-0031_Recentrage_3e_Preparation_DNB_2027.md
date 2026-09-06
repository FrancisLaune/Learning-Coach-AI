# LCAI-0031 — RECENTRAGE PRODUIT : 3e & PRÉPARATION AU DNB 2027

> **Numérotation :** ticket source téléchargé sous le nom LCAI-0022 ; renommé **LCAI-0031**
> (incrément après le dernier livré : LCAI-0030). L’ancien LCAI-0022 phase4 (Professeur IA) n’est pas concerné.

**Statut : READY FOR IMPLEMENTATION**  
**Priorité : P0 — STRUCTURANT / BLOQUANT POUR LA SUITE DU PROJET**  
**Type : Epic de recentrage fonctionnel, pédagogique, données, IA, UX et architecture**  
**Produit cible : Learning Coach AI — Objectif Brevet 2027**  
**Population cible : élèves scolarisés en classe de 3e préparant le DNB, série générale en priorité**

---

# 0. DÉCISION PRODUIT — NON NÉGOCIABLE

Learning Coach AI cesse d'être une plateforme scolaire généraliste couvrant CM1 → 3e.

À l'issue de ce ticket, le produit doit être conçu, présenté, paramétré, testé et exploité comme une plateforme spécialisée :

> **Classe de 3e + réussite scolaire annuelle + préparation intensive et adaptative au Diplôme National du Brevet.**

Le produit doit poursuivre deux objectifs simultanés :

1. **faire progresser l'élève pendant toute son année de 3e**, car le contrôle continu participe au DNB ;
2. **préparer spécifiquement les épreuves terminales du Brevet**, avec entraînements conformes aux formats réels, annales, sujets type Brevet, Brevets blancs, gestion du temps et préparation à l'oral.

Les anciens niveaux CM1, CM2, 6e, 5e et 4e ne constituent plus des parcours utilisateurs, des offres produit ou des niveaux sélectionnables.

Ils peuvent être conservés uniquement comme **socle interne de prérequis/remédiation**, lorsqu'une lacune antérieure empêche un élève de 3e de progresser.

---

# 1. CONTEXTE ET JUSTIFICATION

L'architecture actuelle de Learning Coach AI a progressivement accumulé :

- plusieurs niveaux scolaires ;
- plusieurs logiques de curriculum ;
- des exercices classés par niveau/difficulté ;
- des mécanismes de devoirs génériques ;
- des contenus qui ne contribuent pas directement à l'objectif Brevet ;
- des matières qui ne doivent pas nécessairement être traitées avec la même profondeur ;
- des écrans et services hérités d'une vision multi-niveaux.

Ce périmètre dilue :

- la qualité pédagogique ;
- la profondeur du référentiel ;
- la pertinence du Professeur IA ;
- la capacité à générer des devoirs réellement utiles ;
- la qualité des diagnostics ;
- la capacité à reproduire fidèlement les conditions du DNB ;
- les efforts de développement et de validation.

Le recentrage doit permettre de privilégier la **profondeur** à la largeur fonctionnelle.

---

# 2. ÉTAT CONSTATÉ DANS L'APPLICATION FOURNIE

L'archive `revision_3e.zip` confirme qu'une base historique "Objectif Brevet 2027" existe déjà.

Les éléments observés comprennent notamment :

- `app.py` avec le titre `Objectif Brevet 2027`;
- un référentiel DuckDB `objectif_brevet_2027.duckdb`;
- un moteur `core/engine.py`;
- un registre de matières `core/registry.py`;
- un tuteur IA `ai/revision_tutor.py`;
- des fonctions adaptatives dans `analytics/adaptive.py`;
- un calcul de maîtrise dans `analytics/mastery.py`;
- des modules de matières pour :
  - Français,
  - Mathématiques,
  - Histoire,
  - Géographie,
  - EMC,
  - Physique-Chimie,
  - SVT,
  - Technologie,
  - Anglais,
  - Espagnol ;
- une difficulté actuellement structurée autour de :
  - Facile,
  - Moyen,
  - Difficile,
  - Brevet,
  - Expert ;
- des devoirs dont la difficulté automatique intervient dans la constitution des questions ;
- des entraînements, fiches de révision, analyses et historiques.

Le recentrage ne doit donc pas créer une seconde application parallèle. Il doit **transformer et consolider l'existant**.

---

# 3. CADRE DNB CIBLE

## 3.1 Session cible

Le produit doit être configuré en priorité pour le **DNB session 2027**.

À partir de la session 2027, les sujets des épreuves écrites portent sur les programmes de la **classe de troisième**.

Cette règle doit devenir structurante dans le modèle de curriculum.

## 3.2 Épreuves terminales à couvrir

Pour un candidat scolaire, la préparation terminale doit couvrir :

### Français

- épreuve écrite ;
- durée : 3 h ;
- coefficient 2 ;
- compréhension/interprétation ;
- grammaire et compétences linguistiques ;
- dictée ;
- rédaction.

### Mathématiques

- épreuve écrite ;
- durée : 2 h ;
- coefficient 2 ;
- partie Automatismes sans calculatrice ;
- partie Raisonnement et résolution de problèmes ;
- qualité de rédaction et justification.

### Histoire-Géographie-EMC

- épreuve écrite ;
- durée : 2 h ;
- Histoire-Géographie coefficient 1,5 ;
- EMC coefficient 0,5 ;
- analyse de documents ;
- repères ;
- raisonnement ;
- développement construit ;
- compétences spécifiques EMC.

### Sciences

- épreuve écrite ;
- durée : 1 h ;
- coefficient 2 ;
- deux disciplines sont retenues parmi :
  - Physique-Chimie ;
  - SVT ;
  - Technologie.

**Conséquence produit importante :**
la plateforme doit préparer sérieusement les **trois disciplines scientifiques**, car l'élève ne doit pas dépendre d'une hypothèse sur les deux disciplines retenues le jour de l'épreuve.

### Oral

Le produit doit également intégrer la préparation à l'épreuve orale de soutenance :

- choix du sujet/projet ;
- structuration de la présentation ;
- problématique ;
- plan ;
- expression orale ;
- argumentation ;
- maîtrise du temps ;
- questions du jury ;
- simulation d'oral ;
- feedback IA.

---

# 4. CONTRÔLE CONTINU : NE PAS LE SUPPRIMER

Le recentrage sur les matières des épreuves terminales ne doit pas conduire à ignorer le contrôle continu.

Le DNB prend également en compte les résultats annuels de 3e.

Le produit doit donc distinguer deux périmètres.

## Périmètre A — Préparation Brevet intensive

Matières centrales :

- Français ;
- Mathématiques ;
- Histoire-Géographie ;
- EMC ;
- Physique-Chimie ;
- SVT ;
- Technologie ;
- Oral du DNB.

## Périmètre B — Pilotage contrôle continu

Le moteur peut enregistrer et suivre les moyennes de toutes les disciplines de 3e nécessaires à l'estimation du contrôle continu.

Les matières non terminales ne doivent cependant pas bénéficier, dans cette phase, du même moteur exhaustif de génération d'exercices que les matières DNB.

### Anglais / Espagnol

Pour un candidat scolaire standard :

- ne plus les présenter comme matières principales de préparation aux épreuves écrites terminales du DNB ;
- conserver la possibilité de saisir/suivre leurs moyennes pour le contrôle continu ;
- conserver leurs données historiques sans destruction ;
- ne pas les inclure par défaut dans les parcours "Révision Brevet", "Sujet Brevet" ou "Brevet blanc".

Prévoir une architecture permettant ultérieurement de traiter les candidats individuels sans polluer le parcours standard.

---

# 5. OBJECTIFS DU TICKET

Le ticket doit :

1. supprimer la logique produit multi-niveaux ;
2. imposer la classe de 3e comme niveau utilisateur cible ;
3. transformer le curriculum en curriculum 3e/DNB ;
4. définir explicitement les matières Brevet ;
5. distinguer contrôle continu et préparation terminale ;
6. adapter le moteur pédagogique ;
7. adapter le Professeur IA ;
8. adapter les devoirs ;
9. adapter les entraînements ;
10. adapter les diagnostics ;
11. adapter les fiches de révision ;
12. créer un vrai mode "Brevet" ;
13. créer un vrai mode "Brevet blanc" ;
14. préparer l'intégration des annales ;
15. permettre la génération IA de contenu conforme au DNB ;
16. conserver les anciens niveaux uniquement pour la remédiation ;
17. revoir les dashboards élève et parent ;
18. construire un indicateur de préparation au Brevet ;
19. garantir la traçabilité des recommandations ;
20. préserver les données existantes utiles.

---

# 6. PRINCIPES D'ARCHITECTURE

## PA-001 — Une seule cible utilisateur

Un élève actif est un élève de 3e.

Aucun sélecteur utilisateur ne doit proposer CM1, CM2, 6e, 5e ou 4e comme parcours principal.

## PA-002 — Les prérequis antérieurs restent internes

Une compétence antérieure peut être utilisée si elle explique une difficulté actuelle.

Exemple :

```text
Élève de 3e
→ échec sur Thalès
→ diagnostic
→ difficulté de proportionnalité
→ remédiation interne sur prérequis
→ retour à Thalès
```

L'UX doit rester centrée sur l'objectif 3e.

## PA-003 — Programme 3e comme référentiel canonique

Toutes les compétences cibles doivent être rattachées au programme de 3e et/ou à une compétence explicitement utile au DNB.

## PA-004 — Format d'épreuve comme objet métier

Un exercice ne doit plus seulement être caractérisé par matière/chapitre/difficulté.

Il doit pouvoir être caractérisé par son rôle DNB :

- automatisme ;
- compréhension ;
- dictée ;
- rédaction ;
- analyse documentaire ;
- développement construit ;
- problème ;
- raisonnement ;
- calcul ;
- justification ;
- tâche complexe ;
- sciences ;
- oral ;
- etc.

## PA-005 — Difficulté non bloquante

Conserver la décision du ticket LCAI-0021 :

> la difficulté est une métadonnée adaptative et non un filtre bloquant.

## PA-006 — IA en fallback et en enrichissement

Le référentiel est prioritaire.

L'IA génère lorsque :

- le contenu manque ;
- le stock nouveau est insuffisant ;
- une remédiation spécifique est nécessaire ;
- une variante est utile ;
- un entraînement personnalisé doit être créé.

Tout contenu généré doit être validé et persisté.

---

# 7. NOUVEAU MODÈLE DE MATIÈRES

Créer une configuration canonique, par exemple :

```python
DNB_TERMINAL_SUBJECTS = {
    "french",
    "mathematics",
    "history_geography",
    "emc",
    "physics_chemistry",
    "svt",
    "technology",
}

DNB_ORAL = "oral"

CONTINUOUS_ASSESSMENT_ONLY = {
    # disciplines suivies uniquement pour la moyenne annuelle
    # selon configuration de l'élève/établissement
}
```

Ne pas dupliquer Histoire et Géographie dans les règles d'épreuve si l'architecture peut les agréger sous un domaine `history_geography` tout en conservant les chapitres distincts.

---

# 8. NOUVEAU MODÈLE DE CURRICULUM

Hiérarchie cible :

```text
DNB 2027
└── Matière
    └── Domaine
        └── Chapitre 3e
            └── Compétence
                └── Sous-compétence
                    ├── Prérequis
                    ├── Attendu
                    ├── Format DNB
                    ├── Exercices
                    ├── Annales
                    └── Remédiations
```

Chaque compétence cible doit disposer, lorsque pertinent, de :

- identifiant stable ;
- matière ;
- chapitre ;
- description ;
- attendu de 3e ;
- importance DNB ;
- formats d'épreuve associés ;
- prérequis ;
- sous-compétences ;
- erreurs fréquentes ;
- stratégies de remédiation ;
- difficulté estimée ;
- exemples ;
- exercices ;
- questions d'annales liées ;
- capacité à être évaluée automatiquement ou non.

---

# 9. CLASSIFICATION "IMPORTANCE BREVET"

Ajouter une métadonnée permettant au moteur de prioriser les révisions :

```text
CRITICAL
HIGH
MEDIUM
LOW
```

Cette importance ne doit pas être arbitraire.

Elle doit être calculée ou administrée à partir de critères tels que :

- présence récurrente dans les sujets ;
- poids dans l'épreuve ;
- transversalité ;
- prérequis pour d'autres compétences ;
- faiblesse individuelle de l'élève ;
- proximité de l'examen.

---

# 10. PROFIL PÉDAGOGIQUE ÉLÈVE

Créer une représentation consolidée :

```python
StudentBrevetProfile
```

Elle doit contenir au minimum :

- élève ;
- classe = 3e ;
- date cible DNB ;
- série ;
- moyennes scolaires connues ;
- estimation contrôle continu ;
- résultats par matière ;
- maîtrise par compétence ;
- historique des erreurs ;
- vitesse ;
- autonomie ;
- utilisation des indices ;
- progression ;
- révisions dues ;
- sujets déjà réalisés ;
- annales déjà réalisées ;
- Brevets blancs ;
- estimation de préparation ;
- points forts ;
- points faibles ;
- risques ;
- recommandations ;
- historique des décisions IA.

---

# 11. DIAGNOSTIC INITIAL OBLIGATOIRE

Lors du démarrage du produit, l'élève doit passer un diagnostic.

Le diagnostic ne doit pas nécessairement tester toutes les compétences exhaustivement.

Il doit être adaptatif.

## Objectifs

- estimer rapidement le niveau ;
- identifier les lacunes critiques ;
- détecter les prérequis manquants ;
- construire le premier plan de travail ;
- éviter de faire perdre du temps sur des notions maîtrisées.

## Stratégie

```text
Question discriminante
→ réponse
→ mise à jour de confiance
→ question suivante choisie dynamiquement
→ arrêt lorsque confiance suffisante
```

## Sortie

Le diagnostic doit produire :

- maîtrise estimée par domaine ;
- confiance ;
- lacunes critiques ;
- remédiations ;
- niveau de difficulté cible ;
- plan des premières semaines ;
- score initial de préparation DNB.

---

# 12. PROFESSEUR IA — NOUVELLE MISSION

Le Professeur IA devient un **Coach Brevet de 3e**.

Il ne doit plus raisonner comme un assistant scolaire généraliste.

À chaque interaction, il doit connaître :

- la date ;
- le temps restant avant le DNB ;
- le profil de l'élève ;
- ses résultats ;
- son historique ;
- les compétences faibles ;
- les révisions dues ;
- les sujets déjà faits ;
- les erreurs récurrentes ;
- le temps de travail disponible.

## Responsabilités

Il doit pouvoir :

- construire un programme hebdomadaire ;
- proposer le prochain travail ;
- expliquer un cours ;
- créer une remédiation ;
- interroger l'élève ;
- adapter la difficulté ;
- proposer une annale ;
- déclencher un Brevet blanc ;
- analyser un Brevet blanc ;
- préparer l'oral ;
- motiver sans masquer les difficultés ;
- expliquer au parent les priorités.

---

# 13. PLANIFICATEUR JUSQU'AU BREVET

Créer un `BrevetStudyPlanner`.

Entrées :

- date actuelle ;
- date du DNB ;
- temps hebdomadaire ;
- maîtrise ;
- programme restant ;
- devoirs scolaires ;
- révisions espacées ;
- résultats aux annales ;
- résultats aux Brevets blancs.

Sortie :

- plan hebdomadaire ;
- objectifs ;
- priorités ;
- sessions recommandées ;
- dates de Brevets blancs ;
- révisions finales.

Le plan doit être recalculé après événement significatif.

---

# 14. MODES DE TRAVAIL

Le produit doit disposer au minimum des modes suivants.

## 14.1 Apprendre / Revoir un chapitre

Cours + exemples + exercices progressifs.

## 14.2 Entraînement ciblé

Une ou plusieurs compétences.

## 14.3 Devoir personnalisé

Panachage déterminé par le moteur.

## 14.4 Révision intelligente

Pilotée par répétition espacée et fragilité.

## 14.5 Sujet type Brevet

Respect du format de l'épreuve ciblée.

## 14.6 Annale

Sujet historique identifié, conservé comme tel.

## 14.7 Brevet blanc

Simulation multi-épreuves ou épreuve complète en conditions d'examen.

## 14.8 Oral

Préparation, simulation et feedback.

---

# 15. DEVOIRS PERSONNALISÉS

Intégrer LCAI-0021.

Le devoir personnalisé :

- ne filtre pas les exercices par difficulté ;
- prend tous les exercices compatibles ;
- privilégie ceux jamais vus ;
- mélange consolidation, niveau courant, difficulté supérieure et révision ;
- tient compte des faiblesses ;
- évite les doublons ;
- génère le déficit si nécessaire ;
- persiste les nouveaux exercices.

Le devoir doit être distinct d'un "Sujet Brevet".

Un devoir pédagogique peut être adaptatif.

Un Sujet Brevet doit respecter un format d'examen.

---

# 16. MODE SUJET BREVET

Créer une entité :

```python
BrevetExamTemplate
```

Elle décrit :

- matière ;
- durée ;
- sections ;
- types de questions ;
- contraintes ;
- barème ;
- calculatrice autorisée/interdite selon section ;
- nombre indicatif de questions ;
- règles de correction.

Le moteur doit pouvoir créer :

```python
build_brevet_exam(subject, student_profile, mode)
```

Modes :

- `OFFICIAL_ARCHIVE`
- `BREVET_STYLE`
- `ADAPTIVE_BREVET`
- `MOCK_EXAM`

`BREVET_STYLE` respecte le format mais peut utiliser du contenu généré.

`ADAPTIVE_BREVET` conserve l'esprit de l'épreuve mais cible les besoins de l'élève.

---

# 17. MATHÉMATIQUES — EXIGENCE SPÉCIFIQUE

Le moteur doit explicitement gérer :

## Partie 1 — Automatismes

- sans calculatrice ;
- temps dédié ;
- questions courtes ;
- mesure de vitesse ;
- précision ;
- automatismes variés.

## Partie 2 — Raisonnement / problèmes

- résolution ;
- justification ;
- rédaction ;
- raisonnement ;
- problèmes multi-étapes ;
- situations interdisciplinaires possibles.

Le système ne doit pas produire un faux "Brevet de maths" constitué uniquement de QCM courts.

---

# 18. FRANÇAIS — EXIGENCE SPÉCIFIQUE

Le mode Brevet doit gérer séparément :

- compréhension ;
- interprétation ;
- grammaire ;
- compétences linguistiques ;
- dictée ;
- rédaction.

La rédaction nécessite un moteur d'évaluation spécifique permettant :

- respect du sujet ;
- organisation ;
- cohérence ;
- argumentation/narration selon sujet ;
- syntaxe ;
- vocabulaire ;
- orthographe ;
- feedback détaillé.

Ne pas réduire la rédaction à une comparaison exacte de chaîne.

---

# 19. HISTOIRE-GÉOGRAPHIE-EMC

Le moteur doit gérer :

- repères ;
- chronologie ;
- cartes ;
- documents ;
- analyse documentaire ;
- développement construit ;
- vocabulaire ;
- argumentation ;
- EMC.

Prévoir l'évaluation de réponses longues.

Le module doit distinguer la performance Histoire-Géographie de la performance EMC pour refléter leur pondération respective.

---

# 20. SCIENCES

Préparer les trois matières :

- Physique-Chimie ;
- SVT ;
- Technologie.

Le moteur doit être capable de constituer une épreuve de sciences avec deux disciplines.

Il ne doit pas supprimer la troisième du parcours annuel.

Types de tâches :

- analyse de documents ;
- graphiques ;
- calculs ;
- raisonnement scientifique ;
- protocoles ;
- interprétation ;
- schémas ;
- argumentation.

---

# 21. ORAL DU BREVET

Créer un module fonctionnel dédié.

## Parcours

```text
Choisir sujet
→ définir problématique
→ construire plan
→ préparer support
→ préparer discours
→ répétition
→ chronométrage
→ simulation jury
→ questions
→ feedback
→ nouvelle simulation
```

## IA

Le Professeur IA doit pouvoir jouer le jury.

Il doit générer :

- questions simples ;
- questions de précision ;
- questions déstabilisantes mais pertinentes ;
- demandes de justification ;
- questions de recul personnel.

## Évaluation

Dimensions :

- structure ;
- clarté ;
- maîtrise du sujet ;
- argumentation ;
- vocabulaire ;
- posture/aisance si données disponibles ;
- gestion du temps ;
- qualité des réponses au jury.

---

# 22. ANNALES DNB

Créer un véritable référentiel d'annales.

Entités minimales :

```text
ExamArchive
ExamArchiveSection
ExamArchiveQuestion
ExamArchiveAnswer
ExamArchiveSkillLink
```

Métadonnées :

- année ;
- session ;
- zone/centre ;
- série ;
- matière ;
- durée ;
- sujet source ;
- corrigé source ;
- barème ;
- compétences ;
- chapitres ;
- difficulté observée ;
- statut de validation.

Une annale officielle doit rester identifiable comme contenu officiel/historique et ne jamais être confondue avec un exercice généré par IA.

---

# 23. OBJECTIF DE COUVERTURE DES ANNALES

Le système doit être conçu pour intégrer au minimum plusieurs années d'annales DNB et Brevets blancs de qualité.

Prévoir un import idempotent.

Le ticket ne doit pas imposer de scraping fragile dans le runtime.

Créer un pipeline d'ingestion séparé :

```text
Source
→ téléchargement/import
→ extraction
→ segmentation
→ classification
→ rattachement compétences
→ contrôle
→ publication référentiel
```

---

# 24. CONTENU GÉNÉRÉ PAR IA

Chaque contenu IA doit être marqué :

```text
source_type = AI_GENERATED
```

Métadonnées minimales :

- modèle ;
- version prompt ;
- date ;
- compétence ;
- difficulté ;
- format DNB ;
- fingerprint ;
- validation ;
- provenance ;
- demande à l'origine de la génération.

Avant publication :

1. validation structure ;
2. validation réponse/correction ;
3. cohérence programme 3e ;
4. cohérence compétence ;
5. détection doublon ;
6. jouabilité ;
7. validation de difficulté ;
8. contrôle du format DNB si revendiqué.

---

# 25. RÉFÉRENTIEL UNIQUE

Ne pas créer :

- un catalogue exercices ;
- un catalogue IA ;
- un catalogue Brevet séparé sans relations.

Créer un modèle cohérent avec provenance.

Exemple :

```text
content_item
  source_type:
    CURATED
    OFFICIAL_ARCHIVE
    AI_GENERATED
    TEACHER_CREATED
```

Les mêmes services de recherche doivent pouvoir interroger l'ensemble.

---

# 26. REMÉDIATION SUR NIVEAUX ANTÉRIEURS

Les anciens curricula ne doivent pas apparaître dans la navigation principale.

Créer la notion :

```python
PrerequisiteRemediation
```

Exemple :

```text
Compétence 3e : équations
↓
erreurs répétées
↓
diagnostic : manipulation des nombres relatifs fragile
↓
micro-remédiation
↓
test de sortie
↓
retour au programme de 3e
```

La remédiation doit être :

- courte ;
- ciblée ;
- mesurable ;
- automatiquement refermée lorsque le prérequis est restauré.

---

# 27. SCORE DE PRÉPARATION AU BREVET

Créer un indicateur :

```text
Brevet Readiness Score
```

Il ne doit pas être une simple moyenne.

Il doit intégrer :

- maîtrise des compétences ;
- couverture du programme ;
- stabilité des acquis ;
- résultats récents ;
- résultats en conditions Brevet ;
- gestion du temps ;
- compétences critiques non maîtrisées ;
- résultats aux Brevets blancs ;
- confiance statistique.

Exemple conceptuel :

```python
readiness = (
    mastery_component
    * coverage_component
    * stability_component
    * exam_performance_component
    * critical_gap_penalty
)
```

Les coefficients exacts doivent être configurables et documentés.

---

# 28. ESTIMATION DE NOTE DNB

Créer une estimation séparée du Readiness Score.

Elle peut utiliser :

- contrôle continu connu ;
- simulations terminales ;
- pondérations réglementaires ;
- incertitude.

Afficher une **fourchette**, pas une fausse précision.

Exemple :

```text
Projection actuelle : 12,5 – 14,0 / 20
Confiance : moyenne
Risque principal : Mathématiques — raisonnement
```

Le moteur doit expliquer les facteurs.

---

# 29. DASHBOARD ÉLÈVE

Page d'accueil cible :

1. compte à rebours avant le DNB ;
2. objectif de la semaine ;
3. prochaine session recommandée ;
4. progression programme ;
5. Readiness Score ;
6. matières fortes/faibles ;
7. révisions dues ;
8. prochain Brevet blanc ;
9. message du Professeur IA.

Éviter un dashboard surchargé de métriques techniques.

---

# 30. DASHBOARD PARENT

Le parent doit voir :

- régularité ;
- temps de travail ;
- progression ;
- maîtrise par matière ;
- points d'alerte ;
- projection DNB ;
- contrôle continu saisi ;
- Brevets blancs ;
- recommandations ;
- actions concrètes.

Le parent ne doit pas être exposé aux détails internes des algorithmes de difficulté.

---

# 31. CALENDRIER DNB 2027

Le système doit disposer d'une configuration versionnée des dates d'examen.

Pour la métropole, la session normale 2027 prévoit actuellement les écrits aux dates suivantes :

- Français : 24 juin 2027 ;
- Histoire-Géographie-EMC : 25 juin 2027 ;
- Sciences et Mathématiques : 28 juin 2027.

Ne pas coder ces dates en dur dans l'UI.

Créer une configuration versionnée :

```text
exam_calendar
exam_session
exam_date
timezone
source_reference
effective_from
```

Le planificateur utilise ces données.

---

# 32. UX — ÉLÉMENTS À SUPPRIMER OU MASQUER

Supprimer/masquer du parcours principal :

- sélection CM1 ;
- sélection CM2 ;
- sélection 6e ;
- sélection 5e ;
- sélection 4e ;
- concepts "changer de classe" hors 3e ;
- parcours multi-niveaux ;
- matières non DNB dans "Préparation Brevet".

Ne pas supprimer physiquement les données avant audit.

---

# 33. UX — NOUVELLE NAVIGATION CIBLE

Proposition :

```text
Accueil
Mon programme
Réviser
S'entraîner
Devoir personnalisé
Sujets Brevet
Brevets blancs
Oral
Mes résultats
Professeur IA
```

Parent :

```text
Vue générale
Progression
Résultats
Préparation Brevet
Contrôle continu
Alertes & recommandations
```

---

# 34. MODIFICATION DE `app.py`

L'implémentation actuelle contient des flux génériques.

Cursor doit auditer notamment :

- `automatic_difficulty()`;
- `practice_page()`;
- `new_exam_page()`;
- les sélecteurs `SUBJECTS`;
- les signatures de séries ;
- `build_question_set()`;
- les titres de devoirs ;
- les affichages de difficulté ;
- les dashboards ;
- les pages de fiches ;
- le menu étudiant.

La logique doit être extraite progressivement de l'UI.

**Interdiction :**
ajouter davantage de logique métier directement dans `app.py`.

---

# 35. REGISTRY DES MATIÈRES

`core/registry.py` doit devenir une source de configuration explicite ou déléguer à un service de curriculum.

Chaque matière doit porter des capacités :

```python
SubjectCapabilities(
    terminal_exam=True,
    continuous_assessment=True,
    supports_brevet_exam=True,
    supports_revision=True,
    supports_ai_generation=True,
    supports_long_answer=True,
    supports_oral=False,
)
```

---

# 36. DATABASE

L'actuelle base `objectif_brevet_2027.duckdb` doit être auditée avant migration.

Aucune migration destructive sans sauvegarde.

Créer des migrations additives.

Tables/objets à prévoir selon l'existant :

- curriculum_versions ;
- competencies ;
- subcompetencies ;
- prerequisites ;
- content_items ;
- content_skill_links ;
- exam_archives ;
- exam_templates ;
- student_competency_state ;
- revision_schedule ;
- diagnostic_sessions ;
- diagnostic_answers ;
- brevet_mock_exams ;
- brevet_readiness_snapshots ;
- continuous_assessment_marks ;
- ai_generation_audit ;
- pedagogical_decisions ;
- oral_projects ;
- oral_simulations.

Ne créer que ce qui n'existe pas déjà sous une forme réutilisable.

---

# 37. MIGRATION DES DONNÉES EXISTANTES

Classifier chaque donnée :

```text
KEEP
MIGRATE
ARCHIVE
DEPRECATE
DELETE_AFTER_VALIDATION
```

Par défaut :

- données élève : KEEP ;
- résultats : KEEP ;
- exercices 3e pertinents : MIGRATE ;
- contenus Brevet : MIGRATE ;
- contenus niveaux antérieurs : ARCHIVE/PREREQUISITE ;
- anglais/espagnol : conserver pour contrôle continu/historique mais retirer des parcours terminal DNB standard ;
- doublons : identifier avant suppression.

Produire un rapport de migration.

---

# 38. VERSIONNAGE CURRICULUM

Le curriculum doit être versionné.

Exemple :

```text
FR_3E_2027_V1
```

Chaque exercice doit pouvoir indiquer la version du curriculum à laquelle il a été validé.

Objectif :

- changement réglementaire ;
- session 2028 ;
- programme modifié ;
- conservation de l'historique.

---

# 39. MOTEUR DE SÉLECTION

Nouvelle pipeline :

```text
Objectif pédagogique
→ compétences cibles
→ candidats compatibles
→ exclusions strictes
→ scoring
→ diversité
→ historique élève
→ adaptation difficulté
→ sélection
→ déficit
→ génération IA
→ validation
→ persistance
```

La difficulté ne doit jamais être une exclusion stricte.

---

# 40. ALGORITHME DE PRIORISATION

Score indicatif :

```python
priority = (
    brevet_importance
    * mastery_gap
    * prerequisite_impact
    * revision_urgency
    * exam_frequency
    * confidence_factor
    * time_to_exam_factor
)
```

Le moteur doit pouvoir expliquer :

> "Cette compétence est prioritaire car elle est importante au Brevet, actuellement fragile et nécessaire pour trois autres compétences."

---

# 41. RÉPÉTITION ESPACÉE

La répétition espacée reste active.

Elle doit s'intégrer au plan Brevet.

Une révision peut être avancée lorsque :

- l'examen approche ;
- une compétence critique est fragile ;
- un Brevet blanc révèle une régression.

---

# 42. BREVETS BLANCS

Créer deux niveaux :

## Matière

Simulation complète d'une épreuve.

## Global

Ensemble planifié de plusieurs épreuves reproduisant autant que possible les contraintes réelles.

Chaque Brevet blanc produit :

- notes ;
- temps ;
- analyse ;
- compétences ;
- erreurs ;
- comparaison aux précédents ;
- plan de remédiation ;
- mise à jour Readiness.

---

# 43. GESTION DU TEMPS

Chaque exercice doit pouvoir avoir :

- temps cible ;
- temps observé ;
- ratio ;
- impact sur maîtrise.

Les modes Brevet doivent disposer d'un chronomètre.

En mode examen :

- pas de correction immédiate ;
- pas d'indice ;
- pas d'explication avant soumission ;
- navigation conforme à la stratégie définie ;
- correction après fin.

---

# 44. CORRECTION

Trois catégories :

## Correction déterministe

QCM, numérique, réponse courte contrôlée.

## Correction structurée

Réponse comportant plusieurs éléments attendus.

## Correction IA

Rédaction, développement construit, justification, oral.

Toute correction IA doit produire :

- score ;
- critères ;
- justification ;
- feedback ;
- confiance ;
- points à revoir.

---

# 45. OBSERVABILITÉ

Chaque décision pédagogique importante doit avoir :

```text
decision_id
student_id
timestamp
decision_type
inputs
rules_version
model_version
output
reason
confidence
```

Événements minimum :

- DiagnosticCompleted
- LearningPlanUpdated
- SkillMasteryUpdated
- RemediationStarted
- RemediationCompleted
- RevisionScheduled
- BrevetExamStarted
- BrevetExamCompleted
- MockExamCompleted
- ReadinessUpdated
- AIContentGenerated
- AIContentRejected
- PedagogicalRecommendationCreated

---

# 46. GARDE-FOUS IA

Le modèle IA ne doit pas pouvoir :

- inventer une règle réglementaire et la présenter comme certaine ;
- modifier le curriculum canonique ;
- déclarer une compétence maîtrisée sans preuve ;
- publier directement un exercice invalide ;
- modifier une note déterministe ;
- contourner les prérequis sans décision tracée ;
- confondre annale officielle et contenu généré.

---

# 47. CONFIGURATION, PAS DE HARD-CODE

Doivent être configurables :

- session DNB ;
- dates ;
- coefficients ;
- formats ;
- matières ;
- seuils de maîtrise ;
- poids de priorité ;
- stratégie de difficulté ;
- fréquence des Brevets blancs ;
- règles de génération ;
- limites de retry IA.

---

# 48. PERFORMANCE

Objectifs :

- affichage dashboard < 2 s sur dataset nominal local ;
- constitution d'un devoir depuis catalogue < 2 s hors appel IA ;
- absence d'appel IA si catalogue suffisant ;
- chargement paresseux des analyses lourdes ;
- index/requêtes DuckDB optimisés.

Les seuils exacts doivent être mesurés et documentés.

---

# 49. SÉCURITÉ ET DONNÉES MINEURS

Le produit traite des données scolaires de mineurs.

Minimiser :

- données personnelles ;
- logs contenant réponses libres ;
- exposition de données entre élèves.

Aucun prompt IA ne doit envoyer plus de données personnelles que nécessaire.

Prévoir anonymisation/pseudonymisation des identifiants transmis au fournisseur IA.

---

# 50. TESTS UNITAIRES OBLIGATOIRES

Créer des tests couvrant au minimum :

1. seul niveau utilisateur 3e ;
2. matières terminales correctes ;
3. anglais/espagnol exclus du parcours terminal standard ;
4. curriculum 3e chargé ;
5. prérequis antérieur utilisable en remédiation ;
6. difficulté non bloquante ;
7. génération IA sur déficit ;
8. persistance IA ;
9. déduplication ;
10. diagnostic adaptatif ;
11. priorité Brevet ;
12. répétition espacée ;
13. construction Sujet Brevet ;
14. Mathématiques automatismes ;
15. Français rédaction ;
16. HG/EMC ;
17. sciences 2/3 ;
18. Readiness ;
19. projection ;
20. calendrier versionné ;
21. idempotence.

---

# 51. TESTS D'INTÉGRATION

## TI-001 — Nouvel élève

```text
Création
→ diagnostic
→ profil
→ plan
→ première session
```

## TI-002 — Élève faible en maths

```text
Diagnostic
→ lacune 3e
→ prérequis antérieur
→ micro-remédiation
→ retour 3e
→ progression
```

## TI-003 — Devoir

```text
Demande
→ catalogue complet
→ panachage
→ génération déficit
→ sauvegarde
→ exécution
→ correction
```

## TI-004 — Sujet Brevet Maths

Doit produire les sections attendues, dont automatismes sans calculatrice.

## TI-005 — Annale

Doit conserver année, provenance et structure.

## TI-006 — Brevet blanc

Doit mettre à jour le profil et le plan.

## TI-007 — Oral

Création sujet → préparation → simulation → feedback.

---

# 52. TESTS DE NON-RÉGRESSION

Vérifier :

- login ;
- élèves existants ;
- historique ;
- devoirs ;
- entraînements ;
- fiches ;
- corrections ;
- statistiques ;
- base DuckDB ;
- migrations ;
- IA ;
- reprise de session ;
- reset/refaire un devoir ;
- tests existants.

---

# 53. TESTS DE DONNÉES

Produire des assertions :

- aucun exercice terminal n'est orphelin ;
- chaque exercice a une matière ;
- chaque exercice publié est jouable ;
- chaque exercice DNB est relié à une compétence ;
- chaque annale officielle a une provenance ;
- aucun contenu IA n'est marqué officiel ;
- aucun niveau antérieur n'apparaît comme parcours principal ;
- aucun doublon de fingerprint ;
- aucune FK logique cassée.

---

# 54. CRITÈRES D'ACCEPTATION — PRODUIT

Le ticket est accepté uniquement si :

- [ ] l'application est explicitement centrée 3e ;
- [ ] CM1→4e ne sont plus des parcours utilisateur ;
- [ ] les matières DNB structurent la préparation ;
- [ ] le contrôle continu reste pris en compte ;
- [ ] les langues ne polluent plus le parcours terminal standard ;
- [ ] le diagnostic initial fonctionne ;
- [ ] le Professeur IA agit comme Coach Brevet ;
- [ ] un plan jusqu'au DNB est calculé ;
- [ ] le moteur gère les prérequis antérieurs sans changer le niveau affiché ;
- [ ] les devoirs utilisent la stratégie LCAI-0021 ;
- [ ] les Sujets Brevet sont distincts des devoirs ;
- [ ] les annales sont modélisées ;
- [ ] les Brevets blancs sont modélisés ;
- [ ] l'oral est pris en charge ;
- [ ] un Readiness Score existe ;
- [ ] une projection DNB expliquée existe ;
- [ ] le calendrier est versionné ;
- [ ] les données existantes utiles sont préservées ;
- [ ] aucune migration destructive non validée ;
- [ ] tous les tests passent.

---

# 55. CRITÈRES D'ACCEPTATION — ARCHITECTURE

- [ ] aucune logique métier importante ajoutée directement à Streamlit ;
- [ ] services métier séparés ;
- [ ] repositories séparés ;
- [ ] configuration DNB versionnée ;
- [ ] décisions pédagogiques traçables ;
- [ ] génération IA auditable ;
- [ ] idempotence des générations ;
- [ ] migrations additives ;
- [ ] modèles compatibles avec évolution 2028 ;
- [ ] absence de duplication fonctionnelle avec les moteurs déjà existants.

---

# 56. LIVRABLES CURSOR OBLIGATOIRES

Cursor doit produire :

1. `LCAI-0031_IMPLEMENTATION_REPORT.md`
2. `LCAI-0031_ARCHITECTURE_DECISIONS.md`
3. `LCAI-0031_DATA_MIGRATION_REPORT.md`
4. `LCAI-0031_CURRICULUM_AUDIT.md`
5. `LCAI-0031_CONTENT_AUDIT.md`
6. `LCAI-0031_TEST_REPORT.md`
7. `LCAI-0031_NON_REGRESSION_REPORT.md`
8. `LCAI-0031_REMAINING_GAPS.md`

Le rapport final doit inclure :

- fichiers modifiés ;
- migrations ;
- tables ;
- nombre de contenus conservés ;
- nombre migré ;
- nombre archivé ;
- nombre rejeté ;
- couverture par matière ;
- couverture par compétence ;
- résultats tests ;
- limites ;
- dette restante.

---

# 57. ORDRE D'IMPLÉMENTATION IMPOSÉ

## Phase 0 — Audit

Avant modification :

- architecture ;
- DB ;
- curriculum ;
- matières ;
- contenus ;
- UI ;
- IA ;
- tests.

Créer sauvegarde DB.

## Phase 1 — Modèle cible

- configuration DNB ;
- curriculum version ;
- matières ;
- capacités ;
- modèles données.

## Phase 2 — Migration

- données 3e ;
- contenus ;
- prérequis ;
- langues ;
- historiques.

## Phase 3 — Moteur pédagogique

- diagnostic ;
- sélection ;
- priorisation ;
- remédiation ;
- planificateur.

## Phase 4 — Brevet

- templates ;
- annales ;
- sujets ;
- Brevets blancs ;
- oral.

## Phase 5 — Professeur IA

- contexte ;
- décisions ;
- génération ;
- feedback.

## Phase 6 — UX

- navigation ;
- dashboard ;
- pages ;
- suppression du multi-niveaux.

## Phase 7 — Validation

- tests ;
- non-régression ;
- audit DB ;
- smoke test.

---

# 58. INTERDICTIONS CURSOR

Cursor ne doit pas :

- réécrire tout le projet sans nécessité ;
- créer une V2 parallèle ;
- supprimer les données CM1→4e sans audit ;
- supprimer les langues de la DB ;
- confondre contrôle continu et épreuves terminales ;
- traiter l'anglais/espagnol comme épreuves terminales standard pour un candidat scolaire ;
- coder en dur toutes les règles DNB dans `app.py`;
- supprimer les métadonnées de difficulté ;
- filtrer les exercices par difficulté ;
- créer des exercices IA non persistés ;
- appeler l'IA si le catalogue suffit ;
- créer des annales "officielles" avec l'IA ;
- faire un commit ;
- faire un push.

---

# 59. COMMANDES DE VALIDATION

Cursor doit identifier l'environnement réel puis exécuter les commandes pertinentes.

Minimum attendu :

```bash
python -m compileall .
pytest -q
```

Si configurés :

```bash
ruff check .
mypy .
```

Ajouter :

- validation migrations ;
- audit DuckDB ;
- test de démarrage Streamlit ;
- tests du moteur ;
- tests DNB ;
- tests IA avec mocks ;
- tests d'idempotence.

---

# 60. SCÉNARIO DE RECETTE PRINCIPAL

Le ticket n'est pas terminé tant que ce scénario ne fonctionne pas :

```text
Un élève de 3e se connecte
→ l'application se présente comme Objectif Brevet
→ aucun choix CM1→4e n'est proposé
→ diagnostic initial
→ calcul des forces/faiblesses
→ calcul Readiness initial
→ création d'un plan jusqu'au DNB
→ Professeur IA propose le travail prioritaire
→ élève révise
→ réalise des exercices de difficulté panachée
→ moteur détecte une lacune de prérequis
→ micro-remédiation
→ retour au programme 3e
→ devoir personnalisé
→ contenu insuffisant
→ IA génère uniquement le déficit
→ nouveaux exercices validés et persistés
→ élève réalise un Sujet Brevet
→ correction conforme au type d'épreuve
→ Readiness recalculé
→ élève réalise un Brevet blanc
→ analyse des erreurs
→ plan automatiquement ajusté
→ parent voit progression, risques et projection
→ élève prépare l'oral
→ simulation avec Professeur IA
→ feedback
→ toutes les décisions sont auditables
```

---

# 61. DEFINITION OF DONE

**LCAI-0031 = DONE uniquement si le produit n'est plus une plateforme multi-niveaux ayant un "mode Brevet", mais une plateforme de 3e conçue nativement autour de la réussite au DNB.**

Le verdict final Cursor doit être exactement l'un des deux :

```text
READY FOR REVIEW
```

ou :

```text
NOT READY
```

Un verdict `READY FOR REVIEW` sans rapports, tests et preuves de migration est interdit.
