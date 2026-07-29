# ContractCheck AI Data Classification

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

이 문서는 ContractCheck AI v0.2.2 PR-2 범위에서 데이터 분류 초안을 정의한다.

목적은 계약서 분석 흐름에서 등장할 수 있는 데이터 항목을 민감도, 저장 가능성, 로그 가능성, 외부 전송 후보 여부에 따라 분류하고 후속 PR에서 결정해야 할 통제 항목을 명확히 분리하는 것이다.

## 2. 적용 범위

적용 범위는 v0.2.2 개인정보·보안 통합 설계의 설계 문서에 한정한다.

이 문서는 다음을 승인하지 않는다.

- 구현 시작
- 실제 계약서 사용
- 실제 개인정보 사용
- 외부 AI API 호출
- 공급자 선정
- provider adapter 구현
- 영구 저장 정책 확정
- 외부 전송 정책 확정

## 3. 분류 원칙

- 데이터는 최소 수집, 목적 제한, 최소 저장, 최소 로그 원칙을 따른다.
- 원본 계약서와 추출 원문은 가장 민감한 데이터로 취급한다.
- 마스킹된 데이터도 계약 의미와 개인정보 관련 단서를 포함할 수 있으므로 안전하다고 단정하지 않는다.
- residual 개인정보가 발견된 데이터는 외부 전송할 수 없다.
- outbound allowlist를 통과하지 못한 데이터는 외부 전송할 수 없다.
- raw provider request와 raw provider response는 저장 후보가 아니다.
- 운영 로그에는 계약서 본문, 개인정보, 외부 응답 원문을 기록하지 않는다.
- 실제 데이터 테스트는 별도 승인 전 금지한다.
- 이 분류는 PR-2 초안이며 독립 검토와 사용자 승인 전까지 최종 기준이 아니다.

## 4. 데이터 등급

### D1 - Restricted

가장 민감한 등급이다.

예시는 다음과 같다.

- original contract file
- extracted text
- clause data containing personal data
- detected personal data
- unmasked source text
- derived or reconstructed text that can reveal original contract content or personal data
- raw provider request
- raw provider response

처리 원칙은 다음과 같다.

- 외부 전송 금지
- 운영 로그 기록 금지
- 영구 저장 금지
- 실제 데이터 사용 금지
- 테스트는 합성 fixture만 사용
- 처리 실패 시 안전 삭제 또는 차단
- 임시 보존 시간은 PR-3에서 결정

### D2 - Sensitive

마스킹됐더라도 계약 의미, 조항 맥락, 개인정보 관련 단서를 포함할 수 있는 등급이다.

예시는 다음과 같다.

- masked clause data
- residual scan result
- outbound candidate payload
- normalized analysis result
- confidence score
- expert review recommendation
- analysis block reason

처리 원칙은 다음과 같다.

- residual 검증 통과 전 외부 전송 금지
- outbound allowlist 통과 전 외부 전송 금지
- 저장은 최소 후보만 검토
- 로그는 상태, 코드, 통계만 기록하고 원문을 기록하지 않음
- 보존 기간은 PR-3에서 결정
- 외부 전송 후보 여부는 PR-4에서 별도 승인 필요

### D3 - Internal

본문과 개인정보를 포함하지 않는 내부 메타데이터 등급이다.

예시는 다음과 같다.

- source hash
- reference_id
- job status
- policy/model/endpoint version
- processing time
- error code
- retry count
- block status
- deletion metadata
- audit metadata

처리 원칙은 다음과 같다.

- 최소 수집
- 목적 제한
- 접근 통제
- 계약서 본문과 개인정보 포함 금지
- 보존 기간은 PR-3에서 결정
- 감사에 필요한 최소 필드만 유지

### D4 - Public

계약서 데이터, 사용자 데이터, 내부 보안 세부 정보를 포함하지 않는 공개 가능 등급이다.

예시는 다음과 같다.

- public service description
- public policy wording
- de-identified general guide
- public version info

처리 원칙은 다음과 같다.

- 계약서 또는 사용자 데이터 포함 금지
- 공개 전 별도 검토
- 내부 보안 세부 정보 포함 금지

### Synthetic / Non-production (D1~D4와 별도 축)

Synthetic/Non-production은 D1~D4 등급의 다섯 번째 단계가 아니라, "실제 데이터 여부"를 나타내는 별도 축이다. 어떤 데이터가 D1~D4 중 무엇을 모사하는지와, 그 데이터가 실제(real)인지 가상(synthetic)인지는 서로 다른 질문이며 함께 표시할 수 있다(예: "D1-shape, Synthetic").

원칙은 다음과 같다.

- Synthetic 데이터는 실제 계약서, 실제 개인정보, 실제 고객 데이터가 아니다.
- Synthetic 데이터는 지정된 테스트 경로에서만 사용한다. 경로는 `docs/03-security-rules.md` §11에 이미 정의된 범위(`docs/samples/`, `backend/tests/fixtures/`)를 그대로 따르며, 이 문서에서 새 경로를 정의하지 않는다.
- Synthetic 데이터는 실제 데이터와 동일한 저장소·로그·전송 경로에 혼합하지 않는다.
- Synthetic 데이터는 외부 전송을 하지 않는다.
- Synthetic이라는 이유만으로 D4(Public) 또는 공개 가능으로 간주하지 않는다. Synthetic 데이터가 모사하는 대상이 D1~D2급 구조(예: 가상 계약서 원문, 가상 개인정보 패턴)라면, 저장·로그·경로 격리 기준은 모사 대상 등급(D1~D2)에 준하는 안전 기준을 참고한다.
- Synthetic 상태는 D1~D4 등급을 대체하지 않는다.

이 상태는 v0.2.3에서 신설하는 후보 개념이며, 세부 fixture 카탈로그·명명 규칙·검토 절차는 후속 보안 테스트 설계에서 확정한다.

## 5. 데이터 분류표

| Data item | Proposed classification | Contains contract content | May contain personal data | Persistence candidate | Logging allowed | External transfer candidate | Required control | Decision status | Follow-up PR |
|---|---|---|---|---|---|---|---|---|---|
| original contract file | D1 - Restricted | Yes | Yes | No | No | No | Temporary processing only, delete or block on failure | PROHIBITED | PR-3 |
| extracted text | D1 - Restricted | Yes | Yes | No | No | No | Temporary processing only, no external transfer | PROHIBITED | PR-3 |
| clause data | D1 - Restricted | Yes | Yes | No | No | No | Clause mapping only before masking | PROHIBITED | PR-2 |
| source hash | D3 - Internal | No | No | Yes | Yes | Review needed | Non-reversible hash, no source text | PROPOSED | PR-3 |
| reference_id | D3 - Internal | No | No | Yes | Yes | Review needed | Stable mapping without body text | PROPOSED | PR-4 |
| detected personal data | D1 - Restricted | Yes | Yes | No | No | No | Detection result source must not leave internal flow | PROHIBITED | PR-2 |
| masked clause data | D2 - Sensitive | Yes | Possible | Review needed | No body logs | Deferred | Residual scan and allowlist before any transfer candidate | DEFERRED | PR-4 |
| residual scan result | D2 - Sensitive | Possible | Possible | Minimal candidate | Status only | No | Residual found means block | PROPOSED | PR-2 |
| outbound candidate payload | D2 - Sensitive | Yes | Possible | No raw storage | Metadata only | Deferred | Residual 0, allowlist pass, separate approval | REVIEW REQUIRED | PR-4 |
| provider request | D1 - Restricted | Yes | Possible | No | No | No | Raw request storage prohibited, external transfer not approved, and only a future normalized outbound payload may be reviewed separately in PR-4 | PROHIBITED | PR-4 |
| provider response | D1 - Restricted | Possible | Possible | No | No | N/A | Raw response storage prohibited, normalize first | PROHIBITED | PR-5 |
| normalized analysis result | D2 - Sensitive | Possible | Possible | Review needed | Status only | No | Schema validation and output safety | DEFERRED | PR-5 |
| display label | D2 - Sensitive | Possible | Possible | Review needed | Status only | No | Output safety and legal expression check | DEFERRED | PR-5 |
| confidence score | D2 - Sensitive | No | No | Review needed | Aggregate only | No | No user-facing risk score without later approval | REVIEW REQUIRED | PR-5 |
| expert review recommendation | D2 - Sensitive | Possible | Possible | Review needed | Status only | No | Must not imply legal advice or safety guarantee | DEFERRED | PR-5 |
| job status | D3 - Internal | No | No | Yes | Yes | No | Status code only | PROPOSED | PR-3 |
| audit metadata | D3 - Internal | No | No | Yes | Yes | No | No body, no personal data; allowlist fields only (see logging-audit.md); raw payload is a separate D2 item below | PROPOSED | PR-3 |
| operational logs | D3 - Internal | No | No | Yes | Yes | No | No body, no personal data, no raw response; allowlist fields only (see logging-audit.md); raw payload is a separate D2 item below | PROPOSED | PR-3 |
| deletion metadata | D3 - Internal | No | No | Yes | Yes | No | Completion/failure metadata only | PROPOSED | PR-3 |
| policy version | D3 - Internal | No | No | Yes | Yes | Possible | Version string only | PROPOSED | PR-4 |
| model version | D3 - Internal | No | No | Yes | Yes | Possible | Version string only, no payload | REVIEW REQUIRED | PR-4 |
| endpoint version | D3 - Internal | No | No | Yes | Yes | Possible | Endpoint identifier only, no payload | REVIEW REQUIRED | PR-4 |
| error code | D3 - Internal | No | No | Yes | Yes | No | Code only, no raw text | PROPOSED | PR-5 |
| block reason | D2 - Sensitive | Possible | Possible | Review needed | Code only | No | Avoid body excerpt or personal data | REVIEW REQUIRED | PR-5 |
| retry count | D3 - Internal | No | No | Yes | Yes | No | Numeric count only | PROPOSED | PR-5 |
| processing duration | D3 - Internal | No | No | Yes | Yes | No | Timing metadata only | PROPOSED | PR-3 |
| raw operational/audit log payload | D2 - Sensitive | Possible | Possible | No | No | No | Free-text or body-bearing log/exception content; must not be written to any log; distinct from allowlist-compliant metadata above | PROHIBITED | v0.2.3 |
| document metadata (excluding original filename) | D3 - Internal | No | No | Yes | Yes | Review needed | document_id, status, timestamps, storage/deletion state only; excludes original filename (see separate item) | PROPOSED | v0.2.3 |
| original filename | D2 - Sensitive | Possible | Possible | Review needed | No | No | May identify user or contract; do not log; external transfer prohibited | REVIEW REQUIRED | v0.2.3 |
| external transfer metadata | D3 - Internal | No | No | Yes | Yes | N/A (metadata about a transfer, not payload) | request_id, correlation_id, reference_id, provider/endpoint/model approval status, policy/schema version, event/result/block reason code, retry count, timestamp only; no raw payload or response body | PROPOSED | v0.2.3 |
| security event log | D3 - Internal | No | No | Yes | Yes | No | Event code, actor/target identifier, block reason code, severity only; no raw payload or detected PII value | PROPOSED | v0.2.3 |
| email address (account) | D1 - Restricted | No | Yes | Review needed | No | No | Authentication-adjacent personal data; do not log; masking not applicable (account field, not contract content); access-control governed | REVIEW REQUIRED | v0.2.3 |
| user_id | D3 - Internal (REVIEW REQUIRED) | No | No | Yes | Review needed | Review needed | Directly linkable to a real account, same caution as actor_id in logging-audit.md; not treated as fully non-sensitive | REVIEW REQUIRED | v0.2.3 |
| password hash | D1 - Restricted | No | No | Review needed | No | No | Authentication credential in derived form; classified by credential sensitivity, not by reversibility; must not be equated with source_hash, which is a non-reversible content-reference hash for non-secret text; plaintext password storage remains prohibited | REVIEW REQUIRED | v0.2.3 |
| authentication token (access/refresh token, API key) | D1 - Restricted | No | No | No | No | No | Credential; server-side secret store only; must not be logged or exported | PROHIBITED | v0.2.3 |
| session identifier | D2 - Sensitive (D1 if it functions as a bearer token) | No | No | Review needed | No | No | Default D2 per existing external-transfer-control.md precedent; re-review to D1 required if the identifier itself carries authentication authority (bearer-style) | REVIEW REQUIRED | v0.2.3 |
| role/permission information | D3 - Internal (REVIEW REQUIRED when combined with user_id) | No | No | Yes | Review needed | Review needed | Role category alone is low sensitivity; combined with a specific user_id it reveals a real account's privilege level | REVIEW REQUIRED | v0.2.3 |

### normalized analysis result의 D3 추출 허용 필드

normalized analysis result 컨테이너 자체는 위 표와 같이 D2 - Sensitive로 고정한다. 다음 필드는 원문, 인용문, 개인정보, 자유 텍스트를 포함하지 않는 경우에 한해 로그·감사 등 최소화 목적으로 D3 필드로 별도 추출할 수 있다. 이 화이트리스트는 컨테이너 자체의 등급을 낮추지 않는다.

- document_id
- clause_id
- reference_id
- model_version
- provider_version
- timestamp
- status

위 목록에 없는 필드(조항 원문, 인용문, risk_reason, evidence, 개인정보 등 자유 텍스트를 포함할 수 있는 필드)는 D3로 추출할 수 없으며 D2 컨테이너 등급을 그대로 따른다.

## 6. 처리·저장·로그·외부 전송 기준

- D1 데이터는 영구 저장, 운영 로그 기록, 외부 전송 후보에서 제외한다.
- D2 데이터는 최소 저장 후보로만 검토하며, 외부 전송 후보가 되려면 residual 0, outbound allowlist 통과, 별도 승인 조건이 모두 필요하다.
- D3 데이터는 본문과 개인정보가 없을 때만 저장과 로그 후보가 될 수 있다.
- D4 데이터는 공개 전 별도 공개 기록 검토가 필요하다.
- provider request와 provider response는 raw 형태로 저장하지 않는다.
- 로그에는 본문, 개인정보, raw external response, raw provider request를 기록하지 않는다.
- 보존 기간, 삭제 재시도, 백업 처리, 접근 권한은 PR-3 이후에 확정한다.
- 외부 전송 후보와 allowlist는 PR-4에서 별도 승인한다.

## 7. 금지 규칙

- original contract file external transfer prohibited
- extracted text external transfer prohibited
- detected personal data external transfer prohibited
- unmasked clause data external transfer prohibited
- 마스킹 전 clause data 외부 전송 금지
- masked clause data external transfer prohibited until approved
- raw provider request storage prohibited
- raw provider response storage prohibited
- contract body in operational logs prohibited
- personal data in operational logs prohibited
- real contract data tests prohibited
- real personal data tests prohibited
- data with residual PII external transfer prohibited
- fields not in allowlist external transfer prohibited

## 8. 미결정 사항

- D2 데이터의 영구 저장 가능 여부
- D2 데이터의 보존 기간
- source_hash와 reference_id의 저장 범위
- normalized analysis result의 저장 범위
- block reason의 사용자 표시 범위
- model version과 endpoint version의 기록 형식
- 외부 전송 allowlist
- 삭제 실패 시 차단 또는 재시도 정책
- 운영 로그와 감사 로그의 최소 필드

## 9. 후속 PR 연결

| 후속 PR | 연결 항목 |
|---|---|
| PR-3 | 저장, 보존, 삭제, 로그, 감사 정책 |
| PR-4 | 외부 전송 통제, outbound allowlist, provider boundary |
| PR-5 | 접근 통제, 실패 처리, 출력 안전, 사용자 고지, 보안 테스트 |
| PR-6 | 통합 검토, 미결정 사항 정리, 최종 설계 결정 |

## 10. 승인 상태

- Data classification detail approval: Not approved
- PII processing flow approval: Not approved
- Trust boundary approval: Not approved
- External AI use approval: Not granted
- Real contract use approval: Not granted
- Real personal data use approval: Not granted
- Implementation approval: Not granted
