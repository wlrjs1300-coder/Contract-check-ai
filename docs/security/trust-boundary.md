# ContractCheck AI Trust Boundary

- Status: Draft
- Approval status: Review required / Not approved
- Version: v0.2.2 PR-2
- Implementation status: Not started
- Provider selection: Not selected
- External AI use approval: Not granted
- Real contract use: Not approved
- Real personal data use: Not approved

This document is a design draft for review. It does not approve implementation, external AI use, real contract processing, or real personal data processing. Data storage and transfer rules require follow-up policy review, implementation review, and explicit approval. This document is not legal advice, privacy compliance certification, or an operational approval record.

## 1. 문서 목적

이 문서는 ContractCheck AI v0.2.2 PR-2 범위에서 신뢰 경계 초안을 정의한다.

목적은 사용자 입력, 임시 처리, 내부 애플리케이션, 저장소, 외부 AI 공급자 후보, 사용자 표시, 로그·감사 영역 사이의 데이터 이동 제한과 검증 요구사항을 정리하는 것이다.

## 2. 신뢰 경계 원칙

- 외부 입력은 신뢰하지 않는다.
- 원본 계약서와 추출 원문은 가장 민감한 내부 임시 데이터로 취급한다.
- 외부 AI 공급자 경계는 현재 비활성이고 승인되지 않았다.
- Zone C -> Zone E 경계는 별도 승인 전까지 `NOT APPROVED`이다.
- 로그와 감사 영역에는 계약서 본문, 개인정보, raw provider response를 기록하지 않는다.
- 사용자에게 표시되는 결과는 정규화, schema 검증, reference_id 검증, 출력 안전성 검증을 통과한 후보만 가능하다.
- 이 문서는 공급자 선정, 외부 AI 사용, 실제 데이터 테스트를 승인하지 않는다.

## 3. 구성 영역

### Zone A - User Device

- 사용자가 계약서 파일을 선택하는 영역
- 신뢰할 수 없는 입력
- 파일 내용, 형식, 크기, 악성 입력 가능성 존재

### Zone B - Upload and Temporary Processing

- 파일 검증
- 텍스트 추출
- 조항 분할
- 개인정보 탐지와 마스킹
- residual scan
- 데이터가 존재할 수 있는 가장 민감한 처리 영역

### Zone C - Internal Application Core

- reference_id 관리
- source_hash 관리
- analysis job status
- policy decision
- normalized result processing
- output safety validation

### Zone D - Internal Persistence

- minimal metadata
- normalized analysis result candidate
- audit metadata
- deletion metadata
- original body and raw response storage prohibited

### Zone E - External AI Provider Boundary

- currently disabled
- provider not selected
- external AI use not approved
- only future candidate after masked/residual/allowlist pass
- actual transfer prohibited before separate approval

### Zone F - User Presentation

- only validated normalized results display
- raw provider response display prohibited
- output safety pass required
- legal-advice disclaimer and notice required

### Zone G - Logging and Audit

- no body metadata only
- no contract body
- no personal data
- block reason and policy version candidate

## 4. 경계별 허용 데이터

| Boundary | Allowed data | Prohibited data | Required validation | Failure action | Logging rule | Current status |
|---|---|---|---|---|---|---|
| Zone A -> Zone B | User-selected file candidate | Executable or unsupported input if policy rejects it | File format and size validation | BLOCK | Metadata only | ACTIVE |
| Zone B -> Zone C | source_hash, reference_id, masked processing candidate, status | Original contract file, extracted text, detected personal data | PII masking, residual scan, reference mapping | BLOCK or REVIEW | No body, no personal data | DESIGN ONLY |
| Zone B -> Zone D | deletion metadata, minimal processing metadata | Original contract file, extracted text, detected personal data | Storage policy and deletion policy | BLOCK or REVIEW | Metadata only | DESIGN ONLY |
| Zone C -> Zone D | job status, audit metadata, normalized result candidate | raw provider request, raw provider response, contract body | Schema and storage policy | BLOCK or REVIEW | Metadata only | DESIGN ONLY |
| Zone C -> Zone E | Future outbound candidate only after approvals | Original file, extracted text, detected personal data, residual data, non-allowlisted fields | residual 0, allowlist pass, provider approval | NOT EXECUTED | No payload logs | NOT APPROVED |
| Zone E -> Zone C | Future provider response candidate after approval | Raw response persistence, unsafe output | Schema validation, reference_id validation, output safety | BLOCK or REVIEW | No raw response logs | NOT APPROVED |
| Zone C -> Zone F | Validated normalized result candidate | raw provider response, legal conclusion, guarantee expression | Output safety and user notice | BLOCK or REVIEW | Display metadata only | DESIGN ONLY |
| all zones -> Zone G | status, code, duration, policy version, deletion metadata | contract body, personal data, raw provider request, raw provider response | Logging allowlist | BLOCK | Metadata only | DESIGN ONLY |

## 5. 경계별 필수 검증

- Zone A -> Zone B: 파일 형식, 크기, 악성 입력 가능성 검증
- Zone B -> Zone C: 조항 분할 성공, source_hash 생성, reference_id 생성, 개인정보 마스킹, residual 검증
- Zone B -> Zone D: 임시 데이터 삭제 조건, 삭제 metadata 기록 조건
- Zone C -> Zone D: 저장 가능 데이터 등급, raw 저장 금지, 최소 메타데이터 조건
- Zone C -> Zone E: residual 0, outbound allowlist, 공급자 승인, endpoint/model 승인, 비용·timeout·retry 정책
- Zone E -> Zone C: schema validation, reference_id validation, raw response storage prohibition
- Zone C -> Zone F: 출력 안전성, 법률 확정·보장 표현 차단, 사용자 고지
- all zones -> Zone G: 로그 allowlist, 본문·개인정보 금지, 감사 metadata 범위

## 6. 경계별 금지 데이터

- 원본 계약서 파일은 Zone E로 이동할 수 없다.
- 추출 원문은 Zone E로 이동할 수 없다.
- detected personal data는 Zone E로 이동할 수 없다.
- residual 개인정보가 있는 데이터는 Zone E로 이동할 수 없다.
- raw provider request는 Zone D 또는 Zone G에 저장할 수 없다.
- raw provider response는 Zone D 또는 Zone G에 저장할 수 없다.
- 계약서 본문은 Zone G에 기록할 수 없다.
- 개인정보는 Zone G에 기록할 수 없다.
- 검증되지 않은 외부 응답은 Zone F로 이동할 수 없다.

## 7. 위협과 통제

| Threat | Affected boundary | Preventive control | Detection control | Failure action | Follow-up PR |
|---|---|---|---|---|---|
| malicious/malformed file upload | Zone A -> Zone B | Format and size policy | Validation failure event | BLOCK | PR-5 |
| file format spoofing | Zone A -> Zone B | Content-type and parser checks | Parser mismatch | BLOCK | PR-5 |
| excessive file size | Zone A -> Zone B | Size limit | Size validation | BLOCK | PR-5 |
| text extraction error | Zone B | Extraction validation | Empty or invalid extraction check | BLOCK | PR-5 |
| clause boundary loss | Zone B -> Zone C | Clause splitter validation | Reference coverage check | BLOCK or REVIEW | PR-5 |
| PII detection omission | Zone B | Detection policy | residual scan | BLOCK or REVIEW | PR-2 |
| masking failure | Zone B | Masking rules | residual scan and expected token check | BLOCK | PR-2 |
| residual PII present | Zone B -> Zone C | Masking before transfer candidate | residual scan | BLOCK | PR-2 |
| prompt injection/document instruction text | Zone B -> Zone C | Treat document text as data | Output safety and instruction isolation checks | BLOCK or REVIEW | PR-5 |
| allowlist bypass | Zone C -> Zone E | outbound allowlist | payload field validation | BLOCK | PR-4 |
| raw text log leakage | all zones -> Zone G | logging allowlist | log review and tests | BLOCK | PR-3 |
| raw response storage | Zone E -> Zone C, Zone C -> Zone D | raw response storage prohibition | storage validation | BLOCK | PR-5 |
| reference_id tamper/mismatch | Zone C | signed or validated mapping requirement | reference_id validation | BLOCK or REVIEW | PR-5 |
| provider response schema tamper | Zone E -> Zone C | schema validation | schema mismatch | BLOCK | PR-5 |
| provider outage | Zone C -> Zone E | safe-fail policy | timeout/error status | NOT EXECUTED or BLOCK | PR-5 |
| timeout/retry amplification | Zone C -> Zone E | retry and timeout limits | retry count monitoring | BLOCK or REVIEW | PR-5 |
| cost limit exceeded | Zone C -> Zone E | cost cap | cost metadata | BLOCK | PR-4 |
| unauthorized data read | Zone D | access control | audit event | BLOCK or REVIEW | PR-5 |
| deletion failure | Zone B -> Zone D | deletion policy | deletion metadata | REVIEW or BLOCK | PR-3 |
| audit log tampering | Zone G | audit integrity controls | audit review | REVIEW | PR-3 |

## 8. 실패 시 동작

- 검증 실패 시 안전한 기본값은 `BLOCK`이다.
- 불확실성이 남으면 `REVIEW`이다.
- 외부 AI 호출은 현재 `NOT EXECUTED`이다.
- 삭제 실패는 숨기지 않고 metadata로 기록하되 본문은 기록하지 않는다.
- 사용자 표시 후보는 출력 안전성 검증 전까지 생성하지 않는다.

## 9. 외부 공급자 경계

- Provider selection: Not selected
- External AI use approval: Not granted
- Endpoint selection: Not selected
- Model selection: Not selected
- API Key preparation: Not approved
- Provider adapter implementation: Not approved
- Real data transfer: Not approved

Zone E 활성화 전 필요한 조건은 다음과 같다.

- data classification approval
- PII flow approval
- trust boundary approval
- storage/log policy approval
- outbound allowlist approval
- access control approval
- log/audit policy approval
- failure/blocking approval
- security test pass
- provider policy revalidation
- provider selection
- endpoint/model selection
- cost approval
- actual transfer data scope approval
- user final approval

## 10. 로그·감사 경계

- 로그와 감사는 metadata 중심으로 제한한다.
- 계약서 본문을 기록하지 않는다.
- 개인정보를 기록하지 않는다.
- raw provider request를 기록하지 않는다.
- raw provider response를 기록하지 않는다.
- 허용 후보는 job status, error code, block reason code, policy version, endpoint/model version, retry count, processing duration, deletion metadata이다.
- 구체적인 보존 기간, 접근 권한, 감사 이벤트 구조는 PR-3과 PR-5에서 확정한다.

## 11. 미결정 사항

- 신뢰 경계 다이어그램 작성 여부
- Zone B 임시 처리 영역의 기술적 격리 방식
- Zone D 저장소 세분화 방식
- Zone G 감사 로그 무결성 검증 방식
- Zone C -> Zone E 활성화 조건의 최종 승인 절차
- 공급자 장애 시 사용자 고지 방식
- 접근 통제와 권한 모델

## 12. 승인 상태

- Trust boundary approval: Not approved
- Data classification detail approval: Not approved
- PII processing flow approval: Not approved
- External AI use approval: Not granted
- Real contract use approval: Not granted
- Real personal data use approval: Not granted
- Implementation approval: Not granted
