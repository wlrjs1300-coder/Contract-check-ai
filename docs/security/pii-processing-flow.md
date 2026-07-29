# ContractCheck AI Personal Data Processing Flow

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

이 문서는 ContractCheck AI v0.2.2 PR-2 범위에서 개인정보 처리 흐름 초안을 정의한다.

목적은 파일 입력부터 사용자 표시 후보 생성까지 어떤 단계에서 개인정보를 탐지, 마스킹, 검증, 차단, 삭제해야 하는지 설계 수준으로 정리하는 것이다.

## 2. 전제 조건

- 이 문서는 구현 사양이 아니라 설계 초안이다.
- 외부 AI 호출은 승인되지 않았다.
- 공급자는 선정되지 않았다.
- 실제 계약서와 실제 개인정보는 사용할 수 없다.
- PR-3 마스킹 결과는 후속 설계의 참고 근거일 뿐 실제 개인정보 처리 승인으로 해석하지 않는다.
- PR-4 마스킹 유용성 검증은 합성 fixture 기준이며 실제 외부 전송 승인으로 해석하지 않는다.
- PR-5 출력 안전성 검증은 후속 출력 검증 요구사항으로 연결하되 제품 운영 승인으로 해석하지 않는다.

## 3. 전체 처리 흐름

1. 사용자 파일 입력
2. 파일 형식과 크기 검증
3. 임시 처리 영역 생성
4. 텍스트 추출
5. 조항 분할
6. source_hash 생성
7. reference_id 생성
8. 개인정보 탐지
9. 개인정보 마스킹
10. residual 개인정보 검증
11. 외부 전송 후보 payload 구성
12. outbound allowlist 검증
13. 전송 허용 여부 판정
14. 외부 AI 호출 후보 단계
15. 응답 schema 검증
16. reference_id 검증
17. 출력 안전성 검증
18. 정규화 결과 생성
19. 최소 메타데이터 저장 후보
20. 임시 원문 및 중간 데이터 삭제
21. 사용자 표시 후보 생성

14단계는 외부 AI 호출을 실행하는 단계가 아니다. 별도 승인 전까지 실제 호출은 `NOT EXECUTED` 상태로 유지한다.

## 4. 단계별 입력과 출력

| Step | Input | Output | Decision | Required control |
|---|---|---|---|---|
| 사용자 파일 입력 | User-selected file | Upload candidate | NOT EXECUTED | Real data use not approved |
| 파일 형식과 크기 검증 | Upload candidate | Validated file candidate | BLOCK on failure | Format and size policy required |
| 임시 처리 영역 생성 | Validated file candidate | Temporary processing context | REVIEW until PR-3 | No permanent source storage |
| 텍스트 추출 | Temporary file | Extracted text | BLOCK on failure | Temporary only |
| 조항 분할 | Extracted text | Clause data | BLOCK on failure | Preserve source mapping |
| source_hash 생성 | Source text candidate | Non-reversible source_hash | BLOCK on failure | No source text in hash metadata |
| reference_id 생성 | Clause data | reference_id mapping | BLOCK on failure | Stable mapping without body logs |
| 개인정보 탐지 | Clause data | Detected personal data candidates | REVIEW if unclear | Detection result source remains internal |
| 개인정보 마스킹 | Clause data and detections | Masked clause data | BLOCK on failure | No raw detected values in logs |
| residual 개인정보 검증 | Masked clause data | residual scan result | BLOCK if detected | residual 0 required |
| 외부 전송 후보 payload 구성 | Masked clause data | outbound candidate payload | NOT EXECUTED | Separate approval required |
| outbound allowlist 검증 | outbound candidate payload | allowlist decision | BLOCK on violation | Only approved fields |
| 전송 허용 여부 판정 | residual and allowlist results | transfer decision | NOT EXECUTED | Provider approval required |
| 외부 AI 호출 후보 단계 | approved candidate only | external response candidate | NOT EXECUTED | No actual call in PR-2 |
| 응답 schema 검증 | external response candidate | schema decision | BLOCK on failure | No raw response storage |
| reference_id 검증 | normalized response candidate | association decision | BLOCK or REVIEW on mismatch | Safe association required |
| 출력 안전성 검증 | normalized response candidate | output safety decision | BLOCK/REVIEW on unsafe output | PR-5 safety rules |
| 정규화 결과 생성 | validated response candidate | normalized analysis result | REVIEW until PR-5 | Store only normalized candidate |
| 최소 메타데이터 저장 후보 | job metadata | metadata candidate | REVIEW until PR-3 | No body, no personal data |
| 임시 원문 및 중간 데이터 삭제 | temporary data | deletion metadata | REVIEW/BLOCK on failure | Delete source and intermediate sensitive data |
| 사용자 표시 후보 생성 | validated normalized result | display candidate | REVIEW until PR-5 | No legal conclusion or guarantee |

## 5. 개인정보 탐지와 마스킹

- 개인정보 탐지는 원문 또는 조항 데이터가 내부 임시 처리 영역에 있을 때만 수행한다.
- 탐지 결과는 외부 전송 후보가 아니다.
- 마스킹 결과는 안전하다고 단정하지 않는다.
- 마스킹 실패는 `BLOCK`이다.
- 탐지 결과가 불명확하면 `REVIEW`이다.
- 로그에는 탐지된 원문 값, raw text, source value를 기록하지 않는다.

## 6. residual 검증

residual 검증은 마스킹 후에도 개인정보가 남았는지 확인하는 단계이다.

- residual 개인정보 발견 시 `BLOCK`
- residual scan inconclusive이면 `REVIEW`
- residual 0이 아니면 외부 전송 후보가 될 수 없음
- residual 결과는 본문 없이 상태, 코드, 통계 후보로만 다룸
- residual 검증 방법과 threshold는 후속 PR에서 확정

## 7. 외부 전송 후보 생성

외부 전송 후보 payload는 실제 외부 전송 승인이 아니라 후속 PR-4 검토를 위한 설계 후보이다.

후보가 되려면 다음 조건이 모두 필요하다.

- source file 없음
- extracted text 없음
- detected personal data 없음
- masking complete
- residual 0
- allowlist pass
- allowed clause-level data only
- reference_id included
- source_hash non-reversible form
- provider use separately approved
- endpoint/model separately approved
- cost/timeout/retry policy set

현재 PR-2에서는 provider use, endpoint/model, cost/timeout/retry 정책이 승인되지 않았으므로 실제 결정은 `NOT EXECUTED`이다.

## 8. 차단·검토·허용 판정

판정값은 `ALLOW`, `BLOCK`, `REVIEW`, `NOT EXECUTED`만 사용한다.

### BLOCK 조건

- file format/size validation fails
- clause splitting fails
- source_hash creation fails
- reference_id creation fails
- PII masking fails
- residual PII detected
- outbound allowlist violation
- contract source/extracted source included
- unmasked clause data included in outbound payload
- 외부 전송 payload에 마스킹 전 clause data가 포함된 경우 BLOCK
- unauthorized field included
- response schema validation fails
- reference_id validation failure where safe association impossible
- legal conclusion/guarantee expression included
- raw response storage attempted
- log attempts to write contract body or PII

### REVIEW 조건

- PII detection result unclear
- residual scan inconclusive
- reference_id partial mismatch
- confidence score below policy threshold
- risk analysis needing expert review
- output safety borderline
- deletion failure where an immediate safe BLOCK decision is not yet possible

민감 데이터가 남아 있을 가능성이 있으면 `BLOCK`을 우선한다. 안전 여부 판단을 위해 추가 확인이 필요한 삭제 실패는 `REVIEW`로 둔다. 구체적인 삭제 재시도 정책과 횟수는 PR-3에서 결정한다.

### ALLOW 후보 조건

`ALLOW`는 실제 외부 전송 승인 또는 제품 운영 승인이 아니다. 후보 조건은 다음과 같다.

- no source file
- no extracted text
- no detected personal data
- no unmasked clause data
- masking complete
- residual 0
- allowlist pass
- allowed clause-level data only
- reference_id included
- source_hash non-reversible form
- provider use separately approved
- endpoint/model separately approved
- actual outbound data scope separately approved
- cost incurrence separately approved
- cost/timeout/retry policy set
- final user approval obtained
- 실제 전송 데이터 범위 별도 승인
- 비용 발생 별도 승인
- 사용자 최종 승인

### NOT EXECUTED 조건

- PR-2에서 실제 외부 AI 호출은 실행하지 않는다.
- provider selection이 없다.
- external AI use approval이 없다.
- endpoint/model selection이 없다.
- provider adapter implementation이 없다.

## 9. 저장과 삭제 연결

- original contract file은 임시 처리 전용이며 영구 저장하지 않는다.
- extracted text는 임시 처리 전용이며 영구 저장하지 않는다.
- unmasked clause data is temporary processing data.
- permanent storage of unmasked clause data is prohibited.
- unmasked clause data must be deleted after successful masking or when processing is blocked.
- 마스킹 전 clause data는 임시 처리 데이터이며 영구 저장하지 않는다.
- 마스킹 전 clause data는 마스킹 완료 후 또는 처리 차단 시 삭제 대상이다.
- masked clause data는 임시 데이터 또는 저장 후보일 수 있으나 승인 전 영구 저장하지 않는다.
- 정상 완료, 실패, 차단 후 민감 임시 데이터를 삭제한다.
- 삭제 실패 시 작업을 `REVIEW` 또는 `BLOCK`으로 표시한다.
- 삭제 완료 여부는 본문 없이 metadata로만 기록한다.
- 보존 시간, 삭제 재시도, 백업 처리, 임시 보관 정책은 PR-3에서 결정한다.

## 10. 로그·감사 연결

- operational logs에는 계약서 본문을 기록하지 않는다.
- operational logs에는 개인정보를 기록하지 않는다.
- raw provider request와 raw provider response를 기록하지 않는다.
- 로그 후보는 job status, error code, block reason code, processing duration, retry count, policy version 등 최소 메타데이터로 제한한다.
- audit metadata의 보존 기간과 접근 통제는 PR-3과 PR-5에서 결정한다.

## 11. 실패 처리

| Failure | Decision | User-facing direction | Follow-up PR |
|---|---|---|---|
| File validation failure | BLOCK | 다시 업로드 가능한 실패로 안내 | PR-5 |
| Text extraction failure | BLOCK | 분석을 진행하지 않음 | PR-5 |
| Clause splitting failure | BLOCK | 분석 실패 또는 재시도 후보로 분리 | PR-5 |
| PII detection unclear | REVIEW | 검토 필요 상태로 처리 | PR-5 |
| PII masking failure | BLOCK | 분석을 진행하지 않음 | PR-5 |
| Residual PII detected | BLOCK | 외부 전송 금지 및 내부 차단 | PR-4 |
| Allowlist violation | BLOCK | 외부 전송 금지 | PR-4 |
| Provider unavailable | NOT EXECUTED | PR-2에서는 호출하지 않음 | PR-5 |
| Response schema failure | BLOCK | 결과 표시 금지 | PR-5 |
| Output safety failure | BLOCK or REVIEW | 결과 표시 금지 또는 검토 필요 | PR-5 |
| Deletion failure | REVIEW or BLOCK | 후속 처리 필요 상태로 기록 | PR-3 |

## 12. 금지 흐름

- original file -> external AI
- extracted text -> external AI
- unmasked clause data -> external AI: PROHIBITED
- masked clause data -> external AI before residual 0, allowlist pass, and separate approval: PROHIBITED
- masked clause -> external AI until approval
- detected PII result source -> external AI
- residual detected data -> external AI
- non-allowlisted payload -> external AI
- raw provider response -> persistent storage
- contract body -> operational logs
- personal data -> operational logs
- real data -> test fixtures
- external AI response -> user display without validation

마스킹 전 clause data는 어떤 경우에도 외부 AI로 전송하지 않는다. 마스킹된 clause data도 residual 0 확인, outbound allowlist 통과, 공급자 별도 승인, endpoint 별도 승인, model 별도 승인, 실제 전송 데이터 범위 별도 승인, 비용 발생 별도 승인, 사용자 최종 승인 전에는 외부 AI로 전송하지 않는다. Masked clause data must not be transferred to an external AI provider before final user approval.

## 13. 미결정 사항

- file size와 format validation의 구체 기준
- 임시 처리 영역의 보관 시간
- 개인정보 탐지 대상과 탐지 범위
- 마스킹 형식
- residual 검증 기준
- outbound allowlist 필드
- provider endpoint/model 후보
- timeout, retry, cost limit
- 삭제 실패 재시도 정책
- 사용자 고지 문구

## 14. 승인 상태

- PII processing flow approval: Not approved
- Data classification detail approval: Not approved
- Trust boundary approval: Not approved
- External AI use approval: Not granted
- Real contract use approval: Not granted
- Real personal data use approval: Not granted
- Implementation approval: Not granted
