# Phase 4 — IA-First (Master Book IA)

**Statut :** ouverte  
**Référence fondatrice :** `docs/Master/MASTER BOOK IA .docx` (Volume IA-First + annexes Tech / UX / Data / Security / Voice+ / Next / Pro)  
**Principe :** le Professeur IA orchestre ; les moteurs pédagogiques existants exécutent. Pas de big-bang, strangler pattern uniquement.

## Lot 0 (terminé)

| Document | Description |
|----------|-------------|
| [LCAI-0022_LOT0_GAP_ANALYSIS_MASTER_BOOK_IA.md](LCAI-0022_LOT0_GAP_ANALYSIS_MASTER_BOOK_IA.md) | Cartographie Master Book ↔ code, écarts, backlog Phase A |

## Lot 1 (terminé)

| Document | Description |
|----------|-------------|
| [LCAI-0022A_LOT1_IMPLEMENTATION_REPORT.md](LCAI-0022A_LOT1_IMPLEMENTATION_REPORT.md) | Orchestrateur Professeur IA Core |

## Lot 2 (terminé)

| Document | Description |
|----------|-------------|
| [LCAI-0022B_LOT2_IMPLEMENTATION_REPORT.md](LCAI-0022B_LOT2_IMPLEMENTATION_REPORT.md) | Bandeau Professeur IA + modes |

## Lot 3 (terminé)

| Document | Description |
|----------|-------------|
| [LCAI-0022C_LOT3_IMPLEMENTATION_REPORT.md](LCAI-0022C_LOT3_IMPLEMENTATION_REPORT.md) | Cycle Accueil → Diagnostic → Devoir → Séance → Synthèse |

## Lot 4 (terminé)

| Document | Description |
|----------|-------------|
| [LCAI-0022D_LOT4_IMPLEMENTATION_REPORT.md](LCAI-0022D_LOT4_IMPLEMENTATION_REPORT.md) | Invariants IA + journal `ai_decision_log` |

## Backlog proposé (à formaliser en tickets)

| Lot | Intitulé | Statut |
|-----|----------|--------|
| 0 | Gap analysis Master Book ↔ code | Fait |
| 1 | Orchestrateur Professeur IA Core | Fait |
| 2 | Bandeau Professeur IA + modes (IA / Compagnon / Manuel) | Fait |
| 3 | Cycle Accueil → Diagnostic → Devoir → Séance → Synthèse | Fait |
| 4 | Invariants IA + journal de décisions | Fait |
| 5 | Sécurité mineurs renforcée (filtre scolaire central) | Planifié |
| 6 | Mode vocal scolaire sécurisé (STT → filtre → TTS) | Planifié Phase B |

## Règles Phase 4

- Réutiliser `services/virtual_teacher`, `pedagogical_intelligence`, `student_guidance`, `homework`, `learning_session`, `learning`, `recommendation`, `content`, `curriculum`.
- Pas de second référentiel DuckDB ni de second Content Factory.
- Contenu généré = Draft jusqu’à validation humaine.
- Migrations additives uniquement.
- Commit / push uniquement sur demande explicite.
- Validation technique IA : `python scripts/lcai_0000a_technical_validation.py --ticket <ID>`.

## Lien Phase 3

La Phase 3 est clôturée (`docs/phase3/PHASE3_COMPLETION_MILESTONE.md`). La Phase 4 s’appuie sur les livrables 0015–0021 (auth, famille, Professeur virtuel V1, devoirs, PI, guidance, sélection sans filtre difficulté).
