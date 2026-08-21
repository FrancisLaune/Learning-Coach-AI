# LCAI-0030 — Réorientation produit : parcours élève

**Date :** 2026-08-21  
**Branche cible :** `develop`  
**Prérequis runtime actuel :** mode manuel / moteur Professeur IA désactivé (état de transition).

## Décisions figées

| Sujet | Décision |
|-------|----------|
| Cible utilisateur | L’élève (ou toute personne qui révise) |
| Rôle parent | Comptes uniquement : création / gestion du compte enfant |
| Professeur IA | **Supprimé** du parcours élève (bandeau décisionnel, modes Professeur/Compagnon, orchestration) |
| Remplacement interaction libre | **ChatGPT Voice** — intégration **la plus simple** (pas de Realtime custom, pas de clone ChatGPT) |
| Priorité de build | Lots **1 → 5** strictement dans cet ordre |
| Niveaux d’exercice (facile/moyen/difficile UI) | **Disparaissent** ; adaptation par résultats |
| Périmètre scolaire | CM1 → 3ᵉ, **toutes** les matières ; 3ᵉ ancrée sur corpus brevets déjà chargé |

## Les 9 intentions produit

1. Application centrée élève / révision.  
2. Fin du Professeur IA → ChatGPT Voice pour questions libres.  
3. Plus de « niveau d’exercice » fixe ; montée progressive selon résultats.  
4. Devoirs : pouvoir **passer** une question si bloqué.  
5. Notation robuste aux formats (`3,5` = `3.5`, équivalences usuelles).  
6. Aides réellement utiles (pas d’indices faibles / génériques).  
7. Couverture CM1–3ᵉ toutes matières + génération exercices/corrigés/explications + anti-répétition.  
8. Révisions 3ᵉ basées sur les brevets déjà en base.  
9. Tableau de bord simple et complet : évolution + matières/chapitres à travailler.

---

## Lot 1 — LCAI-0030-A — Socle élève + tableau de bord

**Objectifs (intentions 1, 9)**

- UX et navigation **élève-first** (le parent ne pilote pas le parcours pédagogique).
- Tableau de bord élève :
  - évolution globale (progression / régularité) ;
  - matières et chapitres **à travailler** (priorités claires) ;
  - lecture simple, sans jargon moteur IA.
- Retirer / masquer du parcours élève les éléments « Professeur IA » (bandeau orchestration, modes d’accompagnement, CTA « Discuter/Parler » liés au professeur virtuel). Les laisser en code mort temporaire (strangler) si besoin, sans les exposer.

**Hors scope Lot 1**

- ChatGPT Voice (Lot 5).  
- Refonte complète de la génération de contenu (Lot 4).

**Critères d’acceptation**

- [ ] Connexion élève → écran d’accueil compréhensible sans mode Professeur.  
- [ ] Dashboard affiche évolution + priorités matières/chapitres.  
- [ ] Parent peut toujours créer / gérer le compte enfant.  
- [ ] Aucun appel TTS/LLM bloquant sur l’accueil.

---

## Lot 2 — LCAI-0030-B — Devoirs : skip + notation tolérante

**Objectifs (intentions 4, 5)**

- Bouton / action **« Passer »** (ou équivalent) sur une question de devoir : l’élève n’est pas bloqué.
- Comportement skip à définir et journaliser (ex. : compte comme « passée », pas comme réussite ; n’empêche pas la suite du devoir).
- Moteur de correction :
  - décimales FR/EN (`3,5` / `3.5`) ;
  - espaces, signes, formes équivalentes usuelles (fractions simples, pourcentages si déjà supportés) ;
  - messages d’erreur clairs si format vraiment invalide.

**Critères d’acceptation**

- [ ] L’élève peut passer une question et continuer le devoir.  
- [ ] `3,5` accepté quand la réponse attendue est `3.5` (cas de référence + tests).  
- [ ] Pas de fausse erreur sur formats équivalents couverts par la matrice de tolérance.  
- [ ] Tests unitaires sur le correcteur (pas seulement UI).

---

## Lot 3 — LCAI-0030-C — Adaptation par résultats + aides utiles

**Objectifs (intentions 3, 6)**

- Supprimer le paramètre / filtre UI de **difficulté d’exercice** comme levier principal.
- Sélection / enchaînement d’exercices pilotés par **historique de réussite** (monter progressivement).
- Remplacer les aides faibles par :
  - indice progressif utile ;
  - rappel de notion court ;
  - corrigé expliqué (sans spoiler immédiat si l’élève veut encore essayer — règles UX à figer en ticket).

**Critères d’acceptation**

- [ ] Plus de choix « niveau d’exercice » obligatoire pour lancer une activité.  
- [ ] Après des réussites, les exercices proposés sont plus exigeants (preuve par tests ou scénario).  
- [ ] Après des échecs / skips, l’app propose du renforcement (pas la même question brute en boucle — lien Lot 4).  
- [ ] Au moins un type d’aide jugé « utile » par critère métier (exemple + piste, pas « réessaie »).

---

## Lot 4 — LCAI-0030-D — Couverture CM1→3ᵉ, anti-répétition, brevets

**Objectifs (intentions 7, 8)**

- Couvrir **toutes les matières** CM1 → 3ᵉ (catalogue + génération si stock insuffisant).
- Capacité à produire exercice + explication + corrigé (qualité type ChatGPT, via pipeline déjà existant / généralisé).
- **Anti-répétition** : ne pas resservir la même question / le même exercice à un élève dans une fenêtre définie.
- Pour la **3ᵉ** : s’appuyer sur le corpus **brevets** déjà chargé pour révisions et exercices.

**Critères d’acceptation**

- [x] Matrice CM1–3ᵉ × matières : disponible / générable / gap documenté.  
- [x] Génération avec corrigé + explication pour matières prioritaires du lot.  
- [x] Un exercice déjà vu n’est pas reproposé immédiatement (test).  
- [x] Parcours 3ᵉ peut cibler items issus des brevets chargés.

---

## Lot 5 — LCAI-0030-E — ChatGPT Voice (simple)

**Objectifs (intention 2)**

- Remplacer l’entrée « Professeur IA / Discuter / Parler » par un accès **ChatGPT Voice** le plus simple possible.

**Choix d’intégration (imposé : le plus simple)**

1. **Option retenue par défaut :** lien / bouton « Poser une question (ChatGPT) » ouvrant ChatGPT (web / app) dans un nouvel onglet, avec éventuellement un **prompt de contexte** prérempli (classe, matière, chapitre) via URL ou texte copiable.  
2. Pas de pipeline Realtime OpenAI custom dans ce lot.  
3. Pas de reconstruction du Professeur IA sous un autre nom.

**Critères d’acceptation**

- [x] Depuis le parcours élève, accès clair à ChatGPT pour questions libres.  
- [x] Aucune dépendance au bandeau / modes Professeur.  
- [x] Parent non requis pour cette interaction (l’élève lance seul).  
- [x] Message de cadre scolaire court affiché avant l’ouverture (rappel : questions de cours uniquement).

---

## Strangler / non-régression

- Ne pas supprimer d’un coup tout le code Professeur IA : **désactiver l’exposition UI** (Lot 1), puis retirer progressivement.  
- Ne pas modifier les schémas DuckDB hors tickets explicites.  
- Ne pas toucher aux curriculums hors périmètre d’un lot.  
- Validation technique IA (LCAI-0000A) en fin de chaque lot ; validation humaine = UX élève.

## Enchaînement

```text
0030-A (élève + dashboard)
    → 0030-B (skip + notation)
        → 0030-C (adaptation + aides)
            → 0030-D (contenu CM1–3ᵉ + brevets)
                → 0030-E (ChatGPT Voice simple)
```

## Prochaine action

Démarrer l’implémentation par **LCAI-0030-A** dès validation explicite de cette spec.
