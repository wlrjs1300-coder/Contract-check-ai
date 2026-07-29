# ContractCheck AI Provider Boundary

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

This document is a design draft, not an approval record. It does not approve provider selection, endpoint selection, model selection, credential preparation, provider adapter implementation, external AI use, real external transfer, real contract processing, real personal data processing, or production use. It is not legal advice, privacy compliance certification, or an operational approval record. Merging this document does not approve an external provider call.

## 1. Document Purpose

This document defines the draft provider boundary for ContractCheck AI v0.2.2 PR-4.

Its purpose is to separate the internal application boundary from the external AI provider boundary, define approval gates for provider, endpoint, and model use, and define request, response, credential, policy-review, and audit constraints before any future external AI integration.

## 2. Scope

This draft covers:

- trust zones
- provider approval gates
- endpoint approval gates
- model approval gates
- credential boundary
- request boundary
- response boundary
- provider policy review boundary
- data use and retention review boundary
- jurisdiction and subprocessors
- cost and usage boundary
- failure and suspension boundary
- provider change review
- prohibited provider paths
- verification requirements
- open items
- follow-up PR connections

This draft does not select or approve any provider, endpoint, model, credential, adapter, external transfer, or production path.

## 3. Current Provider State

- Provider: NOT SELECTED
- Endpoint: NOT SELECTED
- Model: NOT SELECTED
- Zone C to Zone E: NOT APPROVED
- Zone E to Zone C: NOT APPROVED
- Zone E: INACTIVE
- External request: NOT EXECUTED
- External response: NOT RECEIVED

## 4. Trust Zones

The relevant zones are:

- Zone C: Internal Application Core
- Zone D: Internal Persistence
- Zone E: External AI Provider Boundary
- Zone G: Logging and Audit

Current zone state:

- Zone C to Zone E: NOT APPROVED
- Zone E to Zone C: NOT APPROVED
- Zone E: INACTIVE
- Provider: NOT SELECTED
- Endpoint: NOT SELECTED
- Model: NOT SELECTED

Boundary principles:

- Zone E is not an internal trusted zone.
- Provider responses are untrusted.
- Provider responses must not be displayed before validation.
- Provider responses must not be stored before validation.
- Raw provider requests and responses must not be logged.
- Transfer from Zone C to Zone E is default DENY.
- Response from Zone E to Zone C is default UNTRUSTED.
- Zone E failures must not bypass internal safety boundaries.

## 5. Provider Approval Gate

The following items must be reviewed before provider approval:

- provider company and service identity
- official terms of use
- API data use policy
- training use policy
- data retention policy
- deletion policy
- region and processing location
- subprocessors
- public security or compliance documents
- incident notice policy
- API logging policy
- user opt-out availability
- paid and unpaid plan differences
- enterprise, business, developer API differences
- contract-data protection conditions
- service termination and policy change response
- cost structure
- rate limit
- timeout support
- data deletion request availability

Decision status values:

- NOT REVIEWED
- REVIEW REQUIRED
- CONDITIONAL
- APPROVED
- REJECTED
- DEFERRED

Current provider status is `NOT SELECTED`, so no provider is `APPROVED`.

## 6. Endpoint Approval Gate

Each endpoint must be reviewed separately.

Review items:

- endpoint URL
- API version
- request schema
- response schema
- streaming support
- file upload support
- batch support
- logging policy
- timeout support
- retry characteristics
- region support
- retention differences
- model selection method
- tool or function calling support
- external URL access support
- image or file input support

Endpoint principles:

- Provider approval and endpoint approval are separate.
- Provider approval does not automatically approve any endpoint.
- File upload endpoints are prohibited by default.
- Batch endpoints are prohibited or REVIEW REQUIRED by default.
- External URL access is prohibited by default.
- Tool or function calling requires separate approval.
- Streaming requires separate review.
- Endpoint changes require re-approval.

## 7. Model Approval Gate

Each model must be reviewed separately.

Review items:

- model identifier
- model version
- context window
- structured output support
- schema compliance capability
- hallucination risk
- personal data regeneration risk
- tool-use capability
- multimodal support
- data policy differences
- cost
- latency
- support availability
- version pinning availability
- deprecation policy

Model principles:

- Endpoint approval and model approval are separate.
- Model aliases alone are not sufficient; version pinning is required where possible.
- Model changes require review.
- Automatic model fallback is prohibited.
- Automatic fallback to an unapproved model is prohibited.
- Model output is untrusted.
- Structured output still requires validation.

## 8. Credential Boundary

- API keys must not be stored in documents, code, or Git.
- API keys must not be logged.
- API keys must not be exposed to browsers or clients.
- Credentials require a server-side secret store.
- The actual secret storage product is not selected.
- Least-privilege credentials are required.
- Environment-specific credentials are required.
- Development, test, and production credentials must be separated.
- Rotation policy is required.
- Revocation procedure is required.
- On exposure suspicion, credentials must be revoked immediately.
- Credential preparation itself requires separate approval.
- Current API key preparation is not approved.

## 9. Request Boundary

Requests from Zone C to Zone E must satisfy:

- provider approved
- endpoint approved
- model approved
- credential approved
- provider adapter implemented and reviewed
- outbound allowlist passed
- payload schema passed
- residual PII result is 0
- actual data scope approved
- cost approved
- timeout policy approved
- retry policy approved
- final user approval obtained
- audit metadata can be created

Any missing approval results in BLOCK, REVIEW REQUIRED, or NOT EXECUTED.

## 10. Response Boundary

Provider response handling must include:

1. Receive response
2. Confirm transport success
3. Confirm content type
4. Confirm response size
5. Validate schema
6. Validate required fields
7. Detect unknown fields
8. Validate `reference_id`
9. Validate `clause_id`
10. Detect duplicate results
11. Detect prohibited fields
12. Detect personal data regeneration
13. Detect contract source regeneration
14. Mark prompt-injection indicators for review
15. Run output safety checks
16. Normalize confidence
17. Validate expert review recommendation
18. Decide storage candidate status
19. Decide display candidate status
20. Decide BLOCK or REVIEW

Response principles:

- Provider response is always UNTRUSTED.
- Passing schema validation alone does not make a response safe.
- `reference_id` mismatch results in BLOCK or REVIEW.
- Regenerated source text or personal data results in BLOCK.
- Raw response storage is prohibited.
- Raw response logging is prohibited.
- Output safety validation is required before user display.

## 11. Provider Policy Review Boundary

The following items require separate policy review:

- provider training use
- abuse monitoring use
- API logging
- request retention
- response retention
- human review possibility
- deletion request availability
- opt-out availability
- account tier differences
- region differences
- subprocessors
- backup retention possibility

Because no provider is selected, concrete provider policy terms are not fixed in this document.

Current policy approval state:

- Provider policy review: REVIEW REQUIRED
- Data retention approval: NOT APPROVED
- Training use approval: NOT APPROVED
- Human review approval: NOT APPROVED

## 12. Jurisdiction and Subprocessor Boundary

Before provider approval, the project must review:

- processing locations
- cross-border transfer implications
- subprocessors
- subprocessor change notice
- data center region options
- account-tier differences
- contractual data processing terms

This document does not approve a jurisdiction, region, or subprocessor list.

## 13. Cost and Usage Boundary

Before any future call, the project must define:

- cost limit
- rate limit
- usage quota
- user-level cost boundary
- retry cost boundary
- duplicate call prevention
- emergency stop condition
- monitoring metadata that does not include body text or personal data

No cost-incurring external call is approved in this PR.

## 14. Failure and Suspension Boundary

Provider failures must safe-fail.

- Provider unavailable: NOT EXECUTED or BLOCK
- Timeout: BLOCK or REVIEW REQUIRED
- Rate limit: BLOCK or REVIEW REQUIRED
- Schema failure: BLOCK
- Unknown response field: BLOCK or REVIEW REQUIRED
- Reference mismatch: BLOCK or REVIEW REQUIRED
- Policy review expired: BLOCK
- Provider approval revoked: BLOCK
- Endpoint approval revoked: BLOCK
- Model approval revoked: BLOCK
- Credential exposure suspected: SECURITY EVENT and BLOCK

The system must not automatically switch to another provider, endpoint, or model.

## 15. Provider Change Review

Approval withdrawal or re-review is required when any of the following changes occur:

- terms of use change
- data use policy change
- retention policy change
- training use policy change
- endpoint change
- model change
- region change
- subprocessor change
- incident notice
- security certification loss
- API logging policy change
- pricing policy change
- rate limit change
- service termination
- regulatory environment change

Possible states:

- SUSPENDED
- REVOKED
- RE-REVIEW REQUIRED
- BLOCKED

If approval is withdrawn, external calls must be blocked automatically.

## 16. Prohibited Provider Paths

The following paths are explicitly prohibited:

- internal D1 data to provider
- original contract file to provider
- full extracted text to provider
- unmasked clause data to provider
- detected personal data to provider
- residual PII to provider
- unapproved payload to provider
- unapproved endpoint request
- unapproved model request
- API key to client
- API key to log
- raw provider request to permanent storage
- raw provider response to permanent storage
- provider response to user without validation
- provider response to normalized result without schema validation
- provider failure to automatic unsafe fallback
- provider policy change to continued execution without review
- provider approval revoked to continued execution
- unknown provider field to internal storage
- external URL tool access without approval
- file upload endpoint without approval

## 17. Verification Requirements

Before any provider integration can move forward, future work must verify:

- provider approval record exists
- endpoint approval record exists
- model approval record exists
- credential approval exists
- outbound allowlist is enforced
- response schema validation exists
- output safety validation exists
- raw request storage is blocked
- raw response storage is blocked
- raw request logging is blocked
- raw response logging is blocked
- provider policy version is recorded
- endpoint and model version are recorded
- provider change review process exists
- safe-fail behavior exists

## 18. Open Items

- Provider selection
- Endpoint selection
- Model selection
- API key storage product
- Credential rotation and revocation procedure
- Provider policy review cadence
- Data retention approval
- Human review approval
- Cost and rate limit values
- Timeout value
- Retry and backoff policy
- Provider adapter interface
- Response normalization schema

## 19. Follow-up PR Connections

| Follow-up PR | Connection |
|---|---|
| PR-5 | Access control, failure handling, output safety, user notice, and security test strategy |
| PR-6 | Integrated review, unresolved items, final design decision, and v0.2.2 closeout |
| v0.4 | API and DB schema |
| v0.5 | Provider adapter and pipeline implementation |
| v0.6 | Secret management and deployment configuration |

## 20. Approval State

- Provider boundary approval: Not approved
- Provider approval: Not approved
- Endpoint approval: Not approved
- Model approval: Not approved
- Credential approval: Not approved
- Provider adapter implementation approval: Not approved
- External AI use approval: Not granted
- Zone C to Zone E approval: Not approved
- Zone E to Zone C approval: Not approved
- Real external transfer approval: Not approved
- Real contract use approval: Not approved
- Real personal data use approval: Not approved
- Production use approval: Not approved
