\# Learning Coach AI — Codex Working Rules



\## Refactoring safety rule



Before deleting, renaming, moving, or significantly modifying an existing module, always prefer a progressive migration using the strangler pattern:



1\. Create the new target structure.

2\. Preserve the existing implementation temporarily.

3\. Redirect calls progressively to the new implementation.

4\. Add or update tests to prove behavioral equivalence.

5\. Remove legacy code only when:

&#x20;  - no production code imports or calls it;

&#x20;  - tests pass;

&#x20;  - application startup succeeds;

&#x20;  - no user-visible regression is identified.



Never perform a large-bang refactor when a progressive migration is possible.



\## Mandatory safeguards



\- Do not modify DuckDB schemas or data unless the ticket explicitly requests it.

\- Do not introduce functional changes during infrastructure or architecture-refactoring tickets.

\- Do not delete an existing feature without explicit approval.

\- Do not commit or push unless explicitly requested.

\- Report every created, modified, moved, renamed, and deleted file.

\- Clearly identify any unresolved risk or incomplete migration.

\## LCAI-0000A — AI validation (obligatoire)

Avant toute demande de revue utilisateur, exécuter la validation technique IA :

\- Script : `python scripts/lcai_0000a_technical_validation.py --ticket <ID>`
\- Curriculums : `python scripts/lcai_0000a_technical_validation.py --curriculum-all`
\- Doc : `docs/phase3/LCAI-0000A_AI_VALIDATION_FRAMEWORK.md`
\- Règle Cursor : `.cursor/rules/lcai-0000a-ai-validation-framework.mdc`

L'utilisateur valide **uniquement** le comportement fonctionnel et l'UX, pas le code ni les tests.

