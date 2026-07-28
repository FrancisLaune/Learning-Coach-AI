# LCAI-0013B — DNB 2026 Mathematics Question Index V1

## Status
Preparation only. No DuckDB modification.

## Scope
Two official 2026 general-series Mathematics papers have been decomposed at training-index level:

- Asia — `26GENMATAA1`
- Antilles-Guyane — `26GENMATAG1`

Both use the 2026 format:
- 20 minutes of automatismes, calculator prohibited, 6 points;
- 1 h 40 of reasoning/problem solving, calculator allowed, 14 points.

## Inventory
- Papers: **2**
- Automatism items indexed: **19**
- Reasoning exercises indexed: **7**
- Reasoning question slots represented: **35**

## Pedagogical domains already visible
The two papers jointly exercise:
- numbers and calculation;
- algebra and equations;
- proportionality, percentages and speed;
- statistics and probability;
- geometry and measures;
- functions and graphical interpretation;
- spreadsheet use;
- algorithmics / Scratch.

## Mapping policy
This V1 intentionally stores `skill_hint` values rather than inventing exact LCAI-0011C Skill identifiers.

Exact `chapter_code` and `primary_skill_code` must be resolved against the project curriculum before import. Mapping confidence and human-review status will then be persisted.

## Exam-object model
`Exam → Part → Exercise/Automatism → Question → Skill mapping → Attempt → Evidence → Remediation`

## Important
Figures, graphs and Scratch blocks are first-class dependencies. Questions requiring them are marked `requires_figure=true`; they must not be converted into text-only exercises that lose necessary evidence.

## Next
1. Add other official 2026 zones.
2. Add 2025 and 2024 Mathematics papers.
3. Resolve exact 3e Skills after the LCAI-0012D/0012E integration baseline is stable.
4. Add corrections/barème metadata where authoritative sources exist.
5. Then expand to French, HG-EMC and Sciences.
