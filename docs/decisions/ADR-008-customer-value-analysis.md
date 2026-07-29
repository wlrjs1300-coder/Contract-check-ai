# ADR-008: Customer Value Analysis Result Contract (v0.6.9)

## Status
Accepted (Backend API contract hardening)

## Context
v0.6.9에서 고객 가치 분석 결과를 API로 확정하기 위해 다음 위험을 제거해야 했다.
- questions/suggestions/facts의 evidence 자동 fallback
- expert review reason 코드의 규격 불일치
- analysis_summary의 top priority를 단순 문자열 배열로만 반환
- 누락/모호 상태를 단정 표현으로 표시

## Decision
1. 증거 연계는 자동 생성 불가로 변경
- 질문/제안의 `related_evidence_ids`와 fact의 `evidence`는 provider가 생성 시 반드시 명시한다.
- 빈 값은 validation 실패(`question_evidence_missing`, `suggestion_evidence_missing`, `fact_evidence_missing`).

2. expert review reason 코드는 고정 상수 집합
- 코드 집합을 고정하고 승인되지 않은 코드는 reject한다.
- `expert_review_recommended`가 true일 때 codes가 없으면 실패.
- codes 존재 시 `expert_review_summary`가 필수.

3. analysis_summary를 구조화
- `top_priorities`를 객체 배열로 고정:
  - `finding_id`, `severity`, `title`, `action_priority`
- `total_findings`는 severity 카운트 합과 일치해야 함
- `missing_terms_count`, `ambiguity_count` 집계 포함

4. 날짜·금액·의무 정규화 정책의 응답 반영
- fact-level 값(`date_value`, `amount_value`, `obligation_party`)을 결과로 노출하고
- context에 기반한 경고 항목은 별도 카운트로 표시한다.

## Consequences
- provider 구현은 더 엄격해지고 이전 테스트가 증가한다.
- 프론트와 하위 연동자는 `related_evidence_ids` 미부여 항목을 가정해선 안 된다.
- plan-independent 테스트를 통해 등급별 결과 차등이 없음을 보장한다.

## Rejected Alternatives
- 누락된 evidence를 첫 번째 evidence로 자동 매핑하는 방식
- `top_priorities`를 severity 문자열만 나열하는 방식
- expert review 코드 없이 권장 상태만 true로 표기하는 방식

## Rollout
- backend tests 증가 적용 후 OpenAPI 문서 및 회귀 테스트 통과를 통해 단계적 반영
- frontend는 문서 계약을 기준으로 화면 렌더링만 확장
