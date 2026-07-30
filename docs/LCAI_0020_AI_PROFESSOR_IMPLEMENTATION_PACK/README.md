# LCAI-0020 — Pack d’implémentation Professeur IA accompagnateur

Ce pack complète le Master Book Volume 4 sans le remplacer.

Il ne redéfinit pas l’architecture générale. Il précise uniquement la généralisation
du Professeur IA dans le parcours élève et garantit le maintien permanent du
« Tableau de bord ».

## Documents

1. `LCAI-0020-02_PROFESSEUR_IA_ACCOMPAGNATEUR_CONTINU.md`
2. `LCAI-0020-03_MODES_IA_ET_ANALYSE_DEGRADEE.md`
3. `LCAI-0020-04_TABLEAU_DE_BORD_ELEVE_INVARIANTS.md`
4. `LCAI-0020-05_TICKET_CURSOR_IMPLEMENTATION.md`

## Références obligatoires

- Master Book Volume 4 — Architecture IA, Professeur IA, LLM, RAG, Prompts, Mémoire et Analytics.
- Architecture existante Learning Coach AI.
- Flux de révision et d’analyse de l’application `revision.zip`.
- Services métier, repositories, authentification et `learner_id` existants.

## Principe produit

Le Professeur IA accompagne l’élève dès sa connexion, pendant ses devoirs,
après les résultats et dans les révisions.

Le menu « Tableau de bord » reste toujours présent et accessible, que le
Professeur IA soit actif, inactif ou indisponible.
