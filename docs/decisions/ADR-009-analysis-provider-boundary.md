# ADR-009: Analysis Provider Boundary

- Status: Accepted for v0.7.0 foundation
- Date: 2026-07-21
- Scope: v0.7.x analysis provider execution, factory, and contract handling

## Context

현재 백엔드는 v0.3 계열 Synthetic 분석 흐름을 사용하고 있고, v0.7에서는 provider contract 기반의 실행 경계와 오류/보안 규칙을 먼저 정리해야 한다.

목표는 실서비스 provider 연동 전, 다음을 선행적으로 고정하는 것이다.

- 요청/응답 schema 버전 계약
- 실패 코드 단일화
- 크기 제한과 candidate/evidence 정합성
- 재시도와 비재시도 오류 경계
- raw data 보안 노출 제한

## Decision

### 1) Provider factory 환경 정책

- `APP_ENV=test`:
  - 기본 동작은 synthetic
  - `ANALYSIS_PROVIDER=fake` 허용
- `APP_ENV=development`:
  - 기본값은 `unavailable` 또는 명시 설정
- `APP_ENV=production`:
  - synthetic/fake 모두 차단
  - real provider 미연결 상태에서 임의 허용 금지
  - 미설정/unknown provider는 명시적 오류 코드로 실패

허용 오류 코드:

- `analysis_provider_forbidden`
- `analysis_provider_unknown`
- `analysis_provider_not_configured`
- `analysis_provider_unavailable`

### 2) Fake provider 범위

v0.7 foundation에서는 다음 mode를 deterministic하게 지원한다.

- success
- timeout
- rate_limit
- temporary_failure
- permanent_failure
- invalid_schema
- unsupported_schema_version
- request_id_mismatch
- unknown_candidate
- duplicate_candidate
- empty_evidence
- missing_required_field
- oversized_response
- too_many_findings

### 3) 실행 규칙

- timeout/rate_limit/temporary failure는 retry 가능
- permanent/schema/request/response size/unknown candidate 등은 retry 불가
- retry exhausted는 별도 코드로 종료
- request/response 바이트 제한은 UTF-8 기준으로 사전 검사

## Consequences

- 현재 구현은 실제 외부 API 연동 없이 결정론적 방식으로 재현 가능
- contract 위반 응답은 API 노출을 통해 실패로만 노출되고, 원시 payload는 보관하지 않음
- 향후 real provider가 도입되더라도 동일 오류 경계를 상향 확장(오류 코드 체계 보존)해야 함
- `provider_rate_limited` 등 v0.7 코드와 기존 레거시 alias는 구분되어 사용
