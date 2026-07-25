# LCAI-0012A — Content Factory Architecture

```text
Curriculum repository (read-only resolution)
              |
ContentGenerationRequest
              |
ContentGenerator port ---- future provider adapter
              |
GeneratedContentCandidate (untrusted, in memory)
              |
schema -> curriculum -> structure -> answer -> difficulty
       -> pedagogy -> duplicate -> safety/quality
              |
existing exercises/questions/content_versions: DRAFT
              |
existing Draft -> Review -> Approved workflow
              |
Approved Learning Catalog
```

The domain and application layers contain no provider reference. Generation
occurs outside database transactions; only validated candidates enter a short
persistence transaction. A generator never returns or creates Approved
content. Provider prompts belong in future infrastructure resources, versioned
through provenance, and never in Streamlit.

The target contains program, grade, subject, chapter, primary Skill, optional
Sub-skill and justified secondary Skills. Exact database resolution rejects
inconsistent combinations. Prerequisites remain curriculum context; they are
not silently added to every activity.

Validation returns `ERROR`, `WARNING` and `INFO`. Errors block persistence.
Quality dimensions are curriculum alignment, answer integrity, pedagogical
completeness, traceability and safety; an aggregate score can never hide an
error. Normalized fingerprints detect accidental duplicates. A matching
`family_code` with distinct declared variant roles records an intentional
guided/evaluative variant instead.

Generated text is untrusted: obvious script/JavaScript/destructive SQL payloads
are rejected. Source material is data, never generator instruction. Raw
provider responses and secrets are not persisted.

No migration was required. Existing normalized content tables, generic
version payload, status events, quality assessments and Approved view represent
the foundation cleanly. Existing Student/Homework/Revision queries therefore
retain their Approved-only boundary.

