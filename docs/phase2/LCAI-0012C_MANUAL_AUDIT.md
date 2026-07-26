# LCAI-0012C — Stratified Manual Audit

## Sample

Seventy persisted Drafts were read in full: prompt, expected answer and
explanation. The sample contains 35 items per grade and, for each grade:

- 10 Mathematics;
- 10 French;
- 5 English/Spanish;
- 5 History/Geography/EMC;
- 5 SVT/Physics-Chemistry.

It includes 43 retry-recovered or later corrective candidates and spans
Practice, Assessment, Diagnostic and Remediation plus D1, D2 and D3.

## Results

Status | Count | Rate
--- | ---: | ---:
PASS | 52 | 74.29%
REVIEW | 5 | 7.14%
REJECT | 13 | 18.57%

The decision for every sample ID is recorded in
`resources/content/expansion/lcai_0012c_manual_audit_results.json`.

## Correctness checks

- Mathematics reviewed: 20.
- Mathematics answers correct: 19/20 (95%).
- Sample 40 was independently enumerated: 55 values exist, but the smallest is
  2004 rather than the generated 2100. It is REJECT.
- Deterministic Science calculations/classifications checked: 7/7 numerically
  or factually correct.
- One qualitative Science scenario is REJECT because a second scratch by a
  different cat does not establish exposure to the same antigen; the claimed
  immune-memory conclusion is unsupported.

The mathematical 100% correctness target is therefore **not achieved** by the
manual sample and remains explicit LCAI-0012D debt.

## Main findings

1. QCM representation is the largest execution defect. Candidate options exist
   in generation records, but the current persisted executable question does
   not expose them. Multiple sampled prompts therefore refer to absent choices.
   The 241 persisted single/multiple-choice Drafts require consolidation.
2. Three sampled 4e Science activities use concepts or calculations above the
   intended grade, including logarithmic pH concentration and P/S-wave
   epicentral-distance calculation.
3. Some otherwise aligned explanations retain irrelevant “other options”
   boilerplate.
4. One History item contains a document but no explicit learner task.
5. Open-response rubric handling is generally useful and does not fabricate one
   exact prose answer.

No sampled concern was hidden or promoted. Every affected item remains Draft.
