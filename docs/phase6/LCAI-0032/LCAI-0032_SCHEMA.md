# LCAI-0032 — Schema

Migrations : `migrations/brevet_content/`

| Fichier | Contenu |
|---------|---------|
| `001_curriculum.sql` | curriculum_versions, subjects, domains, chapters, skills, subskills, prerequisites |
| `002_content_items.sql` | content_items, content_skill_links, content_assets, content_derivations |
| `003_archives.sql` | exam_archives_ref, sections, questions, import events |
| `004_coverage_view.sql` | `v_content_coverage` |

Curriculum code : **`FR_3E_DNB_2027_V1`**.

`content_items.source_type` : CURATED | LEGACY_BANK | OFFICIAL_ARCHIVE | ARCHIVE_DERIVED | AI_GENERATED | TEACHER_CREATED  

`usage_policy` : AVAILABLE_FOR_PRACTICE | RESERVED_FOR_MOCK | DERIVATION_ONLY  

`curriculum_2027_compatible` : TRUE | FALSE | REVIEW  

Runner : `services.brevet_referential.migrations.apply_brevet_content_migrations`
