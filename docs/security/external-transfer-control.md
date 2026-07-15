# ContractCheck AI External Transfer Control

- Status: Draft
- Approval status: Review required / Not approved
- Version: v0.2.2 PR-4
- Implementation status: Not started
- Provider selection: Not selected
- Endpoint selection: Not selected
- Model selection: Not selected
- API key preparation: Not approved
- Provider adapter: Not implemented
- External AI use approval: Not granted
- Real external transfer: NOT EXECUTED
- Real contract use: Not approved
- Real personal data use: Not approved
- Production use: Not approved

This document is a design draft, not an approval record. It does not approve external AI use, external transfer, provider selection, endpoint selection, model selection, API key preparation, provider adapter implementation, real contract processing, real personal data processing, or production use. It is not legal advice, privacy compliance certification, or an operational approval record. Merging this document does not approve an external AI call or any real external transfer.

## 1. Document Purpose

This document defines the draft external transfer control boundary for ContractCheck AI v0.2.2 PR-4.

Its purpose is to specify when data may become an external transfer candidate, when transfer must be blocked, which outbound fields may be reviewed, how provider request and response data must be handled, and which audit metadata is required without exposing contract text or personal data.

## 2. Scope

This draft covers:

- external transfer default-deny rules
- pre-transfer safety gates
- outbound field allowlist candidates
- prohibited outbound fields
- payload minimization
- transfer blocking conditions
- outbound candidate construction flow
- final pre-transfer verification
- post-transfer handling boundaries
- timeout, retry, and duplicate-call safety
- provider request and response storage rules
- external transfer log and audit metadata
- failure handling
- follow-up PR connections

This draft does not implement an external AI call, approve provider use, approve endpoint or model use, approve API key preparation, or permit real contract or personal data transfer.

## 3. Current Approval State

- Provider: NOT SELECTED
- Endpoint: NOT SELECTED
- Model: NOT SELECTED
- API key preparation: NOT APPROVED
- Provider adapter: NOT IMPLEMENTED
- Real data transfer: NOT APPROVED
- Production transfer: NOT APPROVED
- External request: NOT EXECUTED
- Zone C to Zone E: NOT APPROVED
- Zone E to Zone C: NOT APPROVED

## 4. External Transfer Principles

- External transfer is default DENY.
- Only explicitly allowlisted minimum fields can become transfer candidates.
- Fields outside the allowlist are blocked by default.
- Original contract files must not be transferred.
- Full extracted text must not be transferred.
- Unmasked clause data must not be transferred.
- Detected personal data must not be transferred.
- Residual PII must block transfer.
- Raw files and raw payloads must not be transferred.
- Only approved clause-level data can become a candidate.
- The purpose and field set must be explicit; otherwise the result is REVIEW REQUIRED or BLOCK.
- Provider, endpoint, and model approvals are separate gates.
- Actual data scope approval is separate from allowlist validation.
- Cost approval is separate.
- Final user approval is required before any real external transfer.
- Real external transfer remains NOT EXECUTED.
- Real contract data and real personal data remain prohibited.
- Synthetic fixtures are the only test input approved in this phase.
- The pipeline must remain verifiable even if external transfer is not executed.

## 5. Transfer Decision States

The transfer decision states are:

- DENY
- BLOCK
- REVIEW REQUIRED
- CANDIDATE
- APPROVAL REQUIRED
- APPROVED FOR TEST ONLY
- APPROVED FOR PRODUCTION
- NOT EXECUTED

Current state:

- Provider: NOT SELECTED
- Endpoint: NOT SELECTED
- Model: NOT SELECTED
- Real data transfer: NOT APPROVED
- Production transfer: NOT APPROVED
- External request: NOT EXECUTED

`APPROVED FOR TEST ONLY` and `APPROVED FOR PRODUCTION` are state definitions only. They are not current states in this PR.

## 6. Required Pre-Transfer Safety Gates

The following gates must pass before data can even be considered for external transfer:

1. Input file format validation passed
2. Input file size validation passed
3. Text extraction completed
4. Clause splitting completed
5. Personal data detection completed
6. Masking completed
7. Residual PII scan completed
8. Residual PII result is 0
9. Data classification completed
10. No D1 data included
11. No original file included
12. No full extracted text included
13. No unmasked clause data included
14. No detected personal data included
15. Only approved clause-level data included
16. Outbound allowlist passed
17. Schema validation passed
18. `source_hash` non-reconstructability reviewed
19. `reference_id` included
20. Provider approved
21. Endpoint approved
22. Model approved
23. Actual transfer data scope approved
24. Cost approved
25. Timeout policy approved
26. Retry policy approved
27. Final user approval obtained
28. Audit event can be created
29. Final transfer execution decision made

Because gates 20 through 29 are not complete, the current execution decision is `NOT EXECUTED` or `APPROVAL REQUIRED`.

## 7. Outbound Allowlist

Allowlist passing does not approve real external transfer. It only means that a field may be reviewed as a candidate.

| Field | Purpose | Required or optional | Personal data allowed | Contract raw content allowed | Classification | Allowlist status | Required control | Decision status | Follow-up approval |
|---|---|---|---|---|---|---|---|---|---|
| reference_id | Response association without body text | Required | No | No | D3 | ALLOWED CANDIDATE | Stable mapping, no source text | PROPOSED | PR-4 review |
| clause_id | Clause association without body text | Required | No | No | D3 | ALLOWED CANDIDATE | No contract body | PROPOSED | PR-4 review |
| clause_order | Preserve ordering | Required | No | No | D3 | ALLOWED CANDIDATE | Numeric or stable order only | PROPOSED | PR-4 review |
| masked_clause_text | Minimum clause body after masking | Optional candidate | No residual PII allowed | Masked content only | D2 | REVIEW REQUIRED | Masking complete, residual 0, user approval | REVIEW REQUIRED | Separate approval |
| clause_type | Clause category | Optional | No | No | D3 | ALLOWED CANDIDATE | Controlled vocabulary | PROPOSED | PR-4 review |
| document_type_candidate | Document type hint | Optional | No | No | D3 | ALLOWED CANDIDATE | Candidate only, not legal classification | PROPOSED | PR-4 review |
| analysis_instruction_id | Internal analysis instruction reference | Required | No | No | D3 | ALLOWED CANDIDATE | Existing instruction catalog only | PROPOSED | PR-4 review |
| policy_version | Policy version | Required | No | No | D3 | ALLOWED CANDIDATE | Version string only | PROPOSED | PR-4 review |
| schema_version | Outbound schema version | Required | No | No | D3 | ALLOWED CANDIDATE | Version string only | PROPOSED | PR-4 review |
| language_code | Language hint | Optional | No | No | D3 | ALLOWED CANDIDATE | Standard code only | PROPOSED | PR-4 review |
| source_hash | Non-reconstructable source binding | Required | No | No | D3 | REVIEW REQUIRED | Hash method, salt, pepper, and non-reconstructability review | REVIEW REQUIRED | PR-4 and later security review |
| request_id | Request correlation | Required | No | No | D3 | ALLOWED CANDIDATE | Random identifier, no user data | PROPOSED | PR-4 review |
| correlation_id | Cross-step correlation | Optional | No | No | D3 | ALLOWED CANDIDATE | No user, path, or source content | PROPOSED | PR-4 review |
| redaction_summary | Masking summary | Optional | Raw PII prohibited | No | D2 | REVIEW REQUIRED | Counts and categories only, no raw values | REVIEW REQUIRED | Separate approval |
| residual_scan_status | Residual scan status | Required | Raw PII prohibited | No | D2 | ALLOWED CANDIDATE | Status only; residual found blocks transfer | PROPOSED | PR-4 review |
| data_classification | Data class label | Required | No | No | D3 | ALLOWED CANDIDATE | Controlled class label only | PROPOSED | PR-4 review |
| provider_request_version | Provider request schema version | Required | No | No | D3 | ALLOWED CANDIDATE | Version only | PROPOSED | PR-4 review |

Additional allowlist rules:

- `reference_id` must not contain source text.
- `clause_id` must not contain contract body text.
- `masked_clause_text` is only a candidate after masking and residual 0.
- `source_hash` must be non-reconstructable.
- `source_hash` salt, pepper, and hash method remain undecided.
- `redaction_summary` must not contain raw detected personal data.
- `residual_scan_status` must not contain raw personal data.
- `analysis_instruction_id` may only reference an internal instruction catalog.
- `provider_request_version` may only identify the request schema version.
- Allowlist passing never means real transfer approval.

## 8. Field-Level Transfer Policy

- Required fields must be present only when their controls pass.
- Optional fields must be omitted unless needed for the approved purpose.
- Empty fields must be removed.
- Duplicate fields must be removed.
- Unknown fields must cause BLOCK.
- Provider-requested fields that are not allowlisted must not be added.
- Fields that become D1 data after composition must cause BLOCK.
- Fields that contain raw personal data must cause BLOCK.
- Fields that contain full contract text must cause BLOCK.

## 9. Payload Minimization

- Use clause-level minimum payloads.
- Remove metadata not required for analysis.
- Do not send full document structure.
- Do not automatically include neighboring clauses.
- Do not send personal data detection source values.
- Send only limited masking summaries when separately approved.
- Remove duplicate fields.
- Remove empty fields.
- Remove internal paths and internal identifiers.
- Do not add missing fields just because a provider requests them.
- A payload size limit is required, but the exact value is undecided.
- A purpose-specific schema is required.
- Schema version must be fixed.
- If the allowlist and schema conflict, BLOCK.

## 10. Transfer Blocking Conditions

The system must BLOCK or DENY transfer when any of the following conditions apply:

- Provider not approved
- Endpoint not approved
- Model not approved
- API key preparation not approved
- Provider adapter not implemented
- Actual data scope not approved
- Final user approval missing
- Residual PII found
- Residual scan failed
- Masking failed
- Allowlist violation
- Schema violation
- D1 data included
- Original file included
- Full extracted text included
- Personal data source value included
- Raw provider request storage attempted
- Cost approval missing
- Timeout policy missing
- Retry policy missing
- Audit event cannot be created
- Policy version mismatch
- `source_hash` verification unavailable
- `reference_id` missing
- Payload size policy violation
- Unknown field present
- Provider policy review expired
- Security incident in progress
- User cancellation
- Operational emergency block

## 11. Outbound Candidate Construction Flow

1. Receive internal analysis request
2. Confirm active policy version
3. Confirm data classification
4. Confirm masking status
5. Confirm residual PII result
6. Select approved clauses only
7. Extract fields by allowlist
8. Remove or block unknown fields
9. Construct payload schema
10. Attach `reference_id`
11. Attach `source_hash`
12. Confirm provider, endpoint, and model approval status
13. Confirm cost, timeout, and retry approval
14. Confirm final user approval
15. Decide outbound candidate status
16. Create audit metadata
17. Re-verify immediately before transfer
18. Execute call or mark `NOT EXECUTED`

At this phase, step 18 must remain `NOT EXECUTED`.

## 12. Final Pre-Transfer Verification

Immediately before any future transfer, the system must re-check:

- residual result is still 0
- outbound allowlist still matches the payload
- provider approval is still active
- endpoint approval is still active
- model approval is still active
- policy version has not changed
- schema version has not changed
- user final approval is present
- cost approval is present
- timeout policy is present
- retry policy is present
- audit event can be generated

Any failure results in BLOCK, REVIEW REQUIRED, or NOT EXECUTED.

## 13. Post-Transfer Handling

This PR does not execute transfer, but it defines future handling boundaries:

- Treat provider response as untrusted.
- Validate response schema before use.
- Validate `reference_id` before association.
- Run output safety checks before user display.
- Do not store raw provider response.
- Do not log raw provider response.
- Do not use response if schema or safety checks fail.
- Do not present response directly to users.

## 14. Timeout, Retry, and Duplicate Calls

- Timeout policy is required.
- Timeout value is undecided.
- Retry is disabled by default or requires REVIEW.
- Retry count is undecided.
- Retry interval is undecided.
- Backoff method is undecided.
- Same-payload retry is prohibited before idempotency is defined.
- `request_id` or idempotency key is required before retry.
- Duplicate-call detection is required.
- Duplicate cost prevention is required.
- Retry after user cancellation is prohibited.
- Retry after policy change is prohibited.
- Retry after residual PII detection is prohibited.
- Retry after allowlist violation is prohibited.
- Provider-error retry remains undecided.
- Repeated failure requires ESCALATION REQUIRED.

## 15. Provider Request and Response Storage Policy

The following are explicitly prohibited:

- permanent storage of raw provider request
- permanent storage of raw provider response
- logging provider prompt
- logging provider completion
- logging masked clause body
- logging full outbound payload
- logging full response body
- logging credential
- logging authorization header

Only minimal metadata can be considered:

- request_id
- correlation_id
- reference_id
- provider approval status
- endpoint approval status
- model approval status
- policy version
- schema version
- event code
- result code
- block reason code
- processing duration
- retry count
- timestamp

Whether these metadata fields are stored, and for how long, requires PR-3 policy and later approval.

## 16. External Transfer Logs and Audit Policy

Draft audit events:

| Event code | Trigger | Log type | Required metadata | Prohibited data | Action | Decision status |
|---|---|---|---|---|---|---|
| EXTERNAL_TRANSFER_CANDIDATE_CREATED | Candidate payload constructed | Audit | request_id, policy_version, schema_version | Body, PII, raw payload | Record candidate | PROPOSED |
| EXTERNAL_TRANSFER_BLOCKED | Blocking condition met | Audit | request_id, block_reason_code | Body, PII | Block | PROPOSED |
| EXTERNAL_TRANSFER_REVIEW_REQUIRED | Ambiguous transfer condition | Audit | request_id, review_reason_code | Body, PII | Review | PROPOSED |
| PROVIDER_NOT_APPROVED | Provider approval missing | Audit | request_id | Body, PII | Block | PROPOSED |
| ENDPOINT_NOT_APPROVED | Endpoint approval missing | Audit | request_id | Body, PII | Block | PROPOSED |
| MODEL_NOT_APPROVED | Model approval missing | Audit | request_id | Body, PII | Block | PROPOSED |
| OUTBOUND_ALLOWLIST_PASSED | Allowlist passed | Audit | request_id, schema_version | Body, PII | Continue review | PROPOSED |
| OUTBOUND_ALLOWLIST_BLOCKED | Allowlist violation | Audit | request_id, block_reason_code | Body, PII, blocked value | Block | PROPOSED |
| RESIDUAL_PII_BLOCKED | Residual PII found | Audit | request_id, block_reason_code | Raw residual value | Block | PROPOSED |
| PAYLOAD_SCHEMA_PASSED | Payload schema passed | Audit | request_id, schema_version | Body, PII | Continue review | PROPOSED |
| PAYLOAD_SCHEMA_BLOCKED | Payload schema failed | Audit | request_id, block_reason_code | Body, PII | Block | PROPOSED |
| USER_APPROVAL_MISSING | Final user approval missing | Audit | request_id | Body, PII | Block | PROPOSED |
| COST_APPROVAL_MISSING | Cost approval missing | Audit | request_id | Body, PII | Block | PROPOSED |
| TIMEOUT_POLICY_MISSING | Timeout policy missing | Audit | request_id | Body, PII | Block | PROPOSED |
| RETRY_POLICY_MISSING | Retry policy missing | Audit | request_id | Body, PII | Block | PROPOSED |
| EXTERNAL_AI_NOT_EXECUTED | Transfer not executed | Audit | request_id, result_code | Body, PII | Stop | PROPOSED |

The following event codes are not added as active events in this PR:

- EXTERNAL_AI_EXECUTED
- EXTERNAL_TRANSFER_COMPLETED
- PROVIDER_CALL_SUCCEEDED

## 17. Prohibited Transfer Fields

| Prohibited item | Reason | Data class | Block action | Logging rule | Decision status |
|---|---|---|---|---|---|
| original contract file | Source document | D1 | BLOCK | Metadata only | PROHIBITED |
| full extracted text | Full source text | D1 | BLOCK | Metadata only | PROHIBITED |
| unmasked clause data | Source content may include PII | D1 | BLOCK | Metadata only | PROHIBITED |
| detected personal data | Raw personal data source | D1 | BLOCK | Do not log value | PROHIBITED |
| residual PII value | Unmasked personal data | D1 | BLOCK | Do not log value | PROHIBITED |
| original filename | May identify user or contract | D2 | BLOCK | Do not log | PROHIBITED |
| local file path | Internal path and user data risk | D3 | BLOCK | Do not log | PROHIBITED |
| user name | Personal data | D1 | BLOCK | Do not log | PROHIBITED |
| resident registration number | Sensitive identifier | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| passport number | Sensitive identifier | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| driver license number | Sensitive identifier | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| phone number | Personal data | D1 | BLOCK | Do not log | PROHIBITED |
| email address | Personal data | D1 | BLOCK | Do not log | PROHIBITED |
| postal address | Personal data | D1 | BLOCK | Do not log | PROHIBITED |
| bank account | Financial identifier | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| card number | Financial identifier | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| access token | Credential | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| refresh token | Credential | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| API Key | Credential | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| password | Credential | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| secret | Credential | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| authorization header | Credential | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| cookie value | Credential/session data | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| database connection string | Secret | D1 | SECURITY EVENT | Do not log | PROHIBITED |
| raw operational log | May contain source data | D2 | BLOCK | Do not export | PROHIBITED |
| raw audit log | May contain source data | D2 | BLOCK | Do not export | PROHIBITED |
| raw provider request | Raw external payload | D1 | BLOCK | Do not store | PROHIBITED |
| raw provider response | Untrusted raw response | D1 | BLOCK | Do not store | PROHIBITED |
| internal stack trace | Internal security detail | D3 | BLOCK | Redacted only | PROHIBITED |
| full exception body | May contain source data | D2 | BLOCK | Code only | PROHIBITED |
| internal security configuration | Internal security detail | D3 | BLOCK | Do not export | PROHIBITED |
| user IP address | Personal data or tracking data | D2 | REVIEW REQUIRED | Minimal metadata only | PROHIBITED |
| device identifier | Personal data or tracking data | D2 | REVIEW REQUIRED | Minimal metadata only | PROHIBITED |
| session identifier | Session data | D2 | BLOCK | Do not export | PROHIBITED |
| any field not explicitly allowlisted | Unknown field | Unknown | BLOCK | Field name only | PROHIBITED |

## 18. Failure Handling

- Masking failure: BLOCK and do not construct outbound payload.
- Residual PII found: BLOCK and do not construct outbound payload.
- Allowlist violation: BLOCK and log code only.
- Schema violation: BLOCK.
- Missing provider approval: BLOCK.
- Missing endpoint approval: BLOCK.
- Missing model approval: BLOCK.
- Missing user approval: BLOCK.
- Missing cost approval: BLOCK.
- Timeout policy missing: BLOCK.
- Retry policy missing: BLOCK.
- Audit event creation failure: BLOCK or REVIEW REQUIRED.
- User cancellation: NOT EXECUTED.

## 19. Verification Requirements

Future implementation must verify:

- no D1 data in outbound payload
- no original file in outbound payload
- no full extracted text
- no unmasked clause data
- no detected personal data source values
- residual result is 0
- allowlist pass
- schema pass
- reference_id present
- source_hash is non-reconstructable
- provider, endpoint, model approvals exist
- timeout and retry policies exist
- final user approval exists
- audit metadata can be created without body or PII

## 20. Open Items

- Exact outbound schema
- Exact payload size limit
- Hash method, salt, and pepper approach for `source_hash`
- Provider approval process
- Endpoint approval process
- Model approval process
- Cost approval process
- Timeout values
- Retry count and backoff method
- Audit metadata retention period
- User approval UX and wording

## 21. Follow-up PR Connections

| Follow-up PR | Connection |
|---|---|
| PR-5 | Access control, failure handling, output safety, user notice, security test strategy |
| PR-6 | Integrated review, unresolved items, final design decision, v0.2.2 closeout |
| v0.3 | UI and user approval placement |
| v0.4 | API and DB schema |
| v0.5 | Pipeline implementation and provider adapter implementation |

## 22. Approval State

- External transfer policy approval: Not approved
- Outbound allowlist approval: Not approved
- Provider approval: Not approved
- Endpoint approval: Not approved
- Model approval: Not approved
- API key preparation approval: Not approved
- Provider adapter implementation approval: Not approved
- Real data transfer approval: Not approved
- Cost approval: Not approved
- Timeout policy approval: Not approved
- Retry policy approval: Not approved
- Production transfer approval: Not approved
