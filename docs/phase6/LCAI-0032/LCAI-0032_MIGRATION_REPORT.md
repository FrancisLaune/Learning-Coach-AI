# LCAI-0032 — Migration Report

## Étapes exécutées

1. Backup DuckDB + quarantaine WAL  
2. Migrations `brevet_content` 001–004  
3. Seed curriculum depuis `subjects/*.py` (chapitres → skills)  
4. Import SQLite 9+32 exercices (LEGACY_BANK, compat REVIEW)  
5. Import `exam_questions` DuckDB (45)  
6. Manifest annales 64 entrées + enregistrement `exam_archives_ref`  
7. Matérialisation couverture via générateurs banques (+ marqueurs ARCHIVE_DERIVED)

## Idempotence

Second `bootstrap_referential` : migrations `[]`, archives en doublons, contenu stable (~1978 items).

## Non recopié

- Historiques élèves (`practice_attempts`) non fusionnés dans le catalogue  
- EN/ES hors corpus terminal (subjects présents, continuous_assessment)
