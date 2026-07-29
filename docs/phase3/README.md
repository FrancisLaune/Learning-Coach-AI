# Phase 3 — Documentation Learning Coach AI

**Statut :** clôturée — jalon `Phase3_Completed` (2026-07-29)

Ce répertoire regroupe l’ensemble des livrables Phase 3 : audits, rapports d’implémentation, matrices de couverture, exports CSV et archives de spécifications.

## Jalon de clôture

| Document | Description |
|----------|-------------|
| [PHASE3_COMPLETION_MILESTONE.md](PHASE3_COMPLETION_MILESTONE.md) | Synthèse validation fonctionnelle, technique, CI et critères de clôture |

## Tickets Phase 3

| Ticket | Intitulé | Rapport principal |
|--------|----------|-------------------|
| LCAI-0015A | Authentification | [LCAI-0015A_AUTHENTICATION_COMPLETION_REPORT.md](LCAI-0015A_AUTHENTICATION_COMPLETION_REPORT.md) |
| LCAI-0015B | Gestion famille / élèves | [LCAI-0015B_PHASE0_AUDIT.md](LCAI-0015B_PHASE0_AUDIT.md) |
| LCAI-0017 | Professeur virtuel V1 | [LCAI-0017_VIRTUAL_TEACHER_V1_IMPLEMENTATION_REPORT.md](LCAI-0017_VIRTUAL_TEACHER_V1_IMPLEMENTATION_REPORT.md) |
| LCAI-0018 | Couverture devoirs 4e | [LCAI-0018_IMPLEMENTATION_REPORT.md](LCAI-0018_IMPLEMENTATION_REPORT.md) |
| LCAI-0018B | Fallback IA adaptatif 4e | [LCAI-0018B_IMPLEMENTATION_REPORT.md](LCAI-0018B_IMPLEMENTATION_REPORT.md) |

## Exports et matrices

- `exports/` — CSV de couverture, files de revue par matière, gaps par chapitre
- `LCAI-0018_*_COVERAGE_MATRIX.csv`, `LCAI-0018B_COVERAGE_MATRIX.csv` — matrices à la racine phase3

## Archive

Spécifications sources (docx) et extracts texte B4 :

- [archive/README.md](archive/README.md)
- `archive/specifications/` — documents Cursor / Francis
- `archive/extracted_b4/` — extracts Vol. 1–4 LCAI-0018B

## Scripts associés

| Script | Usage |
|--------|-------|
| `scripts/lcai_0018_phase0_audit.py` | Audit couverture devoirs 4e (LCAI-0018) |
| `scripts/lcai_0018b_phase0_baseline.py` | Baseline fallback IA (LCAI-0018B B0) |
| `scripts/reset_family_to_demo_parent.py` | Reset compte démo Parent/1234 |
