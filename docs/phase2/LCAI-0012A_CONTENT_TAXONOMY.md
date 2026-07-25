# LCAI-0012A — Content Taxonomy

## Canonical taxonomy

| Type | Purpose and interaction | Answer / hints | Mastery evidence |
|---|---|---|---|
| `LESSON` | Introduce and explain knowledge or a strategy | Answer optional; progressive hints allowed | No direct mastery evidence by default |
| `WORKED_EXAMPLE` | Model a complete reasoned solution | Solution required; answer may be visible | Learning support, not independent evidence |
| `GUIDED_PRACTICE` | Let the learner act with scaffolding | Deterministic answer where possible; hints expected | Weak-to-moderate evidence, assistance recorded |
| `PRACTICE` | Independent application | Expected answer and feedback required | Normal mastery evidence |
| `ASSESSMENT` | Measure mastery independently | Expected answer required; normally no hints | Strong mastery evidence |
| `DIAGNOSTIC` | Identify a prerequisite gap or misconception | Expected answer required; no answer-revealing hint | Diagnostic evidence |
| `REMEDIATION` | Treat one identified weakness | Expected answer and targeted feedback required | Evidence about the remediated competency |
| `CHALLENGE` | Extend or transfer established mastery | Answer/rubric required; little scaffolding | Advanced evidence, never a substitute for core mastery |
| `REVISION` | Retrieve and consolidate prior learning | Depends on activity; feedback expected | Consolidation evidence |

`content_type` describes the artifact. `pedagogical_intent` describes why it is
used (`INTRODUCE`, `MODEL`, `SCAFFOLD`, `PRACTICE`, `CHECK`, `DIAGNOSE`,
`REMEDIATE`, `CONSOLIDATE`, `EXTEND`). They are deliberately separate: a
revision artifact can, for example, diagnose or consolidate.

## Existing type mapping

| Existing values | Canonical type |
|---|---|
| `method_sheet` | `LESSON` |
| `worked_example` | `WORKED_EXAMPLE` |
| `exercise` | `PRACTICE` |
| `quiz`, `multiple_choice_question`, `open_question`, `exam_practice`, `mini_assessment` | `ASSESSMENT` |
| `diagnostic_activity` | `DIAGNOSTIC` |
| `remediation_activity` | `REMEDIATION` |
| `problem` | `CHALLENGE` |
| `revision_sheet`, `transition_activity` | `REVISION` |

The mapping is non-destructive. Existing database values remain unchanged.

## Activity and answer boundaries

Every executable candidate carries instructions, prompt, expected answer,
explanation, optional hints and feedback, relative difficulty, one primary
Skill and optional Sub-skill/secondary Skills. Implemented answer forms match
the current executor: normalized text, numeric, single/multiple choice,
boolean, structured and review-only open response. Numeric answers can include
an independently computed value and tolerance.

