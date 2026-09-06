# LCAI-0036 — Schema Changes

- `015_lcai_0036_pedagogical_validation.sql` : runs, assessments, history, playability/validation overrides
- `016_lcai_0036_views.sql` : `v_official_pedagogical_effective`, `v_pedagogical_review_queue`
- Pas de modification destructive des migrations 012–014
- Pas d'UPDATE massif des lignes `content_items` (contrainte DuckDB FK)
