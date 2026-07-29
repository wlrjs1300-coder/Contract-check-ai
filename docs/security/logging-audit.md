# ContractCheck AI Logging and Audit

- Status: Draft
- Approval status: Review required / Not approved
- Version: v0.2.2 PR-3
- Implementation status: Not started
- Provider selection: Not selected
- External AI use approval: Not granted
- Real contract use: Not approved
- Real personal data use: Not approved
- Production use: Not approved

This document is a design draft for review. It is not a final approved logging, audit, monitoring, or incident response policy. It does not approve implementation, real contract processing, real personal data processing, external AI use, external transfer, product operation, or production release. This document is not legal advice, privacy compliance certification, or an operational approval record.

Concrete log retention periods, log collection systems, alert thresholds, roles, export procedures, and production operations require follow-up review and explicit user approval.

## 1. 문서 목적

이 문서는 ContractCheck AI v0.2.2 PR-3 범위에서 운영 로그, 감사 로그, 보안 이벤트 로그의 설계 초안을 정의한다.

목적은 로그에 기록 가능한 필드와 금지 필드, 로그 이벤트, 접근 통제, 무결성 요구사항, 보존과 삭제 원칙을 분리하여 PR-4와 PR-5가 참조할 기준선을 마련하는 것이다.

## 2. 적용 범위

적용 범위는 v0.2.2 개인정보·보안 통합 설계의 문서 초안에 한정한다.

이 문서는 다음을 승인하지 않는다.

- 실제 로그 수집 구현
- 실제 감사 로그 구현
- 실제 모니터링 시스템 선정
- 실제 계약서 또는 개인정보 로그 기록
- 구체적인 로그 보존 기간 최종 확정
- 운영 알림 기준 최종 확정
- 공급자 선정
- 외부 AI 사용
- 제품 운영 또는 프로덕션 출시

## 3. 로그 분류

### L1 — Operational Log

목적:

- 서비스 상태 확인
- 작업 진행 상태 확인
- 오류 코드 확인
- 처리 시간 확인
- 성능 및 장애 분석

허용 후보:

- timestamp
- job_id
- reference_id
- event code
- status code
- error code
- processing duration
- retry count
- policy version
- component identifier

금지:

- 계약서 본문
- 추출 원문
- 조항 원문
- 개인정보
- masked clause body
- outbound payload
- raw provider request
- raw provider response
- API Key
- access token
- secret

### L2 — Audit Log

목적:

- 누가
- 언제
- 어떤 작업을
- 어떤 결과로 수행했는지 추적

허용 후보:

- timestamp
- actor identifier
- actor type
- action code
- target identifier
- result code
- policy version
- access decision
- deletion result
- approval status

금지:

- 계약서 본문
- 개인정보
- raw request/response
- provider payload
- credential
- secret

### L3 — Security Event Log

목적:

- 인증 실패
- 권한 거부
- allowlist 위반
- residual PII 탐지
- 삭제 실패
- 무결성 이상
- 비정상 반복 요청
- 정책 위반 시도

허용 후보:

- timestamp
- event code
- actor identifier
- target identifier
- block reason code
- policy version
- severity
- result code

금지:

- 탐지된 개인정보 원문
- 계약서 본문
- payload 전체
- raw exception body
- secret

### L1~L3와 D1~D4 매핑

L1(Operational)/L2(Audit)/L3(Security Event)는 로그의 목적에 따른 분류이며, D1~D4는 개별 데이터 항목의 민감도에 따른 분류이다(`docs/security/data-classification.md` 참고). 두 체계는 서로 다른 축이며, 하나가 다른 하나를 대체하지 않는다.

- **L1 — Operational**: 위 "허용 후보" 목록은 D3(Internal) 등급 필드를 중심으로 구성된다. D2 이상의 payload(raw operational/audit log payload, 계약서 본문, 개인정보, masked clause body 등)가 기록되려는 경우 해당 기록 시도는 금지 또는 차단 대상이다.
- **L2 — Audit**: 위 "허용 후보" 목록은 D3 등급 필드를 중심으로 구성된다. 원문(D1)과 D2 payload(masked clause body, outbound payload, normalized analysis result 원문 등)는 감사 로그에도 기록하지 않는다.
- **L3 — Security Event**: 위 "허용 후보" 목록은 D3 등급 필드(event code, actor/target identifier, block reason code, severity, result code)를 중심으로 구성된다. 코드·상태·식별자 중심으로 제한하며, 탐지된 개인정보 원문이나 payload 전체와 같은 D1/D2 원문은 기록하지 않는다.

이 매핑은 §7 허용 필드와 §8 금지 필드의 기존 값을 변경하지 않으며, 두 분류 체계 사이의 대응 관계만 명확히 한다. 구체적인 보존 기간과 운영 정책은 이 매핑으로 확정되지 않는다.

## 4. 운영 로그

운영 로그는 서비스 상태와 처리 상태를 확인하기 위한 최소 메타데이터 후보이다.

- 본문과 개인정보를 기록하지 않는다.
- raw provider request와 raw provider response를 기록하지 않는다.
- 오류 원문 대신 error code와 component identifier를 사용한다.
- DEBUG 수준에서도 본문과 개인정보를 기록하지 않는다.
- 운영 로그 보존 기간은 미확정이다.
- 운영 로그 접근 권한은 PR-5에서 확정한다.

## 5. 감사 로그

감사 로그는 행위자, 작업, 대상 식별자, 결과를 추적하기 위한 최소 메타데이터 후보이다.

- 계약서 본문과 개인정보를 기록하지 않는다.
- raw request/response와 provider payload를 기록하지 않는다.
- 수정·삭제 권한 제한이 필요하다.
- 로그 조회 자체를 감사 대상으로 기록해야 한다.
- 감사 로그 보존 기간은 미확정이다.
- 구체적인 무결성 방식은 미확정이다.

## 6. 보안 이벤트 로그

보안 이벤트 로그는 차단, 위반, 무결성 이상, 삭제 실패 등 안전 경계 이벤트를 기록하기 위한 후보이다.

- 탐지된 개인정보 원문을 기록하지 않는다.
- payload 전체를 기록하지 않는다.
- block reason code와 policy version 중심으로 기록한다.
- 보안 이벤트 기록 실패는 `ESCALATION REQUIRED` 후보이다.

## 7. 허용 필드

| Field | Operational log | Audit log | Security log | Personal data allowed | Contract content allowed | Required control | Decision status |
|---|---|---|---|---|---|---|---|
| timestamp | Yes | Yes | Yes | No | No | Trusted timestamp source candidate | PROPOSED |
| event_id | Yes | Yes | Yes | No | No | Unique event identifier | PROPOSED |
| job_id | Yes | REVIEW REQUIRED | Yes | No | No | No body or personal data in identifier | PROPOSED |
| reference_id | Yes | REVIEW REQUIRED | Yes | No | No | Mapping without body text | PROPOSED |
| actor_id | No | Yes | Yes | REVIEW REQUIRED | No | Pseudonymous or internal identifier review | REVIEW REQUIRED |
| actor_type | No | Yes | Yes | No | No | Role category only | PROPOSED |
| action_code | No | Yes | Yes | No | No | Code allowlist | PROPOSED |
| status_code | Yes | No | Yes | No | No | Code only | PROPOSED |
| error_code | Yes | REVIEW REQUIRED | Yes | No | No | No raw exception body | PROPOSED |
| block_reason_code | Yes | REVIEW REQUIRED | Yes | No | No | Code only, no body excerpt | PROPOSED |
| result_code | Yes | Yes | Yes | No | No | Code allowlist | PROPOSED |
| processing_duration | Yes | No | REVIEW REQUIRED | No | No | Timing metadata only | PROPOSED |
| retry_count | Yes | No | REVIEW REQUIRED | No | No | Count only | PROPOSED |
| policy_version | Yes | Yes | Yes | No | No | Version string only | PROPOSED |
| model_version | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | No | No | No payload, no response body | REVIEW REQUIRED |
| endpoint_version | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | No | No | Endpoint identifier only | REVIEW REQUIRED |
| component_id | Yes | No | Yes | No | No | Internal component identifier | PROPOSED |
| severity | Yes | REVIEW REQUIRED | Yes | No | No | Severity policy not final | PROPOSED |
| deletion_result | Yes | Yes | Yes | No | No | No deleted body values | PROPOSED |
| access_decision | No | Yes | Yes | No | No | Access result only | PROPOSED |
| approval_status | No | Yes | Yes | No | No | Approval state only | PROPOSED |
| source_hash | REVIEW REQUIRED | REVIEW REQUIRED | REVIEW REQUIRED | No | No | Non-reversible form, salt/pepper implementation not decided | REVIEW REQUIRED |
| request_id | Yes | REVIEW REQUIRED | Yes | No | No | Correlation only, no request body | PROPOSED |
| correlation_id | Yes | Yes | Yes | No | No | Trace correlation without body | PROPOSED |

`source_hash` must be non-reversible. Salt, pepper, or other concrete implementation details are not approved in this PR. `source_hash` log usage is `REVIEW REQUIRED` and must not be treated as a replacement value for source text or personal data.

## 8. 금지 필드

The following fields must not be written to operational logs, audit logs, or security logs.

- original contract file
- extracted text
- clause body
- unmasked clause data
- detected personal data
- masked clause body
- residual PII value
- outbound candidate payload
- raw provider request
- raw provider response
- provider prompt
- provider completion
- API Key
- access token
- refresh token
- password
- secret
- authorization header
- cookie value
- full exception body containing user data
- database connection string

## 9. 로그 이벤트 목록

| Event code | Log type | Severity candidate | Required fields | Prohibited fields | Failure action | Decision status |
|---|---|---|---|---|---|---|
| FILE_RECEIVED | Operational | INFO | timestamp, job_id, event_id | file body, filename if personal data | REVIEW | PROPOSED |
| FILE_VALIDATION_PASSED | Operational | INFO | timestamp, job_id, status_code | file body | REVIEW | PROPOSED |
| FILE_VALIDATION_BLOCKED | Security | WARN | timestamp, job_id, block_reason_code | file body, raw exception | BLOCK | PROPOSED |
| TEXT_EXTRACTION_STARTED | Operational | INFO | timestamp, job_id, component_id | extracted text | REVIEW | PROPOSED |
| TEXT_EXTRACTION_FAILED | Operational/Security | ERROR | timestamp, job_id, error_code | extracted text, exception body with user data | BLOCK | PROPOSED |
| CLAUSE_SPLIT_COMPLETED | Operational | INFO | timestamp, job_id, result_code | clause body | REVIEW | PROPOSED |
| CLAUSE_SPLIT_FAILED | Operational | ERROR | timestamp, job_id, error_code | clause body | BLOCK | PROPOSED |
| PII_DETECTION_COMPLETED | Operational | INFO | timestamp, job_id, result_code | detected personal data | REVIEW | PROPOSED |
| PII_DETECTION_REVIEW | Security | WARN | timestamp, job_id, block_reason_code | detected personal data | REVIEW | PROPOSED |
| MASKING_COMPLETED | Operational | INFO | timestamp, job_id, result_code | masked clause body | REVIEW | PROPOSED |
| MASKING_FAILED | Security | ERROR | timestamp, job_id, error_code | source or masked text | BLOCK | PROPOSED |
| RESIDUAL_SCAN_PASSED | Operational | INFO | timestamp, job_id, result_code | scanned text | REVIEW | PROPOSED |
| RESIDUAL_SCAN_BLOCKED | Security | SECURITY | timestamp, job_id, block_reason_code | residual PII value | BLOCK | PROPOSED |
| ALLOWLIST_PASSED | Operational | INFO | timestamp, job_id, result_code, policy_version | outbound payload | REVIEW | PROPOSED |
| ALLOWLIST_BLOCKED | Security | SECURITY | timestamp, job_id, block_reason_code, policy_version | outbound payload | BLOCK | PROPOSED |
| EXTERNAL_AI_NOT_EXECUTED | Audit/Security | INFO | timestamp, job_id, approval_status | provider payload | REVIEW | PROPOSED |
| RESPONSE_SCHEMA_PASSED | Operational | INFO | timestamp, job_id, result_code | raw provider response | REVIEW | PROPOSED |
| RESPONSE_SCHEMA_BLOCKED | Security | ERROR | timestamp, job_id, block_reason_code | raw provider response | BLOCK | PROPOSED |
| REFERENCE_ID_VALIDATED | Operational | INFO | timestamp, job_id, result_code | clause body | REVIEW | PROPOSED |
| REFERENCE_ID_REVIEW | Audit/Security | WARN | timestamp, job_id, block_reason_code | clause body | REVIEW | PROPOSED |
| OUTPUT_SAFETY_PASSED | Operational | INFO | timestamp, job_id, result_code | output body | REVIEW | PROPOSED |
| OUTPUT_SAFETY_BLOCKED | Security | SECURITY | timestamp, job_id, block_reason_code | unsafe output body | BLOCK | PROPOSED |
| TEMP_DATA_DELETION_STARTED | Operational | INFO | timestamp, job_id, event_id | deleted body values | REVIEW | PROPOSED |
| TEMP_DATA_DELETION_COMPLETED | Audit | INFO | timestamp, job_id, deletion_result | deleted body values | REVIEW | PROPOSED |
| TEMP_DATA_DELETION_FAILED | Security | ERROR | timestamp, job_id, deletion_result, error_code | deleted body values | BLOCK or REVIEW | PROPOSED |
| USER_DELETE_REQUESTED | Audit | INFO | timestamp, actor_id, action_code | contract body, personal data | REVIEW | PROPOSED |
| ACCESS_ALLOWED | Audit | INFO | timestamp, actor_id, access_decision | accessed body | REVIEW | PROPOSED |
| ACCESS_DENIED | Security | WARN | timestamp, actor_id, access_decision | requested body | BLOCK or REVIEW | PROPOSED |
| POLICY_VERSION_CHANGED | Audit | INFO | timestamp, actor_id, policy_version | policy secret or payload | REVIEW | PROPOSED |
| SECURITY_EVENT_DETECTED | Security | SECURITY | timestamp, event_id, block_reason_code, severity | payload, personal data | ESCALATION REQUIRED | PROPOSED |

Concrete severity numbers and monitoring systems are not approved in this PR.

## 10. 로그 수준

The following log levels are design candidates.

- DEBUG
- INFO
- WARN
- ERROR
- SECURITY

Principles:

- DEBUG is a candidate for disabled-by-default in production.
- DEBUG must not include body text or personal data.
- INFO focuses on normal status codes.
- WARN indicates `REVIEW` or abnormal boundary cases.
- ERROR indicates processing failure and safe blocking.
- SECURITY indicates access denial, policy violation, or integrity anomaly.
- Concrete operational levels and collection scope are decided in PR-5 or operations design.

## 11. 접근 통제 요구사항

- 최소 권한
- 역할 기반 접근 통제 후보
- 운영 로그와 감사 로그 접근 분리
- 감사 로그 수정 권한 제한
- 로그 조회 자체를 감사 대상으로 기록
- 다운로드·내보내기 별도 승인
- 대량 조회 제한
- 비정상 조회 탐지
- 접근 권한 정기 검토
- 실제 역할·권한 모델은 PR-5에서 확정

## 12. 무결성 요구사항

- audit event 순서 추적 가능
- event_id 또는 correlation_id 사용 후보
- 수정·삭제 탐지 가능성
- 감사 로그 변경 이력 관리
- timestamp 신뢰성
- 정책 버전 연결
- 삭제 이벤트와 삭제 결과 연결
- 접근 이벤트와 actor 연결
- 무결성 검증 실패 시 `SECURITY` 또는 `REVIEW`
- 구체적인 hash chain, WORM, 서명 방식은 미확정

## 13. 보존과 삭제

- 로그 보존 기간은 미확정이다.
- 운영 로그와 감사 로그 보존 기간을 구분한다.
- 보안 이벤트 로그 보존 기간은 별도 검토가 필요하다.
- 법적 보존 의무는 법률 검토가 필요하다.
- 목적 종료 후 삭제한다.
- 사용자 데이터 삭제 요청 시 본문 없는 감사 기록만 유지 후보이다.
- 로그에 본문·개인정보가 잘못 기록되면 즉시 `BLOCK` 또는 `SECURITY INCIDENT` 후보이다.
- 로그 백업과 삭제 전파는 미확정이다.
- 구체 기간은 사용자 승인이 필요하다.

## 14. 오류·예외 처리

- 예외 메시지에 계약서 본문을 포함하지 않는다.
- stack trace에 개인정보 포함 가능성 검사가 필요하다.
- raw exception body 저장 금지
- 사용자 표시 오류와 내부 오류를 분리한다.
- 내부 오류는 error code 중심으로 다룬다.
- 외부 공급자 오류 원문 저장 금지
- 오류에 payload 포함 금지
- 로그 기록 실패 시 silent success 금지
- 감사 로그 기록 실패 시 `REVIEW` 또는 `BLOCK`
- 보안 이벤트 기록 실패 시 `ESCALATION REQUIRED` 후보

## 15. 모니터링과 알림

- 모니터링 시스템은 선정하지 않는다.
- 알림 채널은 확정하지 않는다.
- alert threshold는 확정하지 않는다.
- 삭제 실패, allowlist 위반, residual PII 탐지, 접근 거부 반복은 보안 이벤트 후보이다.
- 알림에는 계약서 본문, 개인정보, payload, raw exception body를 포함하지 않는다.
- 구체적인 운영 절차는 PR-5 또는 운영 설계에서 확정한다.

## 16. 금지 로그 흐름

- contract body -> operational log
- contract body -> audit log
- personal data -> operational log
- personal data -> audit log
- masked clause body -> operational log
- outbound payload -> log
- raw provider request -> log
- raw provider response -> log
- API Key -> log
- access token -> log
- authorization header -> log
- cookie value -> log
- user-data exception body -> log
- deletion failure -> silent success
- audit log mutation -> untracked change

## 17. 검증 요구사항

- 운영 로그 허용 필드 allowlist 검증
- 감사 로그 허용 필드 allowlist 검증
- 보안 로그 허용 필드 allowlist 검증
- 금지 필드 로그 기록 차단
- 계약서 본문 로그 기록 차단
- 개인정보 로그 기록 차단
- raw request/response 로그 기록 차단
- credential 로그 기록 차단
- 삭제 실패 silent success 차단
- 감사 로그 무결성 요구사항 검토
- 로그 보존 기간 미승인 상태 확인

## 18. 미결정 사항

- 로그 수집 시스템
- 로그 보존 기간
- 감사 로그 보존 기간
- 보안 이벤트 로그 보존 기간
- 구체적인 severity 기준
- 알림 threshold
- 로그 조회 권한 모델
- 로그 export 승인 절차
- 감사 로그 무결성 구현 방식
- hash chain, WORM, 서명 방식
- 로그 백업과 삭제 전파

## 19. 후속 PR 연결

| 후속 PR | 연결 항목 |
|---|---|
| PR-4 | 외부 전송 통제, outbound allowlist, provider boundary, raw request/response 금지 |
| PR-5 | 접근 통제, 실패 처리, 출력 안전, 사용자 고지, 보안 테스트 |
| PR-6 | 통합 검토, 미결정 사항 정리, 최종 설계 결정 |

## 20. 승인 상태

- Operational logging policy approval: Not approved
- Audit logging policy approval: Not approved
- Security event logging approval: Not approved
- Log retention approval: Not approved
- Log access control approval: Not approved
- External AI use approval: Not granted
- Real contract use approval: Not granted
- Real personal data use approval: Not granted
- Implementation approval: Not granted
