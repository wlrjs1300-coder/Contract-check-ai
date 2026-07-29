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

## Clause Splitting Result Structure

PR-2 clause splitting output uses JSON for local experiment observation.

Top-level fields:

| Field | Meaning |
|---|---|
| `test_case_id` | Synthetic fixture or JSON input identifier |
| `input_type` | `fixture` or `json` |
| `source_text_sha256` | SHA-256 of normalized source text re-encoded as UTF-8 |
| `clauses` | Detected clause records |
| `non_clause_sections` | Header, footer, and signature sections |
| `unclassified_sections` | Non-empty source text not classified as clause or non-clause section |
| `document_warnings` | Whole-document warnings such as missing clause markers |

Each clause contains 13 fields:

| Field | Meaning |
|---|---|
| `clause_id` | Deterministic local clause identifier for the actual output |
| `reference_id` | Stable source reference in `{test_case_id}:clause:{ordinal}:{start_offset}-{end_offset}` format |
| `source_hash` | First 12 characters of SHA-256 for the normalized source slice |
| `ordinal` | 1-based clause order in the document |
| `marker` | Detected marker such as `제1조`, `1)`, `(1)`, `①`, `특약`, or `부칙` |
| `clause_type` | `normal`, `appendix`, or `special_agreement` |
| `title` | Explicit parenthesized title only; otherwise `null` |
| `raw_heading` | Text after the marker on the marker line |
| `body` | Clause body with explicit parenthesized title excluded when present |
| `start_offset` | 0-based start offset in normalized source text |
| `end_offset` | Exclusive end offset in normalized source text |
| `source_line_start` | 1-based start line in LF-normalized source text |
| `source_line_end` | 1-based end line in LF-normalized source text |
| `warnings` | Clause-level warnings such as `inline_marker_suspected` or `empty_body` |

`raw_heading` is optional in meaning but is present in PR-2 actual output to preserve marker-line context.

`non_clause_sections` records use:

- `type`: `header`, `footer`, or `signature`
- `text`
- `start_offset`
- `end_offset`
- `source_line_start`
- `source_line_end`
- `warnings`

`unclassified_sections` records use the same shape with `type: unclassified`.

`unclassified_text` means the source text was not dropped. It remains available for human review and later design decisions.

Offset and line rules:

- Input is decoded as UTF-8.
- UTF-8 BOM is rejected.
- CRLF and CR are normalized to LF.
- Offsets are 0-based and `end_offset` is exclusive.
- Line numbers are 1-based after LF normalization.

`reference_id` and `source_hash` are generated by the implementation for actual output. The frozen expected file does not include these derived fields.

Passing the clause splitting evaluator only means the local experiment matched the frozen synthetic expectations. It is not a product guarantee, legal safety guarantee, or complete parser correctness claim.

## PII Masking Result Structure

PR-3 personal data detection and masking output uses JSON for local experiment observation.

Top-level fields:

| Field | Meaning |
|---|---|
| `entities` | Detected synthetic personal data records |
| `masked_text` | Source text with detected entity spans replaced by mask tokens |
| `masked_text_sha256` | SHA-256 of the masked text encoded as UTF-8 |
| `document_warnings` | Whole-document warnings such as `no_pii_detected` |

Each entity contains:

| Field | Meaning |
|---|---|
| `ordinal` | 1-based entity order in the document |
| `entity_type` | One of the approved PR-3 taxonomy values |
| `start_offset` | 0-based start offset in normalized source text |
| `end_offset` | Exclusive end offset in normalized source text |
| `source_line_start` | 1-based start line in LF-normalized source text |
| `source_line_end` | 1-based end line in LF-normalized source text |
| `mask_token` | Deterministic token such as `[PERSON_n]` or `[BIRTH_n]` |
| `source_hash` | First 12 characters of SHA-256 for the normalized source slice |
| `warnings` | Entity-level warnings such as `repeated_value` or `dense_cluster` |

Approved PR-3 taxonomy and token prefixes:

| entity_type | token |
|---|---|
| `person` | `[PERSON_n]` |
| `phone` | `[PHONE_n]` |
| `email` | `[EMAIL_n]` |
| `address` | `[ADDRESS_n]` |
| `date_of_birth` | `[BIRTH_n]` |
| `national_id_number` | `[RRN_n]` |
| `business_registration_number` | `[BIZ_NO_n]` |
| `account_number` | `[ACCOUNT_n]` |

Forbidden entity fields:

- `text`
- `raw_text`
- `value`
- `source_value`
- `matched_text`

The evaluator compares actual output with frozen expected data, verifies exclusion overlap and exclusion self-overlap, verifies expected span replacement, and reruns detection on the masked text to confirm residual entity count 0.

Passing the PII masking evaluator only means the local deterministic synthetic fixture experiment matched frozen expectations. It does not approve real personal data handling, real contract processing, external AI transfer, or production service release.
