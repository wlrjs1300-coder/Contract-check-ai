# ContractCheck AI Storage, Retention, and Deletion

- Status: Draft
- Approval status: Review required / Not approved
- Version: v0.2.2 PR-3
- Implementation status: Not started
- Provider selection: Not selected
- External AI use approval: Not granted
- Real contract use: Not approved
- Real personal data use: Not approved
- Production use: Not approved

This document is a design draft for review. It is not a final approved storage, retention, deletion, backup, or operating policy. It does not approve implementation, real contract processing, real personal data processing, external AI use, external transfer, product operation, or production release. This document is not legal advice, privacy compliance certification, or an operational approval record.

Concrete retention periods, retry counts, backup behavior, operator responsibilities, and production procedures require follow-up review and explicit user approval.

## 1. 문서 목적

이 문서는 ContractCheck AI v0.2.2 PR-3 범위에서 저장, 보존, 삭제, 백업, 복제, 캐시 기준의 설계 초안을 정의한다.

목적은 PR-2에서 정의한 데이터 등급, 개인정보 처리 흐름, 신뢰 경계 위에 어떤 데이터가 임시 처리 대상인지, 어떤 데이터가 영구 저장 후보인지, 어떤 데이터가 저장 금지인지, 삭제 실패 시 어떤 안전 판정을 적용해야 하는지를 명확히 분리하는 것이다.

## 2. 적용 범위

적용 범위는 v0.2.2 개인정보·보안 통합 설계의 문서 초안에 한정한다.

이 문서는 다음을 승인하지 않는다.

- 실제 DB 저장 구현
- 실제 파일 저장 구현
- 실제 백업 구성
- 실제 삭제 작업 구현
- 실제 계약서 또는 개인정보 저장
- 실제 계약서 또는 개인정보 로그 기록
- 구체적인 운영 보존 기간 최종 확정
- 삭제 재시도 횟수 최종 확정
- 공급자 선정
- 외부 AI 사용
- 실제 외부 전송
- 제품 운영 또는 프로덕션 출시

## 3. 기본 원칙

- 최소 저장을 기본값으로 한다.
- 데이터는 목적 제한 원칙에 따라 처리한다.
- 저장 전 데이터 분류를 먼저 확인한다.
- 원문은 기본적으로 저장하지 않는다.
- 민감 데이터는 임시 처리 대상으로만 다룬다.
- 실패 시 안전 삭제 또는 차단을 우선한다.
- 정상 종료 후 임시 데이터는 삭제 대상이다.
- 삭제 확인 메타데이터는 본문 없이 기록한다.
- 로그와 저장소를 분리한다.
- 실제 계약서와 실제 개인정보는 사용할 수 없다.
- 테스트는 synthetic fixture만 가능하다.
- 저장 여부가 불명확하면 기본값은 `BLOCK` 또는 `REVIEW`이다.
- 구체적인 보존 기간은 사용자 승인 전 확정하지 않는다.

## 4. 저장 영역 구분

### S1 — Temporary Processing Storage

용도:

- 업로드 파일 검증
- 텍스트 추출
- 조항 분할
- 개인정보 탐지
- 마스킹
- residual 검사

허용 후보:

- original contract file
- extracted text
- unmasked clause data
- detected personal data
- masked clause data

원칙:

- 임시 처리 전용
- 영구 저장 금지
- 외부 전송 금지
- 운영 로그 기록 금지
- 정상 종료·실패·차단 후 삭제 대상
- 구체적인 보관 시간은 미확정
- 테스트는 synthetic fixture만 허용

### S2 — Application Metadata Storage

허용 후보:

- source_hash
- reference_id
- job status
- policy version
- model version
- endpoint version
- error code
- block reason code
- retry count
- processing duration
- deletion metadata

원칙:

- 본문과 개인정보 포함 금지
- 최소 필드만 저장
- 접근 통제 필요
- 보존 기간 미확정
- PR-5 접근 통제와 연결

### S3 — Normalized Result Storage

허용 후보:

- normalized analysis result
- display label
- confidence score
- expert review recommendation

원칙:

- 저장 여부는 아직 `DEFERRED` 또는 `REVIEW REQUIRED`
- 계약서 원문 포함 금지
- 개인정보 포함 금지
- raw provider response 저장 금지
- schema 검증과 출력 안전성 검증 후에만 저장 후보
- 저장 범위와 보존 기간은 후속 승인 필요

### S4 — Audit Storage

허용 후보:

- audit event metadata
- actor identifier
- action code
- result code
- policy version
- timestamp
- deletion result
- access event

원칙:

- 계약서 본문 포함 금지
- 개인정보 포함 금지
- raw request/response 포함 금지
- 수정·삭제 권한 제한 필요
- 무결성 검증 요구
- 구체적인 보존 기간 미확정

### S5 — Backup and Replica

현재 상태:

- DESIGN ONLY
- Not approved
- 실제 백업 구성 없음

원칙:

- D1 데이터 백업 금지
- 삭제 대상 데이터가 백업에 잔존하지 않도록 설계 필요
- 삭제 전파 요구사항 필요
- 백업 보존 기간 미확정
- 복구 절차 미확정
- 실제 운영 승인 전 구현 금지

### S6 — Cache and Temporary Memory

원칙:

- 민감 데이터 캐시 기본 금지
- 사용이 필요한 경우 명시적 승인 필요
- TTL 미확정
- 프로세스 종료·오류·차단 시 정리 필요
- 로그나 예외 메시지로 유출 금지

## 5. 데이터 등급별 저장 정책

| Data class | Temporary storage | Permanent storage | Logging | Backup | Deletion requirement | Retention status | Decision status | Follow-up PR |
|---|---|---|---|---|---|---|---|---|
| D1 - Restricted | 임시 처리만 후보 | 금지 | 운영 로그 금지, 감사 로그 본문 금지 | 금지 | 정상·실패·차단 후 삭제 | IMMEDIATE DELETE | PROHIBITED | PR-3 |
| D2 - Sensitive | 필요 시 임시 후보 | 항목별 `REVIEW REQUIRED` 또는 `DEFERRED` | 본문·개인정보 없이 상태 코드만 후보 | 미승인 | 저장 전 schema 검증과 출력 안전성 검증 필요 | RETENTION NOT APPROVED | REVIEW REQUIRED | PR-3/PR-5 |
| D3 - Internal | 임시 또는 영구 메타데이터 후보 | 최소 메타데이터만 후보 | 본문·개인정보 없이 후보 | 미승인 | 목적 종료 후 삭제 또는 보존 검토 | REVIEW REQUIRED | PROPOSED | PR-3/PR-5 |
| D4 - Public | 필요 없음 또는 공개 문서 후보 | 공개 검토 후 후보 | 공개 기록 기준 검토 | 미승인 | 공개 기록 정책에 따라 검토 | REVIEW REQUIRED | DEFERRED | PR-6 |

## 6. 임시 데이터 처리

임시 데이터는 처리 목적이 끝나면 삭제 대상이다. D1 데이터는 영구 저장, 운영 로그, 외부 전송, 백업 후보가 아니다.

임시 처리 대상은 다음과 같다.

- original contract file
- extracted text
- unmasked clause data
- detected personal data
- masked clause data before storage approval
- outbound candidate payload before transfer approval

임시 데이터 보관 시간, 격리 방식, 삭제 재시도 정책은 미확정이다. 보관 시간 또는 삭제 재시도 횟수가 필요한 경우 후속 검토와 사용자 승인이 필요하다.

## 7. 영구 저장 후보

영구 저장 후보는 본문과 개인정보를 포함하지 않는 최소 메타데이터 또는 검증된 정규화 결과로 제한한다.

| Data item | Classification | Temporary storage | Permanent storage candidate | Backup candidate | Delete trigger | Retention status | Required control | Decision status |
|---|---|---|---|---|---|---|---|---|
| original contract file | D1 | Yes | No | No | 정상 완료, 실패, 차단, 사용자 취소 | IMMEDIATE DELETE | Temporary only, no external transfer | PROHIBITED |
| extracted text | D1 | Yes | No | No | 텍스트 처리 완료, 실패, 차단 | IMMEDIATE DELETE | Temporary only, no permanent storage | PROHIBITED |
| unmasked clause data | D1 | Yes | No | No | 마스킹 완료, 실패, 차단 | IMMEDIATE DELETE | Delete after masking or block | PROHIBITED |
| detected personal data | D1 | Yes | No | No | 마스킹 완료, 실패, 차단 | IMMEDIATE DELETE | No logs, no external transfer | PROHIBITED |
| masked clause data | D2 | Yes | REVIEW REQUIRED | No until approved | 작업 완료, 차단, 보존 미승인 | RETENTION NOT APPROVED | residual 0, allowlist, approval | REVIEW REQUIRED |
| residual scan result | D2 | Yes | Minimal status candidate | No until approved | 작업 완료 또는 차단 | REVIEW REQUIRED | No residual value stored | PROPOSED |
| outbound candidate payload | D2 | Yes | No raw permanent storage | No | allowlist 실패, 전송 미승인, 작업 종료 | NO PERSISTENCE | raw payload storage prohibited | PROHIBITED |
| raw provider request | D1 | No approved execution | No | No | 생성 시도 차단 | NO PERSISTENCE | External AI not approved, raw storage prohibited | PROHIBITED |
| raw provider response | D1 | No approved execution | No | No | 수신 시도 차단 | NO PERSISTENCE | Raw response storage prohibited | PROHIBITED |
| normalized analysis result | D2 | Candidate | REVIEW REQUIRED | No until approved | 사용자 삭제 요청, 보존 종료 | RETENTION NOT APPROVED | schema validation and output safety | DEFERRED |
| display label | D2 | Candidate | REVIEW REQUIRED | No until approved | 사용자 삭제 요청, 보존 종료 | RETENTION NOT APPROVED | output safety and no legal guarantee | DEFERRED |
| confidence score | D2 | Candidate | REVIEW REQUIRED | No until approved | 사용자 삭제 요청, 보존 종료 | RETENTION NOT APPROVED | No user-facing risk score without approval | REVIEW REQUIRED |
| expert review recommendation | D2 | Candidate | REVIEW REQUIRED | No until approved | 사용자 삭제 요청, 보존 종료 | RETENTION NOT APPROVED | Must not imply legal advice | DEFERRED |
| source_hash | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료, 사용자 삭제 요청 검토 | REVIEW REQUIRED | Non-reversible form, no source text | PROPOSED |
| reference_id | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료, 사용자 삭제 요청 검토 | REVIEW REQUIRED | Stable mapping without body text | PROPOSED |
| job status | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | Status code only | PROPOSED |
| policy version | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | Version only | PROPOSED |
| model version | D3 | Candidate | REVIEW REQUIRED | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | No payload, no provider response | REVIEW REQUIRED |
| endpoint version | D3 | Candidate | REVIEW REQUIRED | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | Identifier only, no payload | REVIEW REQUIRED |
| error code | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | Code only, no raw text | PROPOSED |
| block reason | D2 | Candidate | REVIEW REQUIRED | No until approved | 보존 종료 | REVIEW REQUIRED | Code only, avoid body excerpt | REVIEW REQUIRED |
| retry count | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | Count only | PROPOSED |
| processing duration | D3 | Candidate | Yes | REVIEW REQUIRED | 보존 종료 | REVIEW REQUIRED | Timing metadata only | PROPOSED |
| deletion metadata | D3 | Candidate | Yes | REVIEW REQUIRED | 삭제 기록 보존 종료 | REVIEW REQUIRED | No body, no personal data | PROPOSED |
| audit metadata | D3 | Candidate | Yes | REVIEW REQUIRED | 감사 보존 종료 | REVIEW REQUIRED | No body, no personal data | PROPOSED |
| operational log event | D3 | Candidate | Yes | REVIEW REQUIRED | 로그 보존 종료 | REVIEW REQUIRED | Logging allowlist | PROPOSED |
| audit log event | D3 | Candidate | Yes | REVIEW REQUIRED | 감사 보존 종료 | REVIEW REQUIRED | Integrity control | PROPOSED |

## 8. 보존 기간 결정 원칙

이번 PR에서는 특정 일수나 시간을 최종 확정하지 않는다.

보존 상태 값은 다음만 사용한다.

- IMMEDIATE DELETE
- SESSION ONLY
- SHORT-LIVED — DURATION NOT APPROVED
- RETENTION NOT APPROVED
- NO PERSISTENCE
- REVIEW REQUIRED

보존 원칙은 다음과 같다.

- D1 데이터는 처리 완료·실패·차단 후 삭제한다.
- D1은 영구 보존하지 않는다.
- 일부 임시 처리 데이터는 처리 세션 안에서만 존재할 수 있으나 D1 등급의 최종 보존 판정은 `IMMEDIATE DELETE`이다.
- 구체적인 삭제 시점이나 세션 시간은 아직 승인되지 않았다.
- D2는 항목별 저장 필요성을 검토한다.
- D3는 감사·운영 목적 최소 기간을 검토한다.
- D4는 공개 기록 정책에 따라 별도 검토한다.
- 업무 목적이 끝난 데이터는 삭제한다.
- 법률상 보존 의무는 별도 법률 검토가 필요하다.
- 보존 연장에는 별도 승인이 필요하다.
- 보존 기간이 미정이면 저장 구현 금지 또는 `REVIEW`이다.

## 9. 삭제 트리거

삭제 트리거는 다음과 같다.

- 정상 처리 완료
- 파일 형식 검증 실패
- 파일 크기 검증 실패
- 텍스트 추출 실패
- 조항 분할 실패
- 개인정보 탐지 실패
- 마스킹 실패
- residual PII 발견
- allowlist 위반
- 사용자 취소
- 작업 timeout
- 작업 강제 중단
- 시스템 오류
- 보존 기간 만료
- 사용자 삭제 요청
- 관리자 승인 삭제
- 정책 변경에 따른 삭제
- 테스트 종료

## 10. 삭제 처리 흐름

1. 삭제 트리거 감지
2. 삭제 대상 식별
3. 데이터 분류 재확인
4. 처리 중지 또는 접근 차단
5. 임시 파일 삭제
6. 추출 원문 삭제
7. unmasked clause data 삭제
8. detected personal data 삭제
9. outbound candidate payload 삭제
10. 캐시·메모리 정리 요청
11. 관련 백업·복제 삭제 대상 등록
12. 삭제 결과 확인
13. 삭제 메타데이터 기록
14. 실패 시 `BLOCK` 또는 `REVIEW`
15. 재시도·운영자 검토 후보 등록
16. 사용자 표시 상태 갱신

구체적인 구현 방식, retry count, retry interval, backoff, escalation 담당자는 확정하지 않는다.

## 11. 삭제 실패와 재시도

삭제 실패 판정은 다음만 사용한다.

- BLOCK
- REVIEW
- RETRY CANDIDATE
- ESCALATION REQUIRED
- NOT IMPLEMENTED

### BLOCK

- D1 데이터가 삭제되지 않았고 접근 가능성이 남는 경우
- 삭제 실패 후 외부 전송 또는 사용자 표시가 계속될 수 있는 경우
- 삭제 대상이 운영 로그에 노출된 경우
- 삭제 대상 데이터의 위치를 식별할 수 없는 경우

### REVIEW

- 삭제 결과 확인이 불확실한 경우
- 백업·복제 반영 여부가 불확실한 경우
- 삭제 대상 메타데이터와 실제 상태가 불일치하는 경우

### RETRY CANDIDATE

- 일시적 파일 잠금
- 일시적 저장소 장애
- 일시적 네트워크 또는 replica 장애

### ESCALATION REQUIRED

- 반복 실패
- 무결성 이상
- 권한 부족
- 감사 로그 불일치
- 삭제 대상 손실 또는 위치 불명

현재 구체적인 retry count, retry interval, backoff, escalation 담당자는 미확정이다.

## 12. 백업·복제·캐시

- 백업·복제·캐시는 `DESIGN ONLY`이며 승인되지 않았다.
- D1 데이터는 백업하지 않는다.
- 삭제 대상 데이터가 백업이나 replica에 남지 않도록 삭제 전파 요구사항이 필요하다.
- 백업 보존 기간은 미확정이다.
- 복구 절차는 미확정이다.
- 민감 데이터 캐시는 기본 금지한다.
- 캐시가 필요한 경우 명시적 승인과 TTL 정책이 필요하다.
- 프로세스 종료·오류·차단 시 캐시와 메모리 정리 요구가 필요하다.
- 로그나 예외 메시지로 민감 데이터가 유출되면 `BLOCK` 또는 `SECURITY INCIDENT` 후보이다.

## 13. 사용자 요청 삭제

- 사용자 삭제 요청은 별도 인증·권한 확인 후 처리해야 한다.
- 삭제 요청 대상에는 작업 메타데이터, 정규화 결과 후보, 임시 데이터 잔존 여부 확인이 포함될 수 있다.
- 계약서 본문과 개인정보가 저장되지 않았음을 전제로 하되, 잔존 가능성은 검증해야 한다.
- 사용자 데이터 삭제 요청 시 본문 없는 감사 기록만 유지 후보로 둔다.
- 구체적인 사용자 삭제 UX, 인증 조건, 법률상 보존 예외는 후속 검토가 필요하다.

## 14. 금지 저장 경로

- original contract file -> permanent storage
- extracted text -> permanent storage
- unmasked clause data -> permanent storage
- detected personal data -> permanent storage
- raw provider request -> permanent storage
- raw provider response -> permanent storage
- outbound candidate payload -> raw permanent storage
- contract body -> operational logs
- personal data -> operational logs
- contract body -> audit logs
- personal data -> audit logs
- D1 data -> backup
- real contract data -> test fixture
- real personal data -> test fixture
- deletion failure -> silent success status
- expired data -> continued storage without approval

## 15. 검증 요구사항

- 저장 전 데이터 등급 확인
- D1 영구 저장 시도 차단
- raw provider request 저장 시도 차단
- raw provider response 저장 시도 차단
- outbound candidate payload raw 저장 시도 차단
- 운영 로그에 계약서 본문 또는 개인정보 기록 차단
- 감사 로그에 계약서 본문 또는 개인정보 기록 차단
- 삭제 트리거별 삭제 대상 확인
- 삭제 실패 시 `BLOCK`, `REVIEW`, `RETRY CANDIDATE`, `ESCALATION REQUIRED` 판정 확인
- 보존 기간 미승인 데이터 저장 구현 차단
- synthetic fixture 외 실제 데이터 테스트 차단

## 16. 미결정 사항

- 구체적인 임시 보관 시간
- 구체적인 보존 기간
- 삭제 재시도 횟수
- 삭제 재시도 간격
- backoff 정책
- escalation 담당자
- 백업 보존 기간
- 삭제 전파 방식
- 복구 절차
- 사용자 삭제 요청 UX
- 법률상 보존 의무 적용 여부

## 17. 후속 PR 연결

| 후속 PR | 연결 항목 |
|---|---|
| PR-4 | 외부 전송 통제, outbound allowlist, provider boundary, 실제 전송 데이터 범위 승인 |
| PR-5 | 접근 통제, 실패 처리, 출력 안전, 사용자 고지, 보안 테스트 |
| PR-6 | 통합 검토, 미결정 사항 정리, 최종 설계 결정 |

## 18. 승인 상태

- Storage policy approval: Not approved
- Retention policy approval: Not approved
- Deletion policy approval: Not approved
- Backup policy approval: Not approved
- Logging and audit policy approval: Not approved
- External AI use approval: Not granted
- Real contract use approval: Not granted
- Real personal data use approval: Not granted
- Implementation approval: Not granted
