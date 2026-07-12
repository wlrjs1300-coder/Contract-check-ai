# v0.2.1 Spike Result Schema

## Purpose

This schema defines common result fields for v0.2.1 spike observations.

The schema is for experiment observation only. It must not be used as a user-facing legal risk score, product quality guarantee, or legal safety guarantee.

## Storage Formats

- Raw result record candidate: CSV
- Structured detection result when needed: JSON
- Human review summary: Markdown

Raw input and raw external response must not be stored in Git. Generated local artifacts and raw outputs must remain ignored.

## Fields

| Field | Meaning | Candidate Type | Required | Auto Aggregation | Human Review | Storage Caution |
|---|---|---|---|---|---|---|
| `experiment_id` | Identifier for the spike run | string | yes | yes | no | Do not include provider secrets or local paths. |
| `test_case_id` | Identifier for a fixture or generated case | string | yes | yes | no | Use synthetic IDs only. |
| `input_type` | Input source category such as fixture or generated | string | yes | yes | no | Do not store raw input text in this field. |
| `expected_result` | Expected observation for the test case | string or object | yes | optional | yes | Keep concise; avoid contract originals or personal data. |
| `actual_result` | Observed result from the spike | string or object | yes | optional | yes | Do not store raw external responses. |
| `pass` | Whether this individual spike case met its expected result | boolean | yes | yes | yes | This is not a legal safety guarantee. |
| `failure_reason` | Reason for failure when `pass` is false | string | no | yes | yes | Avoid raw contract text or personal data. |
| `false_positive` | Whether the case produced an unwanted positive detection | boolean | yes | yes | yes | Use only synthetic case references. |
| `false_negative` | Whether the case missed an expected detection | boolean | yes | yes | yes | Use only synthetic case references. |
| `privacy_issue` | Whether the result showed privacy handling concern | boolean | yes | yes | yes | Do not include exposed personal data; summarize only. |
| `legal_expression_issue` | Whether output included legal certainty or guarantee risk | boolean | yes | yes | yes | Do not store prohibited raw output; summarize the issue. |
| `manual_review` | Whether a human review is needed | boolean | yes | yes | yes | Keep review notes concise and public-safe. |
| `notes` | Additional safe observation summary | string | no | no | yes | No raw input, raw output, secrets, or real personal data. |

## Additional Rules

- `pass` is an individual spike test judgment only.
- `pass` must not be interpreted as legal safety, product readiness, or complete privacy protection.
- Results must not become numeric legal risk scores.
- If structured JSON is needed, keep only sanitized fields and synthetic identifiers.
- If human review is needed, write a short Markdown summary without raw input or raw external response.
