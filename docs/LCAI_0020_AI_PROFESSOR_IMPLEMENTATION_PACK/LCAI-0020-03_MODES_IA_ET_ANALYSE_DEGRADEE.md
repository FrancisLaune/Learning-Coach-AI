# LCAI-0020-03 — Modes IA et analyse déterministe dégradée

## 1. Objet

Garantir que l’application reste pleinement exploitable lorsque le Professeur IA
est désactivé, non configuré, hors budget, en timeout ou indisponible.

Le mode sans IA ne doit pas être un mode vide. Il utilise les analyses
déterministes déjà présentes dans Learning Coach AI et les principes observés
dans l’application de révision fournie.

## 2. Modes de fonctionnement

### Mode A — Professeur IA actif

- synthèse narrative personnalisée ;
- accompagnement contextuel ;
- explication des résultats ;
- guidance progressive ;
- recommandations expliquées ;
- création de messages adaptés à l’élève.

Les faits, scores et décisions métier proviennent des services déterministes.

### Mode B — Professeur IA inactif

- Tableau de bord complet ;
- notes et historique ;
- progression ;
- maîtrise par matière et chapitre ;
- catégories de maîtrise ;
- recommandations basées sur règles ;
- devoirs et échéances ;
- fiches et séances de révision ;
- messages standards de coaching.

### Mode C — Professeur IA temporairement indisponible

Le système bascule automatiquement en Mode B sans erreur bloquante.

Un message discret peut indiquer :

> Le Professeur IA est temporairement indisponible. Les analyses et recommandations
> de base restent accessibles.

## 3. Analyses déterministes minimales

Les analyses sans LLM doivent calculer et afficher, selon les données disponibles :

- meilleure note ;
- dernière note ;
- moyenne ;
- évolution des notes ;
- nombre d’activités ;
- taux de réussite ;
- temps moyen ;
- difficulté moyenne ;
- progression par date ;
- maîtrise par matière ;
- maîtrise par chapitre ;
- compétences fortes ;
- compétences en cours d’acquisition ;
- compétences fragiles ;
- chapitres à réviser ;
- recommandations par règles.

## 4. Classification de maîtrise

La classification doit utiliser les conventions existantes du projet.

À défaut d’une convention déjà centralisée, les catégories fonctionnelles sont :

- **Très bien maîtrisé** ;
- **Bien maîtrisé** ;
- **Moyennement maîtrisé / en cours d’acquisition** ;
- **Peu maîtrisé / fragile** ;
- **À découvrir / données insuffisantes** ;
- **À réviser**.

Les seuils ne doivent pas être codés dans l’UI. Ils doivent être centralisés dans
un service ou une politique configurable.

## 5. Recommandations déterministes

Exemples de règles :

- réussite élevée et temps maîtrisé : proposer le niveau supérieur ;
- réussite correcte mais lente : travailler les automatismes ;
- erreurs fréquentes et réponses rapides : recommander de ralentir et relire ;
- réussite faible : reprendre la fiche puis une série guidée ;
- compétence non travaillée récemment : proposer une révision espacée ;
- devoir en retard : priorité au devoir ;
- échéance proche : préparation ciblée ;
- données insuffisantes : proposer un diagnostic court.

Ces règles doivent réutiliser ou adapter les services existants, notamment les
logiques de maîtrise et d’adaptation déjà développées.

## 6. Contrat de fallback

Chaque use case IA doit posséder une réponse déterministe de repli.

Exemples :

| Use case IA | Fallback déterministe |
|---|---|
| Accueil personnalisé | Mission du jour calculée par règles |
| Analyse d’un devoir | Résumé des scores, erreurs et compétences |
| Explication d’une note | Affichage des calculs et activités associées |
| Révision conseillée | Chapitre fragile + fiche + exercices disponibles |
| Message de motivation | Message standard selon progression |
| Plan de travail | Priorités calculées selon devoirs, fragilités et échéances |

## 7. Activation

Le mode doit être déterminé à partir d’une configuration centralisée, par exemple :

- feature flag Professeur IA ;
- configuration fournisseur valide ;
- autorisation du rôle ;
- budget disponible ;
- état du provider ;
- politique de sécurité.

L’UI ne décide pas seule du mode.

## 8. Critères d’acceptation

- l’application démarre sans clé LLM ;
- le Tableau de bord reste complet ;
- les notes et progressions restent visibles ;
- les catégories de maîtrise restent calculées ;
- les devoirs restent réalisables ;
- les révisions restent accessibles ;
- aucune page dépendante de l’IA ne devient vide ;
- un timeout provoque un fallback propre ;
- les tests couvrent les trois modes.
