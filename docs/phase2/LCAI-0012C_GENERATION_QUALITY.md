# LCAI-0012C — Generation Quality

## Headline metrics

- Requests completed: 1105
- Generation executions including later corrective batches: 1162
- Corrective regeneration requests: 57
- First-pass accepted: 1020 (92.31%)
- First-pass baseline LCAI-0012B: 75.27%
- Retries attempted: 91
- Retries recovered: 43
- Persisted Drafts: 1105
- Final technical rejects / missing slots: 0
- Tokens: {"input_tokens": 1310714, "output_tokens": 2978147, "total_tokens": 4288861}
- Sum of per-request generation latency: 26559.289 seconds
- Accepted answer kinds: {"open_response": 190, "structured": 418, "single_choice": 239, "exact_text": 55, "numeric": 200, "boolean": 1, "multiple_choice": 2}

## Stratified manual audit

- Sample: 70 (35 per grade).
- PASS: 52.
- REVIEW: 5.
- REJECT: 13.
- Fully aligned rate: 74.29%.
- Retry/corrective cases sampled: 43.

Every decision and note is preserved in `lcai_0012c_manual_audit_results.json`.

## Duplicate analysis

- Exact duplicate groups persisted: 0.
- Normalized duplicate groups persisted: 0.
- Near-duplicate pairs flagged: 1.
- Near pairs declared intentional variants: 0.

## Rejection reasons

```json
{
  "answer_not_in_choices": 40,
  "answer_contradiction": 92,
  "invalid_choices": 7
}
```

## Quality by grade

```json
{
  "FR-3E": {
    "target_requests": 586,
    "first_pass_accepted": 515,
    "corrective_executions": 47,
    "final_accepted": 586,
    "final_missing": 0
  },
  "FR-4E": {
    "target_requests": 519,
    "first_pass_accepted": 505,
    "corrective_executions": 10,
    "final_accepted": 519,
    "final_missing": 0
  }
}
```

## Quality by subject

```json
{
  "FRENCH": {
    "target_requests": 296,
    "first_pass_accepted": 294,
    "corrective_executions": 4,
    "final_accepted": 296,
    "final_missing": 0
  },
  "MATHEMATICS": {
    "target_requests": 387,
    "first_pass_accepted": 323,
    "corrective_executions": 46,
    "final_accepted": 387,
    "final_missing": 0
  },
  "EMC": {
    "target_requests": 48,
    "first_pass_accepted": 46,
    "corrective_executions": 0,
    "final_accepted": 48,
    "final_missing": 0
  },
  "ENGLISH": {
    "target_requests": 46,
    "first_pass_accepted": 45,
    "corrective_executions": 0,
    "final_accepted": 46,
    "final_missing": 0
  },
  "GEOGRAPHY": {
    "target_requests": 83,
    "first_pass_accepted": 79,
    "corrective_executions": 1,
    "final_accepted": 83,
    "final_missing": 0
  },
  "HISTORY": {
    "target_requests": 81,
    "first_pass_accepted": 74,
    "corrective_executions": 6,
    "final_accepted": 81,
    "final_missing": 0
  },
  "PHYSICS_CHEMISTRY": {
    "target_requests": 58,
    "first_pass_accepted": 57,
    "corrective_executions": 0,
    "final_accepted": 58,
    "final_missing": 0
  },
  "SPANISH": {
    "target_requests": 50,
    "first_pass_accepted": 48,
    "corrective_executions": 0,
    "final_accepted": 50,
    "final_missing": 0
  },
  "SVT": {
    "target_requests": 56,
    "first_pass_accepted": 54,
    "corrective_executions": 0,
    "final_accepted": 56,
    "final_missing": 0
  }
}
```

## Quality by content type and difficulty

```json
{
  "content_type": {
    "practice": {
      "target_requests": 664,
      "first_pass_accepted": 613,
      "corrective_executions": 40,
      "final_accepted": 664,
      "final_missing": 0
    },
    "assessment": {
      "target_requests": 369,
      "first_pass_accepted": 342,
      "corrective_executions": 13,
      "final_accepted": 369,
      "final_missing": 0
    },
    "diagnostic": {
      "target_requests": 36,
      "first_pass_accepted": 32,
      "corrective_executions": 2,
      "final_accepted": 36,
      "final_missing": 0
    },
    "remediation": {
      "target_requests": 36,
      "first_pass_accepted": 33,
      "corrective_executions": 2,
      "final_accepted": 36,
      "final_missing": 0
    }
  },
  "difficulty": {
    "1": {
      "target_requests": 192,
      "first_pass_accepted": 174,
      "corrective_executions": 12,
      "final_accepted": 192,
      "final_missing": 0
    },
    "2": {
      "target_requests": 770,
      "first_pass_accepted": 713,
      "corrective_executions": 34,
      "final_accepted": 770,
      "final_missing": 0
    },
    "3": {
      "target_requests": 143,
      "first_pass_accepted": 133,
      "corrective_executions": 11,
      "final_accepted": 143,
      "final_missing": 0
    }
  }
}
```

First-pass quality debt remains explicit. Technical acceptance does not constitute pedagogical Approval.
