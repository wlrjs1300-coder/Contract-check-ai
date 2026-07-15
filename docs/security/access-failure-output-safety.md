# ContractCheck AI Access, Failure, and Output Safety

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

This document is a design draft, not an approval record. It does not approve authentication or authorization implementation, role model approval, external AI use, real external transfer, real contract processing, real personal data processing, security test execution, or production use. It is not legal advice, privacy compliance certification, security certification, or an operational approval record. Merging this document does not approve implementation or operation.

## 1. Document Purpose

This document defines the draft access control, failure handling, output safety, user notice, and security-test boundary for ContractCheck AI v0.2.2 PR-5.

Its purpose is to connect the data, storage, logging, external transfer, and provider boundary drafts to the user-visible and operator-visible safety decisions that must exist before implementation.

## 2. Scope

This draft covers:

- role model candidates
- access scope by role
- permission decision states
- authentication, authorization, and session boundaries
- administrator, operator, and reviewer access limits
- data access controls
- log and audit access controls
- failure status model
- fail-closed principles
- input, PII, masking, storage, deletion, logging, external transfer, and provider response failures
- output safety validation
- display eligibility decisions
- confidence handling
- expert review recommendation handling
- user notice requirements
- prohibited access paths
- prohibited output paths
- audit event candidates
- unresolved items
- follow-up PR connections

This draft does not implement authentication, authorization, sessions, role permissions, provider calls, provider adapters, output safety code, UI notices, tests, or production controls.

## 3. Current Approval State

- Authentication implementation: NOT STARTED
- Authorization implementation: NOT STARTED
- Session implementation: NOT STARTED
- Role model: DRAFT / NOT APPROVED
- Administrator permissions: NOT APPROVED
- Security operator permissions: NOT APPROVED
- Reviewer permissions: NOT APPROVED
- External AI use: NOT APPROVED
- External transfer: NOT EXECUTED
- Real data use: NOT APPROVED
- Security tests: NOT EXECUTED
- Production use: NOT APPROVED

## 4. Default Safety Principles

- Default access policy is DENY.
- Only explicitly approved roles and permissions may become access candidates.
- Authentication success alone does not allow access to all data.
- Authorization must be evaluated for every request.
- Role and resource ownership must be checked together.
- Administrator privileges must not imply unrestricted data access.
- Operator access and security-review access must be separated.
- Audit log access requires separate approval.
- Direct user access to original contract body text is prohibited by default.
- Direct access to D1 data is prohibited by default.
- Least privilege is required.
- Only minimum data needed for the task may be shown.
- Ambiguous permission results must become BLOCK or REVIEW REQUIRED.
- Failures must fail closed.
- Exceptions must not be shown as successful analysis results.
- Validation failures must be shown to the user as safe error states.
- Provider responses are always UNTRUSTED.
- Output must not be displayed before output safety validation.
- Legal-advice-like output is prohibited.
- Real implementation and production application remain not approved.

## 5. Role Model Candidate

The following roles are design candidates only.

| Role | Purpose | Authentication required | Allowed data scope | Prohibited data scope | Allowed actions | Prohibited actions | Approval status | Implementation status |
|---|---|---|---|---|---|---|---|---|
| Anonymous | Unauthenticated visitor | No | Public static information only | Uploads, analysis, history, results, logs, D1 data | View public project or service entry points only | Upload contract, request analysis, view result, view history | PROHIBITED | NOT STARTED |
| Authenticated User | Regular signed-in user | Yes | Own metadata and own approved display results | Other users' resources, D1 raw source, logs, admin data | Upload candidate document, request permitted analysis, view own safe result candidate | Cross-user access, raw D1 access, admin action | PROPOSED | NOT STARTED |
| Document Owner | Owner of a submitted document | Yes | Own resource metadata, status, approved display result | Raw D1 source unless separately approved by policy | View own status and safe result, request deletion where allowed | View another owner's data, bypass safety checks | PROPOSED | NOT STARTED |
| Reviewer | Assigned review role for limited review tasks | Yes | Assigned review target only | Unassigned user data, raw D1 by default, credentials, provider raw payload | Review flagged output or policy exception candidate | Bulk access, cross-user browsing, provider credential access | REVIEW REQUIRED | NOT STARTED |
| Administrator | System administration role | Yes | System configuration metadata required for administration | User contract body, personal data, raw provider payload, raw logs | Manage system-level settings after approval | Unrestricted product data access, silent impersonation | REVIEW REQUIRED | NOT STARTED |
| Security Operator | Security event response role | Yes | Security event code, state, minimal metadata | Contract body, personal data, provider raw body | Review security holds and event state | Read source text or personal data by default | REVIEW REQUIRED | NOT STARTED |
| System Service | Internal service actor | Service authentication required | Fixed service-scoped data only | User-visible broad access, interactive admin action | Execute approved pipeline step | Use user-facing privileges, bypass policy gates | REVIEW REQUIRED | NOT STARTED |
| External Provider | External processing boundary, not a trusted internal role | Not an internal user | Approved outbound candidate only if all gates pass | D1 data, raw source, residual PII, unapproved payload | No internal access | Internal access, user data browsing, storage access | PROHIBITED | NOT IMPLEMENTED |

Role assignment itself must be auditable. The current role model is Draft / Not approved.
Product data access is prohibited for Anonymous users. External Provider is not an internal trusted role and must not receive internal access privileges.

## 6. Access Scope By Role

- Anonymous users cannot upload, request analysis, view history, or view results.
- Authenticated users may only access resources they own or are explicitly assigned to.
- Document owners do not automatically receive raw D1 source access after upload.
- Reviewers may access only assigned review targets.
- Administrators may manage system state but do not receive unrestricted user data access.
- Security operators focus on security event codes and state, not body text.
- System services may only use fixed service permissions.
- External providers are not internal trusted users.
- Every role-based permission requires later approval and implementation.

## 7. Permission Decision States

The permission decision states are:

- ALLOW CANDIDATE
- DENY
- BLOCK
- REVIEW REQUIRED
- AUTHENTICATION REQUIRED
- AUTHORIZATION REQUIRED
- OWNERSHIP CHECK REQUIRED
- ROLE NOT APPROVED
- SESSION INVALID
- SECURITY HOLD

These are design candidates only. No actual permission system exists in this PR.

The following cases must resolve to DENY or BLOCK candidates:

- no authentication
- invalid session
- role not approved
- ownership mismatch
- requested resource scope exceeded
- administrator privilege abuse suspected
- audit log unauthorized access
- D1 data access attempt
- another user's contract access attempt
- unapproved storage lookup
- policy version mismatch
- security incident in progress

## 8. Authentication Boundary

- Authentication method is not selected.
- Specific authentication product is not selected.
- Password policy is undecided.
- MFA scope is undecided.
- SSO support is undecided.
- Account lock policy is undecided.
- Authentication failure count is undecided.
- Authentication failure messages must not reveal account existence.
- Credential logging is prohibited.
- Password logging is prohibited.
- Access token logging is prohibited.
- Refresh token logging is prohibited.
- Authorization checks are still required after authentication succeeds.
- Administrator and operator accounts require stronger authentication candidates.
- Authentication implementation is not started.

## 9. Authorization Boundary

Authorization must follow this draft sequence:

1. Receive request
2. Confirm authentication state
3. Confirm session state
4. Confirm role
5. Confirm role approval status
6. Confirm requested action
7. Confirm target resource
8. Confirm ownership
9. Confirm data classification
10. Confirm policy version
11. Confirm security hold state
12. Confirm least-privilege scope
13. Confirm audit event can be created
14. Decide ALLOW CANDIDATE or BLOCK

Authorization principles:

- Possession of a URL or document_id must not grant access.
- Frontend hiding is not a permission control.
- Server-side authorization is required.
- Permission cache use requires revalidation.
- Administrator bypass is prohibited by default.
- Service roles must not be used for regular user requests.
- Unauthorized access responses must minimize data-existence disclosure.

## 10. Session Boundary

- Raw session identifiers must not be logged.
- Session expiration is required.
- Exact expiration time is undecided.
- Idle timeout is required.
- Exact idle timeout is undecided.
- Session reuse after logout is prohibited.
- Existing sessions must be re-evaluated after permission changes.
- Sessions must be invalidated after account blocking.
- Security incidents may require immediate session revocation.
- Session fixation protection is required.
- CSRF protection is a required future review item.
- Cookie setting criteria require later review.
- Session store product is not selected.

## 11. Administrator and Operator Permissions

- Administrator access is for system management, not unrestricted user data reading.
- Administrator actions require separate audit metadata.
- Administrator access to D1 data is prohibited by default.
- Security operator access is for event response, not contract review.
- Security operators may view event codes and state candidates only.
- Operator access to contract body or personal data requires separate review and is not approved.
- Reviewer, administrator, and security operator roles must not be collapsed into one unrestricted role.
- Privileged role assignment and revocation require audit events.

## 12. Reviewer Permissions

- Reviewer access is not automatically available.
- Reviewer assignment must be explicit.
- Reviewer access is limited to assigned review targets.
- Reviewer access to raw source or D1 data remains prohibited by default.
- Reviewer actions must not bypass output safety validation.
- Reviewer access is a future policy and product decision, not implemented here.

## 13. Data Access Control

| Data item | Data class | User access | Reviewer access | Administrator access | Security operator access | Service access | Required control | Decision status |
|---|---|---|---|---|---|---|---|---|
| Original contract file | D1 | PROHIBITED by default | PROHIBITED by default | PROHIBITED by default | PROHIBITED | REVIEW REQUIRED | Deletion and D1 access policy | PROHIBITED |
| Extracted text | D1 | PROHIBITED by default | PROHIBITED by default | PROHIBITED by default | PROHIBITED | REVIEW REQUIRED | D1 policy and masking | PROHIBITED |
| Unmasked clause data | D1 | PROHIBITED | PROHIBITED | PROHIBITED | PROHIBITED | REVIEW REQUIRED | Masking and residual checks | PROHIBITED |
| Detected personal data | D1 | PROHIBITED | PROHIBITED | PROHIBITED | PROHIBITED | REVIEW REQUIRED | No raw source exposure | PROHIBITED |
| Masked clause text | D2 | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | PROHIBITED | REVIEW REQUIRED | residual 0 and allowlist | REVIEW REQUIRED |
| Normalized analysis result | D2/D3 | ALLOWED CANDIDATE for owner after safety checks | REVIEW REQUIRED | REVIEW REQUIRED | PROHIBITED | REVIEW REQUIRED | output safety and ownership | ALLOWED CANDIDATE |
| Document metadata | D3 | ALLOWED CANDIDATE for owner | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | ownership and minimization | ALLOWED CANDIDATE |
| Operational log | D2/D3 | PROHIBITED | PROHIBITED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | no body or PII | REVIEW REQUIRED |
| Audit log | D3 | PROHIBITED | PROHIBITED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | audit access approval | REVIEW REQUIRED |
| Security event log | D3 | PROHIBITED | PROHIBITED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | event-code minimization | REVIEW REQUIRED |
| Deletion metadata | D3 | ALLOWED CANDIDATE for owner where safe | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | minimal fields only | REVIEW REQUIRED |
| External transfer metadata | D3 | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | no raw payload | REVIEW REQUIRED |

Data access policy approval is not implementation approval.

## 14. Log and Audit Access Control

- Logs must not include body text or personal data.
- Audit access requires a separate permission.
- Operational log access and audit log access must be separated.
- Security event logs expose minimal state, not source text.
- Log search must not become a backdoor for D1 access.
- Raw provider request and response logs are prohibited.
- Credential and session logs are prohibited.
- Log export is not approved.

## 15. Failure Status Model

| Failure status | Meaning | User-visible | Retry allowed | Data retention action | Logging action | Escalation | Decision status |
|---|---|---|---|---|---|---|---|
| SAFE FAILURE | Controlled non-success state | Yes, as safe error | REVIEW REQUIRED | Follow PR-3 policy | Code only | No by default | PROPOSED |
| BLOCK | Safety boundary violation | Limited message | No by default | Preserve minimal metadata | Code only | REVIEW REQUIRED | PROPOSED |
| REVIEW REQUIRED | Ambiguous result | Limited message | Not automatic | Preserve minimal metadata | Code only | Yes | PROPOSED |
| RETRY CANDIDATE | Potentially recoverable failure | Maybe | Only after policy approval | Preserve minimal metadata | Code only | No by default | REVIEW REQUIRED |
| ESCALATION REQUIRED | Repeated or serious failure | Limited message | No | Preserve minimal metadata | Code only | Yes | PROPOSED |
| SECURITY HOLD | Security-sensitive condition | Limited message | No | Freeze minimal state | Security event only | Yes | PROPOSED |
| USER ACTION REQUIRED | User must re-upload, re-authenticate, or correct input | Yes | User initiated only | Follow PR-3 policy | Code only | No by default | PROPOSED |
| NOT IMPLEMENTED | Feature not implemented | Maybe | No | None | Code only | No | CURRENT |
| NOT EXECUTED | Step intentionally not run | Maybe | No | Minimal metadata only | Code only | No | CURRENT |
| PERMANENT FAILURE CANDIDATE | Failure may not be recoverable | Limited message | No by default | Follow deletion policy | Code only | REVIEW REQUIRED | PROPOSED |

Failures must not be converted into successful analysis states.

## 16. Fail-Closed Principles

- Safety boundary failures block further processing.
- Ambiguous permissions block access.
- Ambiguous output validation blocks display.
- Missing provider approval keeps external transfer NOT EXECUTED.
- Missing output safety validation keeps result NOT DISPLAYED.
- Missing audit event may block or require review.
- Repeated failures require escalation review.
- Security incidents require SECURITY HOLD candidates.
- User-facing messages must not expose raw exception details.

## 17. Input Processing Failures

Input processing failures include:

- unsupported file format
- file size exceeded
- file corruption
- text extraction failure
- clause splitting failure
- schema creation failure

Expected handling:

- default decision: SAFE FAILURE, BLOCK, or USER ACTION REQUIRED
- user-visible state: safe error only
- retry: user initiated only where policy allows
- deletion action: follow PR-3 deletion policy
- logging: code and metadata only
- escalation: only when repeated or security-sensitive

## 18. PII and Masking Failures

PII and masking failures include:

- PII detection failure
- masking failure
- residual scan failure
- residual PII found
- data classification failure

Expected handling:

- residual PII found must become BLOCK or SECURITY HOLD candidate.
- detected personal data must not be logged.
- raw personal data must not be shown to users.
- external transfer must remain NOT EXECUTED.
- temporary data deletion must follow PR-3 policy.
- audit events may record code only.

## 19. Storage, Deletion, and Logging Failures

Storage, deletion, and logging failures include:

- temporary storage failure
- prohibited-path storage attempt
- deletion failure
- deletion verification failure
- backup deletion metadata failure
- operational log write failure
- audit event creation failure

Expected handling:

- prohibited storage attempts must become BLOCK or SECURITY HOLD candidates.
- deletion failure must not be reported as success.
- log failure must not expose body text or personal data.
- repeated deletion or audit failure requires escalation.
- raw provider request and response storage is prohibited.

## 20. External Transfer Failures

External transfer failures include:

- provider not approved
- endpoint not approved
- model not approved
- allowlist violation
- schema violation
- cost approval missing
- timeout policy missing
- retry policy missing
- final user approval missing
- provider timeout
- provider transport failure
- provider rate limit
- provider authentication failure
- provider policy review expired
- provider approval revoked

Current external AI state is not approved, so actual execution remains NOT EXECUTED. Provider timeout and rate-limit cases are design scenarios, not recorded execution failures.

## 21. Provider Response Validation Failures

Provider response validation failures include:

- response parsing failure
- response schema failure
- missing required field
- unknown field
- `reference_id` mismatch
- `clause_id` mismatch
- duplicate result
- personal data regeneration
- contract source regeneration
- confidence value out of range
- legal-advice-like expression
- unsupported assertion without evidence
- prompt-injection indicator
- excessive response size
- invalid content type

Expected handling:

- output becomes BLOCKED OUTPUT or REVIEW REQUIRED.
- raw response is not stored.
- user display is prohibited.
- audit event stores code only.

## 22. Output Safety Validation

Output safety validation must include:

1. Receive normalized result candidate
2. Validate schema
3. Validate required fields
4. Detect unknown fields
5. Validate `reference_id`
6. Validate `clause_id`
7. Confirm document ownership link
8. Detect duplicate results
9. Detect prohibited fields
10. Detect personal data regeneration
11. Detect contract source regeneration
12. Detect excessive certainty language
13. Detect legal-advice-like language
14. Detect unsupported risk assertion
15. Confirm reference evidence linkage
16. Validate confidence value
17. Normalize confidence range
18. Validate expert review recommendation
19. Confirm user notice requirement
20. Decide final display eligibility

Schema passing alone does not make output displayable.

## 23. Display Eligibility Decision

Display decision states are:

- DISPLAY CANDIDATE
- BLOCKED OUTPUT
- REVIEW REQUIRED
- EXPERT REVIEW RECOMMENDED
- USER NOTICE REQUIRED
- INVALID OUTPUT
- NOT DISPLAYED

Display principles:

- `reference_id` mismatch blocks or requires review.
- Personal data regeneration blocks display.
- Contract source regeneration blocks display.
- Legal certainty language is prohibited.
- Statements that a clause is safe are prohibited.
- Contract validity determination is prohibited.
- Litigation outcome prediction is prohibited.
- Expert review recommendation must be explicit when required.
- Failed validation must not be displayed to users.
- Raw provider response must not be displayed.

## 24. Confidence Handling

- Confidence is not a legal accuracy score.
- Confidence is not a guarantee of model reliability.
- Confidence alone must not decide safety.
- Reference validation and schema validation are also required.
- Confidence range validation is required.
- Out-of-range or invalid values become INVALID OUTPUT.
- Specific threshold values are undecided.
- Missing confidence becomes REVIEW REQUIRED candidate.
- High confidence does not remove expert review need.
- User-facing explanation is required if confidence is displayed.
- Whether to display percentage values is undecided.

## 25. Expert Review Recommendation

Expert review recommendation is a user-facing safety signal. It is not legal advice, does not connect the user to an expert, and does not decide legality, validity, enforceability, payment duty, dismissal result, refund result, or dispute outcome.

The candidate states are:

| Review status | Meaning | Typical trigger | User-visible label | Action restriction | Approval status | Implementation status |
|---|---|---|---|---|---|---|
| NOT REQUIRED | No additional expert review condition was found by the current draft checks. This does not mean the clause or contract is safe. | No high-impact trigger candidate, references pass, confidence candidate is valid | No expert review recommendation displayed | None in this draft | PROPOSED | DESIGN ONLY |
| RECOMMENDED | Expert review should be suggested to the user, but the user action is not automatically blocked by this draft. | Ambiguous reference, material meaning uncertainty, moderate legal or financial consequence candidate | Expert review recommended | Warning candidate only | PROPOSED | DESIGN ONLY |
| STRONGLY RECOMMENDED | Stronger recommendation should be shown before important decisions, download, sharing, or reliance. | High-impact clause candidate, multiple trigger combination, conflicting model result, high uncertainty | Expert review strongly recommended | Strong warning candidate; actual restriction undecided | REVIEW REQUIRED | DESIGN ONLY |
| REQUIRED BEFORE ACTION | Expert review is required before a specific follow-up action candidate. This is a design candidate, not an implemented enforcement rule. | Contract signing, termination, payment, refund, dismissal, or dispute action candidate | Expert review required before action | Blocking candidate; final enforcement rule undecided | REVIEW REQUIRED | DESIGN ONLY |
| REVIEW STATUS NOT DECIDED | The evidence is insufficient or validation did not finish, so the review status must not be shown as normal. | Missing confidence, invalid confidence, incomplete validation, unsupported document type | Review status not decided | Do not present as normal result | REVIEW REQUIRED | NOT IMPLEMENTED |

High-impact trigger candidates are tracked separately from the final recommendation state:

| Trigger | Default review status candidate | Reason | User-visible requirement | Blocking candidate | Decision status |
|---|---|---|---|---|---|
| Missing confidence | REVIEW STATUS NOT DECIDED | Confidence cannot support display decision | Explain that review status is not decided | Yes | REVIEW REQUIRED |
| Confidence error or out-of-range confidence | REVIEW STATUS NOT DECIDED | Invalid confidence can mislead users | Explain validation problem without numeric reliance | Yes | REVIEW REQUIRED |
| Incomplete reference_id validation | REVIEW STATUS NOT DECIDED | Result may not map to source clause | Explain reference validation issue | Yes | REVIEW REQUIRED |
| Possible clause_id mismatch | REVIEW STATUS NOT DECIDED | Result may point to the wrong clause | Explain clause mapping uncertainty | Yes | REVIEW REQUIRED |
| Insufficient reference evidence | RECOMMENDED | Supporting source is incomplete | Show expert review recommendation | No by default | PROPOSED |
| High-impact clause candidate | STRONGLY RECOMMENDED | User may rely on important contract meaning | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Damage compensation clause | STRONGLY RECOMMENDED | Financial consequence may be material | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Penalty clause | STRONGLY RECOMMENDED | Penalty obligation may be material | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Automatic renewal clause | STRONGLY RECOMMENDED | Renewal timing may affect obligations | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Termination restriction clause | STRONGLY RECOMMENDED | Termination limits may affect important actions | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Unusual intermediate termination condition | STRONGLY RECOMMENDED | Early termination meaning may be uncertain | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Liability limitation clause | STRONGLY RECOMMENDED | Liability allocation may be material | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Indemnity clause | STRONGLY RECOMMENDED | Indemnity scope may create financial risk | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Personal data processing clause | STRONGLY RECOMMENDED | Privacy obligations may be involved | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Personal data third-party provision clause | STRONGLY RECOMMENDED | Third-party data transfer may be involved | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Governing law clause | RECOMMENDED | Applicable rule context may matter | Show expert review recommendation | No by default | PROPOSED |
| Dispute resolution clause | STRONGLY RECOMMENDED | Forum or process may affect dispute response | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Arbitration clause | STRONGLY RECOMMENDED | Dispute path may materially change | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Contract validity interpretation needed | REQUIRED BEFORE ACTION | The result may require legal interpretation before action | Require expert review before follow-up action candidate | Candidate only | REVIEW REQUIRED |
| Waiver of rights clause | STRONGLY RECOMMENDED | User rights may be reduced | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Unilateral change clause | STRONGLY RECOMMENDED | One party may change terms | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Large payment or refund restriction clause | STRONGLY RECOMMENDED | Payment or refund consequence may be material | Show stronger expert review warning | Candidate only | REVIEW REQUIRED |
| Conflicting model results | REVIEW STATUS NOT DECIDED | Result consistency is not established | Explain review is needed before relying on result | Yes | REVIEW REQUIRED |
| Dependency uncertainty | REVIEW STATUS NOT DECIDED | Upstream validation or data dependency is unclear | Explain validation uncertainty | Yes | REVIEW REQUIRED |
| User understanding risk | RECOMMENDED | User may misunderstand the output as a decision | Show expert review recommendation and limitation notice | No by default | PROPOSED |
| Unverified document type | REVIEW STATUS NOT DECIDED | Support scope is not confirmed | Do not present as normal result | Yes | REVIEW REQUIRED |
| Support scope or contract type uncertainty | REVIEW STATUS NOT DECIDED | Supported contract type is unclear | Do not present as supported analysis | Yes | REVIEW REQUIRED |
| Legal interpretation wording needed | REQUIRED BEFORE ACTION | A legal interpretation may be required before action | Require expert review before follow-up action candidate | Candidate only | REVIEW REQUIRED |
| Output validation incomplete | REVIEW STATUS NOT DECIDED | Safety validation did not finish | Do not present as normal result | Yes | REVIEW REQUIRED |
| Data classification uncertainty | REVIEW STATUS NOT DECIDED | Data handling class may be unclear | Explain validation uncertainty | Yes | REVIEW REQUIRED |
| Conflict with deletion or retention policy | REVIEW STATUS NOT DECIDED | Handling may conflict with storage policy | Explain that review is needed | Yes | REVIEW REQUIRED |

High-impact triggers do not make final legal determinations. Multiple triggers may escalate to a stronger review status candidate. High confidence does not cancel high-impact triggers or remove expert review need. Low confidence alone does not automatically block the result; it must be evaluated with the other validation outcomes. REQUIRED BEFORE ACTION is a design candidate and not an implemented enforcement rule. NOT REQUIRED does not guarantee safety or legal validity. Specific thresholds, priority rules, and final state mapping remain undecided. Expert review recommendation is not legal advice and no expert connection feature is implemented in this draft.

## 26. User Notice

User notices must communicate:

- AI analysis is reference information only.
- The service is not legal advice.
- The service does not replace experts.
- Omissions and errors are possible.
- Confidence is not a guarantee.
- Important decisions may require expert review.
- External AI is not executed in the current draft state.
- Real data use is not approved in this design phase.

Exact UI copy, location, modal behavior, checkbox wording, and consent records are deferred to later versions.

## 27. Error State Display

User-facing error states must:

- avoid raw exception text
- avoid account existence disclosure
- avoid contract body exposure
- avoid personal data exposure
- give safe next-step direction where appropriate
- distinguish user action required from safety block
- avoid presenting failure as successful analysis
- avoid blaming the user for system failure

## 28. Prohibited Access Paths

- anonymous upload or analysis request
- unauthenticated result access
- cross-user result access
- URL-only access to document resources
- frontend-only authorization
- administrator unrestricted D1 access
- security operator contract body access
- service role use for user requests
- audit log access without approval
- raw provider request or response access
- access after permission revocation

## 29. Prohibited Output Paths

- provider response displayed without validation
- provider response stored before validation
- personal data regenerated in output
- contract source text regenerated in output
- legal advice wording
- legality, illegality, invalidity, enforceability, win, refund, dismissal, or outcome certainty
- "safe" or "no risk" conclusions
- confidence-only safety decision
- expert review need suppressed when required
- user notice omitted when required

## 30. Audit Event Candidates

| Event code | Trigger | Required metadata | Prohibited data | Status |
|---|---|---|---|---|
| AUTHENTICATION_REQUIRED | Missing authentication | request_id, action_code | credential, body, PII | PROPOSED |
| AUTHORIZATION_DENIED | Permission denied | request_id, action_code, reason_code | body, PII | PROPOSED |
| CROSS_USER_ACCESS_BLOCKED | Ownership mismatch | request_id, reason_code | target content, PII | PROPOSED |
| ROLE_NOT_APPROVED | Role not approved | request_id, role_code | body, PII | PROPOSED |
| SESSION_INVALID | Invalid session | request_id, reason_code | session identifier | PROPOSED |
| SECURITY_HOLD_APPLIED | Security hold candidate | request_id, reason_code | body, PII | PROPOSED |
| OUTPUT_SCHEMA_BLOCKED | Output schema failure | request_id, reason_code | raw response | PROPOSED |
| OUTPUT_REFERENCE_BLOCKED | Output reference mismatch | request_id, reason_code | raw response | PROPOSED |
| OUTPUT_REGENERATION_BLOCKED | PII or source regeneration | request_id, reason_code | regenerated value | PROPOSED |
| OUTPUT_SAFETY_REVIEW_REQUIRED | Ambiguous output | request_id, reason_code | raw response | PROPOSED |
| USER_NOTICE_REQUIRED | Notice required before display | request_id, notice_code | body, PII | PROPOSED |
| EXPERT_REVIEW_RECOMMENDED | Expert review candidate | request_id, reason_code | body, PII | PROPOSED |
| FAILURE_ESCALATION_REQUIRED | Repeated or severe failure | request_id, reason_code | body, PII | PROPOSED |

No actual success event for provider execution is activated in this PR.

## 31. Open Items

- Authentication product
- Password and MFA policy
- Session expiration values
- Role approval workflow
- Reviewer assignment process
- Administrator and operator separation details
- Error copy and UI placement
- Confidence display policy
- Expert review display policy
- User notice wording
- Security test fixture format
- Output safety schema

## 32. Follow-up PR Connections

| Follow-up PR | Connection |
|---|---|
| PR-6 | Integrated review, remaining issues, and final v0.2.2 design decision |
| v0.3 | UI placement, user notice copy, consent UX, and error message UX |
| v0.4 | Authentication, authorization, session, API, and DB schema |
| v0.5 | Pipeline implementation, output safety validation, and job recovery |
| v0.6 | Secret management, deployment configuration, and security operations |

## 33. Approval State

- Access control approval: Not approved
- Failure handling approval: Not approved
- Output safety approval: Not approved
- User notice approval: Not approved
- Security test plan approval: Not approved
- Authentication policy approval: Not approved
- Authorization policy approval: Not approved
- Session policy approval: Not approved
- Role model approval: Not approved
- Actual security test execution: NOT EXECUTED
- Production use approval: Not approved
