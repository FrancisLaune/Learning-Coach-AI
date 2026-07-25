# LCAI-0012B — Real Generation Metrics

## Generator

- Layer: real generation pilot through the provider-independent `ContentGenerator` port
- Infrastructure adapter: OpenAI structured output
- Configured model: `gpt-5-mini`
- Prompt/template: `lcai-0012b-prompt-v1`
- No API call is used by automated tests

## Volume and outcome

| Metric | Result |
|---|---:|
| Selected Skills | 24 |
| Planned API requests | 45 |
| Requested candidates | 93 |
| First-pass valid | 70 |
| First-pass warnings | 0 |
| First-pass rejected | 23 |
| First-pass acceptance | 75.27% |
| First-pass rejection | 24.73% |
| Controlled request retries | 19 |
| Technically valid after retry | 90 |
| Manual pedagogical rejections | 2 |
| Final accepted Drafts | 88 |
| Final acceptance | 94.62% |
| Generation failures | 0 |
| Tokens including discarded retries | 715,612 |
| Parallel wall-clock time | 909.44 s |
| Mean accepted-candidate request latency | about 33.8 s |

No price estimate is asserted because provider pricing is not part of the
domain and no reliable billed-cost response was available.

## First-pass rejection reasons

| Reason | Occurrences |
|---|---:|
| Correct choice not represented exactly in options | 12 |
| Independent numeric computation contradiction | 11 |

Optional missing-hint information was recorded three times but was not itself
a blocking error.

## Final accepted by subject

| Subject | Accepted | First-pass rejected |
|---|---:|---:|
| Mathematics | 42 | 11 |
| French | 23 | 4 |
| English | 3 | 0 |
| Spanish | 3 | 1 |
| History | 6 | 3 |
| Geography | 3 | 1 |
| EMC | 3 | 0 |
| SVT | 2 | 1 |
| Physics-Chemistry | 3 | 2 |

## Final accepted by type

| Canonical type | Accepted | First-pass rejected |
|---|---:|---:|
| `WORKED_EXAMPLE` | 8 | 0 |
| `GUIDED_PRACTICE` | 9 | 1 |
| `PRACTICE` | 23 | 7 |
| `ASSESSMENT` | 9 | 3 |
| `DIAGNOSTIC` | 12 | 2 |
| `REMEDIATION` | 11 | 4 |
| `CHALLENGE` | 7 | 4 |
| `REVISION` | 9 | 2 |

## Final accepted by difficulty

| Difficulty | Accepted | First-pass rejected |
|---|---:|---:|
| 1 | 10 | 4 |
| 2 | 73 | 18 |
| 3 | 5 | 1 |

## Correctness, alignment and duplicates

- Directly deterministic answer forms (`numeric`, `exact_text`,
  `single_choice`, `boolean`): 30 accepted; 30/30 correct in the audit.
- All 42 accepted Mathematics candidates were independently recalculated or
  manually checked against their explanations: 42/42 correct.
- One candidate per Skill was audited for curriculum alignment. Two
  misaligned/above-level candidates were rejected manually; the remaining
  accepted sample was 22/22 aligned (100%).
- Exact duplicates: 0.
- Normalized duplicates: 0.
- Lexical near-duplicate warnings at Jaccard >= 0.75: 0.
- Intentional family variants: 24 generation families represented.

This is a pilot result, not evidence that production coverage is sufficient.

