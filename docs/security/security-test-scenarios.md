# ContractCheck AI Security Test Scenarios

- Status: Draft
- Approval status: Review required / Not approved
- Version: v0.2.2 PR-5
- Implementation status: Not started
- Authentication implementation: Not started
- Authorization implementation: Not started
- Role model approval: Not approved
- Provider selection: Not selected
- Endpoint selection: Not selected
- Model selection: Not selected
- External AI use approval: Not granted
- Real external transfer: NOT EXECUTED
- Real contract use: Not approved
- Real personal data use: Not approved
- Production use: Not approved

This document is a design draft, not an approval record. It does not execute security tests, approve authentication or authorization implementation, approve external AI use, approve real data use, or approve production use. It is not legal advice, privacy compliance certification, security certification, or an operational approval record.

## 1. Document Purpose

This document defines draft security test scenarios for ContractCheck AI v0.2.2 PR-5.

The purpose is to identify expected security-test coverage before implementation, using synthetic data only and preserving the no-real-data and no-external-transfer boundaries.

## 2. Scope

This draft covers:

- test design status
- test data rules
- role and access tests
- authentication tests
- authorization and ownership tests
- session tests
- PII and masking tests
- storage, deletion, and logging tests
- external transfer tests
- provider response validation tests
- output safety tests
- user notice tests
- security regression tests
- stop conditions
- open items
- follow-up PR connections

No actual test execution is approved in this PR.

## 3. Current Test State

- Test scenario status: DRAFT
- Test execution: NOT EXECUTED
- Test automation: NOT IMPLEMENTED
- Real contract use: NOT APPROVED
- Real personal data use: NOT APPROVED
- External provider call: NOT EXECUTED
- Provider response fixture use: SYNTHETIC ONLY
- Security test approval: NOT APPROVED

## 4. Test Data Rules

- Use synthetic fixtures only.
- Do not use real contracts.
- Do not use real personal data.
- Do not use live provider calls.
- Do not use API keys.
- Do not include secrets.
- Do not include local absolute paths.
- Do not log body text or personal data.
- Synthetic placeholders must be obvious and non-real.
- Any suspected real data stops the test.

## 5. Access Control Tests

Scenarios:

- anonymous upload attempt
- anonymous analysis request
- anonymous result access
- authenticated user own result access
- authenticated user other user's result access
- reviewer unassigned result access
- administrator unrestricted body access attempt
- security operator contract body access attempt
- service role used for user request
- revoked permission reused
- direct URL resource access

Expected results:

- DENY or BLOCK for unauthorized access
- minimal data existence disclosure
- `CROSS_USER_ACCESS_BLOCKED` or `AUTHORIZATION_DENIED` event candidate
- no D1 source exposure
- security event candidate when access is suspicious

## 6. Authentication Tests

Scenarios:

- missing authentication
- invalid credentials
- expired session
- logout then session reuse
- account blocked then session reuse
- authentication failure message comparison
- credential logging attempt
- access token logging attempt
- refresh token logging attempt
- administrator account without stronger authentication candidate

Expected results:

- AUTHENTICATION REQUIRED, ACCESS DENIED, SESSION INVALID, BLOCK, or SECURITY HOLD candidate
- no account existence disclosure
- no credential logging
- no token logging
- no password, token, body, or personal data exposure
- audit event candidate generated with minimal metadata only
- no implementation claim

## 7. Authorization and Ownership Tests

Scenarios:

- valid authentication but wrong owner
- role not approved
- request action outside role
- document_id guessing
- frontend-only permission bypass attempt
- stale permission cache
- administrator bypass attempt
- reviewer unassigned resource access
- security operator D1 access attempt

Expected results:

- DENY or BLOCK
- server-side authorization required
- ownership check required
- minimal error information
- audit event candidate without body or PII

## 8. Session Tests

Scenarios:

- expired session reuse
- idle session reuse
- logout then reuse
- permission revoked while session exists
- account blocked while session exists
- security hold while session exists
- session fixation attempt
- CSRF protection missing candidate

Current implementation is not started, so execution state remains NOT IMPLEMENTED or NOT EXECUTED.

## 9. PII and Masking Tests

Synthetic scenarios:

- synthetic name placeholder
- synthetic resident registration number format placeholder
- synthetic phone placeholder
- synthetic email placeholder
- synthetic address placeholder
- synthetic account placeholder
- synthetic card placeholder
- mixed-format personal data placeholder
- personal data split across text
- residual PII after masking
- masking failure
- PII detection failure

Expected results:

- residual PII found becomes BLOCK
- detected personal data is not externally transferred
- raw personal data is not logged
- temporary data deletion candidate is created
- `RESIDUAL_PII_BLOCKED` or `MASKING_FAILED` event candidate

Do not add real personal data examples.

## 10. Storage, Deletion, and Logging Tests

Scenarios:

- D1 permanent storage attempt
- D1 backup attempt
- original contract body log attempt
- personal data audit log attempt
- raw provider request storage attempt
- raw provider response storage attempt
- temporary data preserved after success
- temporary data preserved after failure
- deletion verification failure
- deletion failure treated as success
- operational log write failure
- audit event write failure

Expected results:

- BLOCK
- SECURITY HOLD candidate
- silent success prohibited
- deletion failure escalation candidate
- prohibited fields are not logged

## 11. External Transfer Tests

Scenarios:

- provider not approved
- endpoint not approved
- model not approved
- field outside allowlist included
- unknown field included
- D1 data included
- original contract included
- full extracted text included
- residual PII included
- `reference_id` missing
- `source_hash` unavailable
- cost approval missing
- timeout policy missing
- retry policy missing
- final user approval missing
- audit event cannot be created

Expected results:

- NOT EXECUTED
- BLOCK or APPROVAL REQUIRED
- no actual provider call
- `EXTERNAL_AI_NOT_EXECUTED` event candidate
- no raw payload storage

## 12. Provider Response Tests

Use synthetic response fixtures only. No live provider call is approved.

Scenarios:

- schema mismatch
- missing required field
- unknown field
- `reference_id` mismatch
- `clause_id` mismatch
- duplicate result
- personal data regeneration
- contract source regeneration
- confidence out of range
- legal-advice-like wording
- unsupported assertion
- prompt injection indicator
- excessive response size
- invalid content type

Expected results:

- BLOCKED OUTPUT
- REVIEW REQUIRED
- raw response not stored
- user display prohibited
- `OUTPUT_SCHEMA_BLOCKED` or `OUTPUT_REFERENCE_BLOCKED` event candidate

## 13. Output Safety Tests

Scenarios:

- certainty wording that a clause is safe
- contract validity certainty
- litigation outcome prediction
- expert review suppressed for high-impact result
- confidence shown as 100% guarantee
- risk assertion without reference
- personal data regenerated in result
- contract source text regenerated in result
- legal advice notice missing
- user notice missing

Expected results:

- BLOCK or REVIEW REQUIRED
- USER NOTICE REQUIRED
- EXPERT REVIEW RECOMMENDED
- NOT DISPLAYED

## 14. User Notice Tests

The future UI must be designed so notices can appear around:

- upload
- analysis start
- result view
- high-impact result
- expert review recommendation
- download or sharing
- error state

Notices to verify:

- AI reference information
- not legal advice
- not an expert replacement
- omissions and errors possible
- confidence is not a guarantee
- expert review may be needed before important decisions
- external AI not executed in the current draft state
- real data use not approved in this design phase

The current UI is not implemented.

## 15. Security Regression Tests

Future changes to PR-1 through PR-5 policies must preserve:

- D1 permanent storage prohibition
- D1 external transfer prohibition
- personal data logging prohibition
- raw provider request and response storage prohibition
- residual PII blocking
- allowlist field blocking
- provider, endpoint, and model approval separation
- unauthorized access blocking
- cross-user access blocking
- output personal data regeneration blocking
- failed validation not displayed to users
- real external transfer NOT EXECUTED unless separately approved
- no real data use in design tests

## 16. Test Stop Conditions

Security tests must stop when any of the following occurs:

- suspected real personal data found
- suspected real contract found
- credential exposed
- external transfer could occur
- real provider call could occur
- unauthorized file access
- test log contains body or personal data
- deletion failure
- security incident suspected
- unexpected network connection
- approval scope or test data uncertainty
- Git secret detection

Stop states:

- BLOCK
- SECURITY HOLD
- ESCALATION REQUIRED
- TEST DATA INVALID

## 17. Open Items

- Test fixture format
- Synthetic placeholder catalog
- Security test runner design
- CI execution policy
- Secret scanning integration
- Network isolation policy
- Expected JSON schema for test scenarios
- User notice verification method
- Output safety test oracle
- Access-control test harness

## 18. Follow-up PR Connections

| Follow-up PR | Connection |
|---|---|
| PR-6 | Integrated review, unresolved items, final design decision, and v0.2.2 closeout |
| v0.3 | UI notice placement and error UX |
| v0.4 | Authentication, authorization, session, API, and DB schema |
| v0.5 | Pipeline implementation, output safety validation, and security test automation |
| v0.6 | CI/CD, secret management, and deployment security |

## 19. Approval State

- Security test scenario approval: Not approved
- Test execution approval: Not approved
- Test automation approval: Not approved
- Real data test approval: Not approved
- External provider test approval: Not approved
- Production security approval: Not approved
