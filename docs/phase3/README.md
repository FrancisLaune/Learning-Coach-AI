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
| LCAI-0018 | Couverture devoirs 4e | [LCAI-0018_IMPLEMENTATION_REPORT.md](LCAI-0018_IMPLEMENTATION_REPORT.md) — [Inventaire global 0000A](LCAI-0000A_GLOBAL_CURRICULUM_VALIDATION_INVENTORY.md) |
| LCAI-0018B | Fallback IA adaptatif 4e | [LCAI-0018B_IMPLEMENTATION_REPORT.md](LCAI-0018B_IMPLEMENTATION_REPORT.md) — [Validation B4](LCAI-0018B_B4_VALIDATION_REPORT.md) — [B5 playability](LCAI-0018B_B5_IMPLEMENTATION_REPORT.md) |
| LCAI-0018C | Industrialisation CM1 | [LCAI-0018C.md](LCAI-0018C.md) — [Baseline C0](LCAI-0018C_PHASE0_BASELINE.md) — [Rapport](LCAI-0018C_IMPLEMENTATION_REPORT.md) |
| LCAI-0018D | Industrialisation CM2 | [LCAI-0018D.md](LCAI-0018D.md) — [Baseline C0](LCAI-0018D_PHASE0_BASELINE.md) — [Rapport](LCAI-0018D_IMPLEMENTATION_REPORT.md) |
| LCAI-0018E | Industrialisation 6e | [LCAI-0018E.md](LCAI-0018E.md) — [Baseline C0](LCAI-0018E_PHASE0_BASELINE.md) — [Rapport](LCAI-0018E_IMPLEMENTATION_REPORT.md) |
| LCAI-0018F | Industrialisation 5e | [LCAI-0018F.md](LCAI-0018F.md) — [Baseline C0](LCAI-0018F_PHASE0_BASELINE.md) — [Rapport](LCAI-0018F_IMPLEMENTATION_REPORT.md) |
| LCAI-0018G | Certification 3e | [LCAI-0018G.md](LCAI-0018G.md) — [Rapport](LCAI-0018G_IMPLEMENTATION_REPORT.md) |
| LCAI-0018H | Certification globale | [LCAI-0018H.md](LCAI-0018H.md) — [Rapport certification](LCAI-0018H_GLOBAL_CERTIFICATION_REPORT.md) — [Rapport](LCAI-0018H_IMPLEMENTATION_REPORT.md) |
| LCAI-0000A | Validation technique IA | [LCAI-0000A_AI_VALIDATION_FRAMEWORK.md](LCAI-0000A_AI_VALIDATION_FRAMEWORK.md) — [Statut curriculums](LCAI-0000A_CURRICULUM_VALIDATION_STATUS.md) — [Inventaire global](LCAI-0000A_GLOBAL_CURRICULUM_VALIDATION_INVENTORY.md) |

## Documentation Master Book

Volumes de référence Francis : [docs/Master/README.md](../Master/README.md)

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
