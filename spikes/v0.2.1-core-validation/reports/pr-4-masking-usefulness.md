# PR-4 마스킹 유용성 검증 보고서

## 1. 검증 목적

- 개인정보를 탐지하고 토큰으로 치환하는 것만으로는 충분하지 않다.
- 마스킹 후에도 계약서 조항 구조와 핵심 의미가 유지되어야 한다.
- 당사자 역할, 문맥, 반복 토큰 일관성, 비개인정보 텍스트 보존을 검증한다.
- 이미 존재하는 마스킹 토큰과 새로 생성되는 토큰의 충돌 가능성을 검증한다.

## 2. 검증 범위

포함 범위:

- 합성 fixture 4개
- 근로계약서 형식 fixture 2개
- edge fixture 2개
- 조항 구조 보존
- 계약 유형 보존
- 비개인정보 텍스트 보존
- 반복 토큰 일관성
- required context
- party role
- residual detection
- preexisting token collision
- 수동 의미 보존 검토

제외 범위:

- 실제 개인정보
- 실제 계약서
- 법률적 적정성 판단
- OCR
- 운영환경 성능
- 외부 AI 평가

## 3. 기준 파일

### 최초 동결 기준

- path: `spikes/v0.2.1-core-validation/data/fixtures/masking-usefulness-expected.sample.json`
- schema: `0.2`
- frozen commit: `ed906d83c1f91cf6b5ec3fb6d810447109750963`

### corrective 동결 기준

- path: `spikes/v0.2.1-core-validation/data/fixtures/masking-usefulness-expected.v0.3.sample.json`
- schema: `0.3`
- frozen commit: `721526aa1cbdabe45e2077ff8a6711d71b4620f5`
- corrective basis: `manual-review-token-collision-discovery`

## 4. 구현 커밋

- `d54c729e33e9609c66cb28b399be3e7a54550a0e`
  - `feat: implement masking usefulness evaluation`
  - PR-4 마스킹 유용성 평가 스크립트와 v0.2 expected 기준의 자동 검증 흐름을 구현했다.
  - 조항 보존, 계약 유형 보존, required context, party role, 반복 토큰, residual detection을 자동 검증 대상으로 연결했다.

- `d4e40a0122e6d8d1b3b82102932a829b6c1daeb7`
  - `fix: strengthen masking usefulness validation`
  - 독립 검토에서 지적된 검증 강도 문제를 보완하고 수동 검토 입력을 반영한 최종 판정 흐름을 강화했다.
  - 자동 검증과 수동 검토 결과가 서로 다른 역할을 갖도록 실패 기록과 요약 판정을 명확히 했다.

- `4f568ff2dbdd78a641c91b727cea544042825125`
  - `fix: avoid preexisting masking token collisions`
  - 원문에 이미 존재하는 마스킹 토큰 ordinal을 예약하고 새 토큰이 같은 ordinal을 재사용하지 않도록 보완했다.
  - PR-3 및 v0.2 동작과의 회귀가 없도록 기본 동작을 유지하면서 v0.3 corrective 기준에서만 충돌 회피 검증을 수행했다.

## 5. 최초 자동 검증

- expected schema: `0.2`
- test cases: `4`
- automatic checks: `36/36`
- automatic failures: `0`
- residual detector matches: `0`
- overall without manual review: `PENDING_REVIEW`

자동 검증은 통과했지만, 수동 의미 보존 검토 전에는 최종 PASS로 확정하지 않았다.

## 6. 최초 수동 검토 실패

- employment-01: `PASS`
- employment-02: `PASS`
- edge-01: `PASS`
- edge-02: `FAIL`

실패 원인:

- 원문에 이미 `[PERSON_1]` 토큰이 존재했다.
- edge-02의 새 인명 마스킹 결과도 `[PERSON_1]`로 생성됐다.
- 서로 다른 대상을 같은 토큰으로 해석할 가능성이 있었다.
- `token_induced_ambiguity_count`: `1`
- `major_meaning_loss_count`: `0`

최초 수동 검토 전체 결과: `FAIL`

이 실패는 자동 검증이 놓친 수동 의미 보존 문제를 수동 검토가 발견한 사례로 보존한다.

## 7. 원인 분석

- 기존 마스킹 구현은 각 entity type의 ordinal을 입력 단위 1부터 생성했다.
- 원문에 이미 존재하는 마스킹 토큰 ordinal을 예약하지 않았다.
- 기존 토큰 span은 일반 텍스트로 남아 있었지만 번호 충돌 방지 기준은 없었다.
- 따라서 원문 `[PERSON_1]`과 새 `[PERSON_1]`이 동시에 존재했다.
- 구조적·형태적 검사는 통과했지만 수동 의미 검토에서 동일 토큰 오해 가능성이 확인됐다.

## 8. corrective 기준

v0.3 corrective expected는 다음 기준을 동결했다.

- `preserve_preexisting_mask_tokens`: `true`
- `reserve_preexisting_token_ordinals`: `true`
- `new_tokens_must_not_reuse_reserved_ordinal`: `true`
- `reservation_scope`: `entity_type`
- 새 ordinal은 같은 entity type의 최고 기존 ordinal 다음부터 시작한다.

edge-02 기대 결과:

- 기존 토큰: `[PERSON_1]`
- 새 토큰: `[PERSON_2]`

## 9. corrective 구현

- 기존 마스킹 토큰 형식을 탐지한다.
- 허용 entity type만 기존 토큰으로 인식한다.
- 기존 토큰 span을 보호한다.
- 기존 토큰과 겹치는 entity 후보를 제거한다.
- entity type별 최고 ordinal을 계산한다.
- 최고 ordinal 다음부터 새 토큰 번호를 생성한다.
- 동일 source value에는 동일 token을 재사용한다.
- entity type 간 ordinal 독립성을 유지한다.
- raw PII를 결과나 로그에 포함하지 않는다.

## 10. 회귀 검증

### PR-3 회귀

- test cases: `4/4`
- entity checks: `26/26`
- exclusion checks: `15/15`
- overlap checks: `0`
- residual matches: `0`
- result: `PASS`

### PR-4 v0.2 회귀

- automatic checks: `36/36`
- automatic failures: `0`
- residual matches: `0`
- result without manual review: `PENDING_REVIEW`
- 기존 numbering 동작 회귀 없음

## 11. v0.3 자동 검증

- test cases: `4`
- automatic checks: `40/40`
- automatic failures: `0`
- residual detector matches: `0`
- manual review pending cases: `4`
- overall before manual review: `PENDING_REVIEW`

edge-02:

- existing token: `[PERSON_1]`
- new token: `[PERSON_2]`
- collision_count: `0`
- reused_reserved_ordinal_count: `0`
- preexisting_token_preservation_failures: `0`
- dense-pii-context: `PASS`
- token separation context: `PASS`

## 12. corrective 수동 검토

| test_case_id | party_roles_preserved | required_context_preserved | major_meaning_loss_count | token_induced_ambiguity_count | result |
|---|---:|---:|---:|---:|---|
| masking-usefulness-pii-employment-01 | true | true | 0 | 0 | PASS |
| masking-usefulness-pii-employment-02 | true | true | 0 | 0 | PASS |
| masking-usefulness-pii-edge-01 | true | true | 0 | 0 | PASS |
| masking-usefulness-pii-edge-02 | true | true | 0 | 0 | PASS |

## 13. 최종 결과

- overall: `PASS`
- test cases: `4`
- automatic checks: `40/40`
- automatic failures: `0`
- manual review pending cases: `0`
- manual review failed cases: `0`
- residual detector matches: `0`
- major meaning loss count: `0`
- token-induced ambiguity count: `0`

## 14. 보안 확인

- 실제 개인정보 사용 없음
- 실제 계약서 사용 없음
- 외부 AI 호출 없음
- 외부 네트워크 호출 없음
- 외부 패키지 설치 없음
- raw PII stdout 없음
- raw PII 결과 필드 없음
- 원문 전체 결과 저장 없음
- PII mapping 저장 없음
- 로컬 절대경로 하드코딩 없음

## 15. 제한사항

- fixture 4개 기반 spike 검증이다.
- 실제 계약서 전체 유형을 대표하지 않는다.
- 수동 의미 검토는 현재 frozen criteria에 한정된다.
- 법률적 정확성이나 법적 효력을 검증하지 않는다.
- party role prescreen은 일부 상황에서 문서 단위 fallback을 사용할 수 있다.
- 최종 의미 보존 판단은 수동 검토가 담당한다.
- 제품 출시 전 전문가 및 법률 검토가 필요하다.

## 16. 결론

- 최초 자동 검증만으로는 발견하지 못한 토큰 모호성을 수동 검토가 발견했다.
- 실패 기록을 보존하고 corrective expected를 구현 전에 동결했다.
- corrective 구현 후 PR-3와 v0.2 회귀가 없음을 확인했다.
- v0.3 자동 검증과 수동 검토가 모두 통과했다.
- PR-4 spike 목적은 충족됐다.
- 이 결과는 운영 적용이나 법적 안전성을 보장하는 결과가 아니다.
