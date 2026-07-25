# LCAI-0012B — Pilot Review Package

The complete structured review package is
`resources/content/pilot/lcai_0012b_real_candidates.json`. It contains target,
prompt, answer, explanation, hints, validation, quality and provenance.

## Strong examples

### 4e Mathematics — Fractions — Worked example

Prompt: add `3/8` litre and `1/12` litre. Expected answer: `11/24`.
The explanation establishes a common denominator and keeps the unit. This is
precise, age-appropriate and directly aligned.

### 3e French — Relative clause — Practice

The learner identifies the relative clause, antecedent, relative pronoun and
function in “Le chat qui dort sur le canapé…”. The answer separates the four
observables and supports targeted correction.

### 4e Physics-Chemistry — Conservation — Challenge

The learner uses `2 Mg + O2 → 2 MgO` with 48 g Mg, determines 80 g MgO and
32 g oxygen, then checks the mass balance. Quantities, units and explanation
are coherent.

## Borderline but retained

### 4e SVT — Earthquake remediation

The retained candidates distinguish magnitude from local damage and require
several vulnerability factors. They are useful but need editorial attention
to keep vocabulary and causal detail at 4e level.

### 3e French — Argumentation

The structured rubric correctly distinguishes thesis, argument, evidence and
limit. Because several answers are open, execution must use the rubric rather
than exact-text equality.

## Rejected examples

### Invalid single-choice outputs

Twelve first-pass candidates named a correct answer that did not exactly match
an option identifier/label. They were rejected by deterministic validation.

### Numeric contradiction

Eleven first-pass candidates disagreed with the independently recomputed
numeric value. They were rejected and never persisted.

### Manual rejection — French rewriting

One candidate asked for stylistic concision/register change rather than the
expected grammatical transformation focus. It was structurally valid but
pedagogically too broad.

### Manual rejection — 4e SVT

One remediation required logarithmic magnitude calculation. The mathematics
was coherent, but the task was above the intended grade-relative scope.

## Diversity

Multiple candidates for the same Skill vary context, representation, reasoning
path and scaffolding. The five difficulty families and the three
diagnostic/remediation chains demonstrate changes beyond number substitution.
No exact, normalized or high-threshold lexical near duplicate remained.

