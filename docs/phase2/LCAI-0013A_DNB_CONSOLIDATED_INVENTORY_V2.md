# LCAI-0013A — DNB Official Library — Consolidated Inventory V2

## Scope
Série générale, Français, Mathématiques, Histoire-Géographie-EMC et Sciences.

## Sessions
- Official Eduscol core: 2018–2026.
- 2020 is exceptional and must not be treated as a normal June written session.
- 2016–2017 require a separately documented reliable archive layer.
- 2026 is retained as a distinct format reference.
- Historical annals require compatibility tagging for preparation toward the 2027 DNB.

## Verified examples
- 2019 Métropole Mathematics: reference `19GENMATMEAG1`, 2 hours, 100 points, six exercises.
- 2018 Mathematics: official zero subject is retained as `OFFICIAL_ZERO_SUBJECT`.
- 2024 and 2025 official Eduscol mathematics PDFs are represented as verified source records.

## Official supplementary indexes
Official Eduscol STI pages provide additional subjects/corrections for 2018, 2021, 2022 and 2024, including foreign-centre variants and replacement sessions.

## Data model
`Exam → Component → Exercise → Question → Skill mapping → Attempt → Evidence → Remediation`

Question mappings carry chapter, primary/secondary Skills, points, difficulty, estimated time, confidence and review status.

## Guardrails
- Official exam, official zero subject, third-party mock and generated mock remain separate.
- Original-source provenance is retained.
- No automatic Approval.
- No historical question is assumed to match the 2027 3e-only scope without compatibility review.

## Next
LCAI-0013B should perform document ingestion, question decomposition and Skill mapping, beginning with recent official subjects and then expanding backward.
